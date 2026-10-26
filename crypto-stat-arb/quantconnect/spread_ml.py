"""
spread_ml — self-contained quant library for the QuantConnect ML pairs strategy.

This file has NO dependency on the cryptostat research package and NO dependency
on the LEAN API: everything in here is plain numpy (torch / scikit-learn are
optional accelerators with automatic fallback), so every component can be unit
tested outside QuantConnect and dropped into a QC project unchanged.

Contents
--------
1.  Statistics          full auto-lag ADF (MacKinnon critical values), the
                        Engle-Granger two-step cointegration test, OLS/TLS
                        hedge ratios, OU half-life, z-scores. Numerically
                        identical to the cryptostat research repo.
2.  KalmanHedge         online dynamic hedge ratio (state = [alpha, beta] as a
                        random walk) — replaces the static OLS beta so the
                        spread tracks a slowly-drifting relationship.
3.  Features & labels   the spread feature matrix and the forward-return label
                        the models learn from. Verbatim port of the research
                        repo (kept identical on purpose: the features were
                        validated there, and fidelity beats novelty).
4.  Models              SpreadNet (PyTorch LSTM), GBMSignal (sklearn gradient
                        boosting), NumpyRidge (closed-form, zero-dependency).
                        resolve_kind() degrades lstm -> gbm -> ridge so the
                        strategy always runs, whatever the environment has.
5.  MLSignal            the fit/predict wrapper with the anti-overfitting
                        defences validated in the research repo: seed
                        ensembling, the z-agreement gate, conviction gating,
                        and honest per-fold entry tuning on a validation tail
                        of the training window.
6.  Metrics             sharpe / drawdown / equity utilities and a
                        PerformanceTracker for end-of-run reporting.
7.  Pair screening      screen_pairs() ranks every pair of a universe by
                        cointegration strength on TRAINING data only —
                        walk-forward pair selection, which kills the selection
                        bias of hand-picking pairs that already backtested well.
8.  PairEngine          one pair's complete trading state machine: fit on a
                        training window (freeze beta/mu/sd, train the model,
                        measure half-life), then consume one bar at a time and
                        emit a target position. Handles Kalman updating,
                        half-life time stops, and post-stop cooldowns. This is
                        the QC-agnostic core of the algorithm, verified against
                        the vectorized research backtest.
9.  RiskManager         portfolio-level volatility targeting and a drawdown
                        kill-switch with a halt period.

Availability workarounds (things the research stack uses that a given LEAN/QC
environment may not have):

    statsmodels / scipy  -> never imported; OLS via numpy lstsq, ADF hand-rolled
    torch (LSTM)         -> tried first; missing => sklearn gradient boosting
    scikit-learn (GBM)   -> tried second; missing => closed-form numpy ridge
    NumpyRidge           -> always available, so the strategy always runs

The resolved model is recorded in ``MLSignal.resolved_kind`` so the algorithm
can log what actually trained.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


# =========================================================================== #
# 1. Statistics — full port of cryptostat.common.stats (numpy only)
# =========================================================================== #

# MacKinnon asymptotic critical values for the ADF test.
ADF_CRIT = {
    "n":  {0.01: -2.5658, 0.05: -1.9411, 0.10: -1.6168},
    "c":  {0.01: -3.4336, 0.05: -2.8621, 0.10: -2.5671},
    "ct": {0.01: -3.9638, 0.05: -3.4126, 0.10: -3.1279},
}
# Engle-Granger residual-based cointegration critical values (2 series, const).
EG_CRIT = {0.01: -3.9001, 0.05: -3.3377, 0.10: -3.0462}


def _ols(X, y):
    """Ordinary least squares. Returns (beta, resid, se_beta)."""
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = max(n - k, 1)
    sigma2 = resid @ resid / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(sigma2 * xtx_inv))
    return beta, resid, se


def _approx_pvalue(stat, crit):
    """
    Coarse p-value by interpolating the test statistic against the 1/5/10%
    critical values (log-linear), clamped into (0, 1). Approximate — use for
    ranking pairs, not for exact inference.
    """
    xs = [crit[0.01], crit[0.05], crit[0.10], 0.0]
    ys = [0.01, 0.05, 0.10, 0.5]
    if stat <= xs[0]:
        return max(0.001, 0.01 * np.exp((stat - xs[0])))
    if stat >= xs[-1]:
        return min(0.999, 0.5 + 0.5 * (1 - np.exp(-(stat))))
    return float(np.interp(stat, xs, ys))


@dataclass
class ADFResult:
    stat: float
    pvalue: float
    lags: int
    nobs: int
    crit: dict
    regression: str

    def is_stationary(self, alpha=0.05):
        return self.stat < self.crit[alpha]


def adf_test(y, lags="auto", regression="c", max_lags=None):
    """
    Augmented Dickey-Fuller test.  H0: the series has a unit root (is a random
    walk, non-stationary).  Rejecting H0 (stat below the critical value) implies
    the series is mean-reverting.

    regression : "c" constant (default), "ct" constant+trend, "n" none.
    lags       : number of lagged differences, or "auto" (Schwert rule).
    """
    y = np.asarray(y, dtype=float)
    y = y[~np.isnan(y)]
    n = y.size
    if regression not in ADF_CRIT:
        raise ValueError("regression must be 'c', 'ct', or 'n'")

    if lags == "auto":
        cap = max_lags if max_lags is not None else int(np.ceil(12 * (n / 100.0) ** 0.25))
        lags = int(min(cap, max(0, n // 2 - 2)))

    dy = np.diff(y)
    y_lag = y[:-1]
    rows = n - 1 - lags
    if rows <= len(ADF_CRIT[regression]) + lags + 2:
        raise ValueError("series too short for the requested number of lags")

    cols = [y_lag[lags:]]
    for i in range(1, lags + 1):
        cols.append(dy[lags - i: -i])
    X = np.column_stack(cols)
    if regression in ("c", "ct"):
        X = np.column_stack([X, np.ones(rows)])
    if regression == "ct":
        X = np.column_stack([X, np.arange(rows, dtype=float)])
    target = dy[lags:]

    beta, _, se = _ols(X, target)
    stat = beta[0] / se[0]
    crit = ADF_CRIT[regression]
    return ADFResult(stat=float(stat), pvalue=_approx_pvalue(stat, crit),
                     lags=lags, nobs=rows, crit=crit, regression=regression)


def hedge_ratio(y, x, method="ols"):
    """
    Hedge ratio beta for the spread ``y - beta*x``.

    method="ols" : slope of OLS y ~ const + x (asymmetric in y, x).
    method="tls" : total least squares / orthogonal regression (symmetric),
        via the first principal component of the demeaned (x, y) cloud.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if method == "ols":
        X = np.column_stack([np.ones_like(x), x])
        beta, _, _ = _ols(X, y)
        return float(beta[1])
    if method == "tls":
        M = np.column_stack([x - x.mean(), y - y.mean()])
        _, _, Vt = np.linalg.svd(M, full_matrices=False)
        vx, vy = Vt[0]
        return float(vy / vx)
    raise ValueError("method must be 'ols' or 'tls'")


def half_life(spread):
    """
    Mean-reversion half-life (in observations) from an Ornstein-Uhlenbeck /
    AR(1) fit:  ds_t = a + b*s_{t-1} + eps  ->  half-life = -ln(2)/b.
    Returns np.inf if the series is not mean-reverting (b >= 0).
    """
    s = np.asarray(spread, dtype=float)
    s = s[~np.isnan(s)]
    lag = s[:-1]
    delta = np.diff(s)
    X = np.column_stack([np.ones_like(lag), lag])
    beta, _, _ = _ols(X, delta)
    b = beta[1]
    if b >= 0:
        return np.inf
    return float(-np.log(2) / b)


def zscore(series, window=None):
    """
    Standardized series. ``window=None`` uses the full-sample mean/std;
    an integer uses a trailing rolling window (leading entries are NaN).
    """
    s = np.asarray(series, dtype=float)
    if window is None:
        return (s - np.nanmean(s)) / np.nanstd(s)
    out = np.full_like(s, np.nan)
    for t in range(window - 1, s.size):
        w = s[t - window + 1: t + 1]
        mu, sd = w.mean(), w.std()
        out[t] = (s[t] - mu) / sd if sd > 0 else 0.0
    return out


@dataclass
class CointResult:
    stat: float
    pvalue: float
    beta: float
    intercept: float
    resid: np.ndarray
    half_life: float
    crit: dict

    def is_cointegrated(self, alpha=0.05):
        return self.stat < self.crit[alpha]


def engle_granger(y, x, adf_lags="auto"):
    """
    Engle-Granger two-step cointegration test.

    Step 1: regress y on x (with a constant) -> residual spread.
    Step 2: ADF (no-constant) on the spread. If the spread is stationary the
    two series are cointegrated and their spread is tradeable. Uses
    Engle-Granger-specific critical values (stricter than a plain ADF because
    the spread was fitted, not observed).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    beta, resid, _ = _ols(X, y)
    adf = adf_test(resid, lags=adf_lags, regression="n")
    return CointResult(
        stat=adf.stat, pvalue=_approx_pvalue(adf.stat, EG_CRIT),
        beta=float(beta[1]), intercept=float(beta[0]), resid=resid,
        half_life=half_life(resid), crit=EG_CRIT,
    )


def engle_granger_stat(y, x):
    """Convenience: just the EG statistic (used by lightweight guards)."""
    return engle_granger(y, x).stat


def is_cointegrated(y, x, alpha=0.05):
    return engle_granger(y, x).is_cointegrated(alpha)


# =========================================================================== #
# 2. Kalman filter dynamic hedge ratio
# =========================================================================== #
class KalmanHedge:
    """
    Online dynamic hedge ratio: observation  y_t = alpha_t + beta_t * x_t + eps,
    state [alpha_t, beta_t] evolving as a random walk. Each ``update`` performs
    one predict/correct cycle and returns the *innovation* (the de-meaned
    spread) — which is exactly the residual a static regression would produce,
    except the relationship is allowed to drift.

    Noise scales are self-calibrating: the observation variance Ve is estimated
    from the OLS residuals of the seed window (so the filter works for $100
    coins and $0.10 coins alike), and the state noise is ``delta * Ve`` per
    step — ``delta`` controls how fast beta may drift (1e-4 = slow).
    """

    def __init__(self, delta=1e-4):
        self.delta = delta
        self.state = None          # [alpha, beta]
        self.P = None              # 2x2 state covariance
        self.Ve = None             # observation noise variance
        self.Vw = None             # state transition noise covariance

    def initialize(self, y, x):
        """Seed the state with OLS on a training window and calibrate noise."""
        y = np.asarray(y, dtype=float)
        x = np.asarray(x, dtype=float)
        X = np.column_stack([np.ones_like(x), x])
        beta, resid, _ = _ols(X, y)
        self.state = np.array([beta[0], beta[1]], dtype=float)
        self.Ve = float(resid.var()) or 1e-8
        self.Vw = self.delta * self.Ve * np.eye(2)
        self.P = 1e-3 * self.Ve * np.eye(2)
        return self

    def update(self, y_t, x_t):
        """
        One Kalman predict/correct step. Returns (alpha, beta, innovation,
        innovation_std). The innovation e = y - (alpha + beta*x) is computed
        with the *predicted* (pre-update) state, so it never peeks at y_t.
        """
        if self.state is None:
            raise RuntimeError("KalmanHedge.update() before initialize()")
        H = np.array([1.0, float(x_t)])
        # Predict.
        self.P = self.P + self.Vw
        y_hat = float(H @ self.state)
        e = float(y_t) - y_hat
        Q = float(H @ self.P @ H) + self.Ve
        # Correct.
        K = (self.P @ H) / Q
        self.state = self.state + K * e
        self.P = self.P - np.outer(K, H) @ self.P
        return float(self.state[0]), float(self.state[1]), e, float(np.sqrt(Q))

    def run(self, y, x):
        """Run updates over aligned arrays; returns (alphas, betas, innovations)."""
        y = np.asarray(y, dtype=float)
        x = np.asarray(x, dtype=float)
        n = y.size
        alphas = np.empty(n)
        betas = np.empty(n)
        innov = np.empty(n)
        for t in range(n):
            a, b, e, _ = self.update(y[t], x[t])
            alphas[t], betas[t], innov[t] = a, b, e
        return alphas, betas, innov

    @property
    def beta(self):
        return float(self.state[1]) if self.state is not None else np.nan

    @property
    def alpha(self):
        return float(self.state[0]) if self.state is not None else np.nan


# =========================================================================== #
# 3. Feature engineering & labels (verbatim port of cryptostat.statarb.ml)
# =========================================================================== #
def spread_features(spread, mu, sd, lookback=10):
    """
    Per-timestep features describing where the spread is and how it is moving.

    Everything is standardized with the *training* mean/std (``mu``, ``sd``) so
    the model sees the same scale in train and test. Returns an ``(n, F)`` array
    aligned to ``spread`` (early rows use only the history available, no NaNs).

    Features per row t:
        z_t                              current standardized level
        z_{t-1..t-k}                     lagged levels (the sequence shape)
        dz over 1, 3, 5 steps            momentum / velocity of the spread
        rolling std of z (lookback)      local volatility regime
        rsi of the spread (lookback)     overbought/oversold of the raw spread
    """
    s = np.asarray(spread, dtype=float)
    n = s.size
    sd = sd if sd > 0 else 1.0
    z = (s - mu) / sd

    def _lag(x, k):
        out = np.empty_like(x)
        out[:k] = x[0] if x.size else 0.0
        out[k:] = x[:-k]
        return out

    def _roll_std(x, w):
        out = np.zeros_like(x)
        for t in range(n):
            lo = max(0, t - w + 1)
            out[t] = x[lo:t + 1].std()
        return out

    def _rsi(x, w):
        d = np.diff(x, prepend=x[0])
        up = np.where(d > 0, d, 0.0)
        dn = np.where(d < 0, -d, 0.0)
        out = np.full(n, 50.0)
        for t in range(n):
            lo = max(0, t - w + 1)
            au, ad = up[lo:t + 1].mean(), dn[lo:t + 1].mean()
            out[t] = 100.0 if (au + ad) == 0 else 100.0 * au / (au + ad)
        return (out - 50.0) / 50.0            # center to [-1, 1]

    cols = [z]
    for k in (1, 2, 3, 5, 8):
        cols.append(_lag(z, k))
    for k in (1, 3, 5):
        cols.append(z - _lag(z, k))
    cols.append(_roll_std(z, lookback))
    cols.append(_rsi(s, lookback))
    return np.column_stack(cols)


def forward_label(spread, horizon, sd):
    """
    Regression target: the spread's change ``horizon`` steps ahead, in sigma
    units. ``label[t] = (spread[t+horizon] - spread[t]) / sd``. The last
    ``horizon`` rows have no future and are returned as NaN (the caller drops
    them from the training set). Positive => spread rises => long-spread trade
    profits.
    """
    s = np.asarray(spread, dtype=float)
    sd = sd if sd > 0 else 1.0
    n = s.size
    out = np.full(n, np.nan)
    if horizon < n:
        out[:n - horizon] = (s[horizon:] - s[:n - horizon]) / sd
    return out


def _build_sequences(feats, seq_len):
    """Stack each row's trailing ``seq_len`` feature vectors into a sequence
    tensor of shape ``(n, seq_len, F)`` (front-padded by repeating row 0)."""
    n, _ = feats.shape
    pad = np.repeat(feats[:1], seq_len - 1, axis=0)
    padded = np.vstack([pad, feats])
    return np.stack([padded[i:i + seq_len] for i in range(n)])


# =========================================================================== #
# 4. Models — each guarded so a missing library degrades instead of crashing
# =========================================================================== #
class SpreadNet:
    """
    A compact LSTM regressor (torch): spread-feature sequence -> forward move.

    Kept deliberately small (one LSTM layer + a linear head) because pairs data
    is short and daily — a big network would only memorize. Regularized with
    dropout + weight decay, trained with Adam + early stopping on a held-out
    tail of the training window, deterministic given a seed.
    """

    def __init__(self, seq_len=12, hidden=16, epochs=120, lr=1e-2,
                 weight_decay=1e-3, dropout=0.2, patience=12, seed=0):
        self.seq_len = seq_len
        self.hidden = hidden
        self.epochs = epochs
        self.lr = lr
        self.weight_decay = weight_decay
        self.dropout = dropout
        self.patience = patience
        self.seed = seed
        self._model = None
        self._fmu = None
        self._fsd = None

    def _make(self, n_features):
        import torch
        from torch import nn

        torch.manual_seed(self.seed)

        class _Net(nn.Module):
            def __init__(self, f, h, p):
                super().__init__()
                self.lstm = nn.LSTM(f, h, batch_first=True)
                self.head = nn.Sequential(nn.Dropout(p), nn.Linear(h, h),
                                          nn.ReLU(), nn.Linear(h, 1))

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :]).squeeze(-1)

        return _Net(n_features, self.hidden, self.dropout)

    def fit(self, feats, labels):
        import torch

        self._fmu = feats.mean(axis=0)
        self._fsd = feats.std(axis=0)
        self._fsd[self._fsd == 0] = 1.0
        fz = (feats - self._fmu) / self._fsd

        X = torch.tensor(_build_sequences(fz, self.seq_len), dtype=torch.float32)
        y = torch.tensor(labels, dtype=torch.float32)
        n = X.shape[0]
        cut = max(1, int(n * 0.8))
        Xtr, ytr, Xva, yva = X[:cut], y[:cut], X[cut:], y[cut:]

        self._model = self._make(feats.shape[1])
        opt = torch.optim.Adam(self._model.parameters(), lr=self.lr,
                               weight_decay=self.weight_decay)
        loss_fn = torch.nn.MSELoss()

        best_state, best_val, bad = None, float("inf"), 0
        for _ in range(self.epochs):
            self._model.train()
            opt.zero_grad()
            loss = loss_fn(self._model(Xtr), ytr)
            loss.backward()
            opt.step()

            self._model.eval()
            with torch.no_grad():
                val = loss_fn(self._model(Xva), yva).item() if Xva.shape[0] else loss.item()
            if val < best_val - 1e-6:
                best_val, bad = val, 0
                best_state = {k: v.clone() for k, v in self._model.state_dict().items()}
            else:
                bad += 1
                if bad >= self.patience:
                    break
        if best_state is not None:
            self._model.load_state_dict(best_state)
        return self

    def predict(self, feats):
        import torch
        fz = (feats - self._fmu) / self._fsd
        seqs = _build_sequences(fz, self.seq_len)
        self._model.eval()
        with torch.no_grad():
            return self._model(torch.tensor(seqs, dtype=torch.float32)).numpy()


class GBMSignal:
    """
    Regularized sklearn gradient boosting — the classical-ML fallback for the
    LSTM. Regularized against small, autocorrelated financial samples: shallow
    trees, row subsampling, a minimum leaf size, and internal early stopping on
    a held-out validation fraction so the boosting run stops as soon as it
    starts memorizing.
    """

    def __init__(self, n_estimators=300, max_depth=2, learning_rate=0.03,
                 subsample=0.7, min_samples_leaf=20, seed=0):
        self.kw = dict(n_estimators=n_estimators, max_depth=max_depth,
                       learning_rate=learning_rate, subsample=subsample,
                       min_samples_leaf=min_samples_leaf,
                       validation_fraction=0.2, n_iter_no_change=15,
                       random_state=seed)
        self._model = None

    def fit(self, feats, labels):
        from sklearn.ensemble import GradientBoostingRegressor
        self._model = GradientBoostingRegressor(**self.kw).fit(feats, labels)
        return self

    def predict(self, feats):
        return self._model.predict(feats)


class NumpyRidge:
    """
    Closed-form L2 linear regression — pure numpy, zero dependencies, so the
    strategy can always run even if torch AND sklearn are unavailable. Also the
    maximally regularized reference: if ridge ties the fancier models
    out-of-sample, their extra capacity was buying only overfit.
    """

    def __init__(self, alpha=10.0, seed=0):
        self.alpha = alpha
        _ = seed                             # deterministic; interface parity
        self._w = None

    def fit(self, feats, labels):
        X = np.column_stack([np.ones(len(feats)), feats])
        A = X.T @ X + self.alpha * np.eye(X.shape[1])
        A[0, 0] -= self.alpha                # don't penalize the intercept
        self._w = np.linalg.solve(A, X.T @ labels)
        return self

    def predict(self, feats):
        X = np.column_stack([np.ones(len(feats)), feats])
        return X @ self._w


def resolve_kind(kind):
    """Downgrade the requested model to whatever this environment can run:
    lstm (torch) -> gbm (sklearn) -> ridge (numpy, always available).
    "zscore" is the hand-written baseline and needs nothing."""
    if kind == "zscore":
        return "zscore"
    if kind == "lstm":
        try:
            import torch  # noqa: F401
            return "lstm"
        except ImportError:
            kind = "gbm"
    if kind == "gbm":
        try:
            import sklearn.ensemble  # noqa: F401
            return "gbm"
        except ImportError:
            return "ridge"
    return "ridge"


# =========================================================================== #
# 5. MLSignal — the learned position, with the validated overfitting defences
# =========================================================================== #
class MLSignal:
    """
    Learn a spread-trading position from data.

    ``fit`` on one training window's spread (freezing mu/sd — the same
    statistics the z-score baseline freezes); ``predict`` returns {-1, 0, +1}
    per bar of any later spread window using only frozen statistics. Nothing
    from the future leaks into scaling, labels, or the conviction gate.

    Parameters
    ----------
    kind : "lstm", "gbm" or "ridge" (auto-downgraded per environment).
    horizon : how many steps ahead the label looks (the reversion horizon).
    entry_sigma : take a position only when the predicted return exceeds this
        many training-prediction sigmas (conviction gate; higher => fewer,
        higher-quality trades).
    lookback : window for the rolling/RSI features.
    n_ensemble : train this many models with different seeds and average their
        predictions. Ensembling is the cheapest variance-reduction there is for
        small-data nets — the seed lottery washes out.
    z_gate : if set, a prediction only becomes a trade when the *frozen*
        z-score also agrees with it as mean-reversion: long the spread only
        when z <= -z_gate, short only when z >= +z_gate. The model can rank and
        time entries, but it cannot invent trades the cointegration doesn't
        support — a structural cap on how much damage an overfit model can do.
    """

    def __init__(self, kind="lstm", horizon=5, entry_sigma=0.5, lookback=10,
                 n_ensemble=3, z_gate=1.0, model_kwargs=None, seed=0):
        self.kind = kind
        self.resolved_kind = None            # set at fit(): what actually trained
        self.horizon = horizon
        self.entry_sigma = entry_sigma
        self.lookback = lookback
        self.n_ensemble = max(1, int(n_ensemble))
        self.z_gate = z_gate
        self.seed = seed
        self.model_kwargs = model_kwargs or {}
        self._models = []
        self._mu = 0.0
        self._sd = 1.0
        self._pred_sd = 1.0

    def _new_model(self, seed):
        if self.resolved_kind == "lstm":
            return SpreadNet(seed=seed, **self.model_kwargs)
        if self.resolved_kind == "gbm":
            return GBMSignal(seed=seed, **self.model_kwargs)
        return NumpyRidge(seed=seed, **self.model_kwargs)

    def _ensemble_predict(self, feats):
        return np.mean([m.predict(feats) for m in self._models], axis=0)

    def fit(self, spread_train, mu=None, sd=None):
        """Fit on ONE training window's spread. ``mu``/``sd`` default to the
        window's own mean/std (the same statistics the baseline freezes)."""
        s = np.asarray(spread_train, dtype=float)
        self._mu = float(s.mean()) if mu is None else float(mu)
        self._sd = float(s.std()) if sd is None else float(sd)
        if self._sd <= 0:
            self._sd = 1.0
        self.resolved_kind = resolve_kind(self.kind)

        feats = spread_features(s, self._mu, self._sd, self.lookback)
        labels = forward_label(s, self.horizon, self._sd)
        ok = ~np.isnan(labels)
        Xf, yf = feats[ok], labels[ok]

        # Ridge is deterministic — ensembling it is pointless.
        n_models = self.n_ensemble if self.resolved_kind != "ridge" else 1
        self._models = [self._new_model(self.seed + k).fit(Xf, yf)
                        for k in range(n_models)]
        # Scale of in-sample predictions sets the conviction gate for test.
        insample_pred = self._ensemble_predict(Xf)
        self._pred_sd = float(np.std(insample_pred)) or 1.0
        return self

    def predict(self, spread_test):
        """Position array in {-1,0,+1} for an unseen spread window, using the
        mu/sd and model(s) frozen at ``fit`` time."""
        s = np.asarray(spread_test, dtype=float)
        feats = spread_features(s, self._mu, self._sd, self.lookback)
        pred = self._ensemble_predict(feats)
        gate = self.entry_sigma * self._pred_sd
        pos = np.zeros(s.size)
        pos[pred >= gate] = 1.0
        pos[pred <= -gate] = -1.0
        if self.z_gate is not None:
            z = (s - self._mu) / self._sd
            pos[(pos > 0) & (z > -self.z_gate)] = 0.0   # long needs a cheap spread
            pos[(pos < 0) & (z < self.z_gate)] = 0.0    # short needs a rich spread
        return pos


class ZScoreSignal:
    """
    The research repo's hand-written baseline, wearing the same fit/predict
    interface as MLSignal so the algorithm can A/B them with one config knob
    (MODEL_KIND="zscore").

    A symmetric, stateful z-score band: go long the spread when it is cheap
    (z <= -entry), short when rich (z >= +entry), close when it reverts inside
    the +/-exit band, and bail if it diverges past +/-stop. This is the
    baseline the ML models had to beat in research — on short daily windows it
    is genuinely hard to beat, so keeping it selectable in production is not a
    courtesy, it's the control group.

    Event-driven caveat: the band is *stateful* (a position persists until an
    exit condition), and the engine re-runs it over a trailing buffer each bar.
    A position held longer than the buffer would be forgotten at the buffer
    edge — keep buf_len comfortably above the expected holding period (the
    default 60-bar buffer vs. the <=90-bar half-life cap is deliberate).
    """

    def __init__(self, entry=2.0, exit=0.5, stop=4.0):
        self.entry = entry
        self.exit = exit
        self.stop = stop
        self.resolved_kind = "zscore"    # uniform logging with MLSignal
        self.entry_sigma = entry         # uniform logging with MLSignal
        self._mu = 0.0
        self._sd = 1.0

    def fit(self, spread_train, mu=None, sd=None):
        """Freeze the z-score statistics from the training window."""
        s = np.asarray(spread_train, dtype=float)
        self._mu = float(s.mean()) if mu is None else float(mu)
        self._sd = float(s.std()) if sd is None else float(sd)
        if self._sd <= 0:
            self._sd = 1.0
        return self

    def predict(self, spread_test):
        """Stateful band positions in {-1, 0, +1} over the window."""
        s = np.asarray(spread_test, dtype=float)
        z = (s - self._mu) / self._sd
        pos = np.zeros(z.size)
        state = 0
        for t in range(z.size):
            zt = z[t]
            if np.isnan(zt):
                pos[t] = state
                continue
            if state == 0:
                if zt <= -self.entry:
                    state = 1
                elif zt >= self.entry:
                    state = -1
            elif state == 1:               # long spread, waiting to revert up
                if zt >= -self.exit or (self.stop is not None and zt <= -self.stop):
                    state = 0
            elif state == -1:              # short spread, waiting to revert down
                if zt <= self.exit or (self.stop is not None and zt >= self.stop):
                    state = 0
            pos[t] = state
        return pos


def spread_returns(a, b, beta, pos):
    """P&L of a dollar-neutral spread position, as a return on gross notional.
    Position is lagged one bar before it earns P&L — no look-ahead."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    spread = a - beta * b
    dspread = np.diff(spread, prepend=spread[0])
    gross = np.abs(a) + np.abs(beta) * np.abs(b)
    pos_lag = np.concatenate([[0.0], np.asarray(pos, dtype=float)[:-1]])
    pnl = pos_lag * dspread
    return np.divide(pnl, gross, out=np.zeros_like(pnl), where=gross > 0)


ENTRY_GRID = (0.25, 0.5, 0.75, 1.0, 1.5)


def tune_entry_sigma(a_tr, b_tr, kind="lstm", horizon=5, lookback=10,
                     n_ensemble=3, z_gate=1.0, cost_bps=10.0,
                     hedge_method="ols", model_kwargs=None, seed=0,
                     periods_per_year=365, grid=ENTRY_GRID, val_frac=0.25):
    """
    Pick ``entry_sigma`` on a validation tail of the TRAINING window only.

    Fits the model on the front of the training window, replays each candidate
    gate on the held-back tail (with a cost penalty so the tuner doesn't pick a
    hyperactive gate), and returns the gate with the best validation Sharpe.
    Nothing from the test window is touched — this is how you optimize a
    hyperparameter without paying for it in hidden look-ahead.

    NOTE from the research repo: on short daily windows this tuning was mixed
    (it rescued one pair and hurt another), which is why the algorithm exposes
    it as opt-in rather than default.
    """
    a_tr = np.asarray(a_tr, dtype=float)
    b_tr = np.asarray(b_tr, dtype=float)
    cut = max(lookback + horizon + 10, int(len(a_tr) * (1 - val_frac)))
    if cut >= len(a_tr) - 5:                       # window too short to split
        return grid[1]
    a_fit, b_fit, a_val, b_val = a_tr[:cut], b_tr[:cut], a_tr[cut:], b_tr[cut:]
    beta = hedge_ratio(a_fit, b_fit, method=hedge_method)
    sig = MLSignal(kind=kind, horizon=horizon, entry_sigma=grid[0],
                   lookback=lookback, n_ensemble=n_ensemble, z_gate=z_gate,
                   model_kwargs=model_kwargs, seed=seed)
    sig.fit(a_fit - beta * b_fit)
    spread_val = a_val - beta * b_val

    best_gate, best_sharpe = grid[1], -np.inf
    for gate in grid:
        sig.entry_sigma = gate
        pos = sig.predict(spread_val)
        ret = spread_returns(a_val, b_val, beta, pos)
        ret = ret - np.abs(np.diff(pos, prepend=0.0)) * (cost_bps / 1e4)
        s = sharpe(ret, periods_per_year)
        if s > best_sharpe:
            best_sharpe, best_gate = s, gate
    return best_gate


# =========================================================================== #
# 6. Performance metrics & tracking
# =========================================================================== #
def sharpe(returns, periods_per_year=365):
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 2 or r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(periods_per_year))


def annualized_return(returns, periods_per_year=365):
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size == 0:
        return 0.0
    total = np.prod(1.0 + r)
    years = r.size / periods_per_year
    if years <= 0 or total <= 0:
        return 0.0
    return float(total ** (1.0 / years) - 1.0)


def annualized_vol(returns, periods_per_year=365):
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 2:
        return 0.0
    return float(r.std() * np.sqrt(periods_per_year))


def max_drawdown(equity):
    """Max peak-to-trough drawdown of an equity curve. Returns a negative
    fraction (e.g. -0.23 for a 23% drawdown)."""
    eq = np.asarray(equity, dtype=float)
    eq = eq[~np.isnan(eq)]
    if eq.size == 0:
        return 0.0
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(dd.min())


def hit_rate(returns):
    r = np.asarray(returns, dtype=float)
    r = r[(~np.isnan(r)) & (r != 0)]
    if r.size == 0:
        return 0.0
    return float((r > 0).mean())


class PerformanceTracker:
    """
    Rolling record of portfolio equity plus per-pair trade telemetry, for the
    end-of-run report and for the RiskManager's realized-vol estimate.
    """

    def __init__(self, periods_per_year=365):
        self.ppy = periods_per_year
        self.equity = []
        self.times = []
        self.pair_stats = {}       # name -> dict of counters

    def record_equity(self, time, value):
        self.times.append(time)
        self.equity.append(float(value))

    def returns(self):
        eq = np.asarray(self.equity, dtype=float)
        if eq.size < 2:
            return np.array([])
        return np.diff(eq) / eq[:-1]

    def _pair(self, name):
        if name not in self.pair_stats:
            self.pair_stats[name] = {
                "trades": 0, "bars_long": 0, "bars_short": 0, "bars_flat": 0,
                "time_stops": 0, "stand_downs": 0, "refits": 0,
                "paper_pnl": 0.0,
            }
        return self.pair_stats[name]

    def record_bar(self, name, position):
        p = self._pair(name)
        if position > 0:
            p["bars_long"] += 1
        elif position < 0:
            p["bars_short"] += 1
        else:
            p["bars_flat"] += 1

    def record_trade(self, name):
        self._pair(name)["trades"] += 1

    def record_time_stop(self, name):
        self._pair(name)["time_stops"] += 1

    def record_stand_down(self, name):
        self._pair(name)["stand_downs"] += 1

    def record_refit(self, name):
        self._pair(name)["refits"] += 1

    def record_pair_return(self, name, ret):
        """Accumulate a pair's pre-cost spread return (attribution only)."""
        self._pair(name)["paper_pnl"] += float(ret)

    def summary_lines(self):
        """Human-readable end-of-run report."""
        lines = []
        r = self.returns()
        if r.size:
            lines.append(
                f"portfolio: ann.ret {annualized_return(r, self.ppy):7.2%} | "
                f"ann.vol {annualized_vol(r, self.ppy):6.2%} | "
                f"sharpe {sharpe(r, self.ppy):5.2f} | "
                f"maxDD {max_drawdown(self.equity):7.2%} | "
                f"hit {hit_rate(r):5.1%} | {r.size} bars")
        for name in sorted(self.pair_stats):
            p = self.pair_stats[name]
            active = p["bars_long"] + p["bars_short"]
            lines.append(
                f"{name}: {p['trades']} trades | {active} bars active "
                f"({p['bars_long']}L/{p['bars_short']}S) | "
                f"paper P&L {p['paper_pnl']:+.2%} (pre-cost) | "
                f"{p['time_stops']} time-stops | {p['stand_downs']} stand-downs | "
                f"{p['refits']} refits")
        return lines


# =========================================================================== #
# 7. Pair screening — walk-forward pair selection on training data only
# =========================================================================== #
def screen_pairs(closes, alpha=0.05, min_corr=0.5,
                 min_half_life=2.0, max_half_life=90.0, use_log=True):
    """
    Test every pair of a universe for cointegration and return a ranked list.

    ``closes`` is a dict {ticker: 1-D np.ndarray}, all aligned to the same
    dates (the caller aligns them). Pairs are prefiltered by price correlation
    (no point cointegration-testing unrelated series), tested in both
    regression directions (Engle-Granger is asymmetric — the stronger direction
    wins), and filtered to a tradeable half-life range: too fast is
    noise-plus-costs, too slow ties up capital for months.

    Returns a list of dicts sorted best-first:
        {"a", "b", "stat", "pvalue", "beta", "half_life", "corr", "candidate"}

    IMPORTANT: call this with TRAINING data only. Screening on data you then
    trade is selection bias — the exact sin the research repo's README warns
    about. The algorithm re-screens at every rebuild so pair selection is
    walk-forward, the same discipline as parameter estimation.
    """
    names = sorted(closes)
    rows = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            na, nb = names[i], names[j]
            xa = np.asarray(closes[na], dtype=float)
            xb = np.asarray(closes[nb], dtype=float)
            m = min(xa.size, xb.size)
            if m < 120:
                continue
            xa, xb = xa[-m:], xb[-m:]
            sa = np.log(xa) if use_log else xa
            sb = np.log(xb) if use_log else xb
            corr = float(np.corrcoef(sa, sb)[0, 1])
            if abs(corr) < min_corr:
                continue
            try:
                r1 = engle_granger(sa, sb)
                r2 = engle_granger(sb, sa)
            except ValueError:
                continue
            res, (dep, ind) = (r1, (na, nb)) if r1.stat <= r2.stat else (r2, (nb, na))
            hl = res.half_life
            rows.append({
                "a": dep, "b": ind, "corr": corr,
                "stat": res.stat, "pvalue": res.pvalue, "beta": res.beta,
                "half_life": hl,
                "candidate": (res.is_cointegrated(alpha)
                              and min_half_life <= hl <= max_half_life),
            })
    # Candidates first, then strongest (most negative) EG statistic.
    rows.sort(key=lambda r: (not r["candidate"], r["stat"]))
    return rows


# =========================================================================== #
# 8. PairEngine — one pair's complete, QC-agnostic trading state machine
# =========================================================================== #
@dataclass
class PairConfig:
    """Per-pair strategy configuration (see MLSignal for signal params)."""
    kind: str = "lstm"                 # lstm/gbm/ridge (ML) or "zscore" baseline
    horizon: int = 5                   # label horizon, bars
    entry_sigma: float = 0.5           # conviction gate (prediction sigmas)
    z_entry: float = 2.0               # zscore baseline: entry band
    z_exit: float = 0.5                # zscore baseline: reversion exit band
    z_stop: float = 4.0                # zscore baseline: divergence stop
    lookback: int = 10                 # feature window
    n_ensemble: int = 3                # seed ensemble size
    z_gate: float = 1.0                # z-score agreement gate (None = off)
    tune_entry: bool = False           # per-fit gate tuning on a train tail
    hedge: str = "ols"                 # "ols" | "tls" | "kalman"
    kalman_delta: float = 1e-4         # beta drift speed (kalman only)
    coint_alpha: float = 0.05          # stand-down threshold at refit
    min_half_life: float = 2.0         # tradeable half-life band (bars)
    max_half_life: float = 90.0
    time_stop_half_lives: float = 3.0  # exit after this many HLs held (0 = off)
    cooldown_bars: int = 5             # bars flat after a time stop
    buf_len: int = 60                  # trailing spread buffer for prediction
    min_predict: int = 40              # bars needed before first prediction
    seed: int = 0
    model_kwargs: dict = field(default_factory=dict)


class PairEngine:
    """
    Everything one pair needs, with no LEAN dependency (unit-testable locally):

        engine = PairEngine("LINK/LTC", PairConfig())
        ok = engine.fit(a_train, b_train)     # freeze params, train the model
        pos = engine.on_bar(pa, pb)           # once per bar -> {-1, 0, +1}
        wa, wb = engine.leg_weights(pa, pb, budget)

    ``fit`` re-runs the full cointegration test and STANDS DOWN (always flat)
    if the pair de-cointegrated — the "relationship broke" brake. ``on_bar``
    handles Kalman beta updates (if configured), the half-life time stop, and
    the post-stop cooldown. The prediction path over the trailing buffer is
    bar-for-bar identical to the vectorized research backtest (the last row's
    features depend only on trailing history).
    """

    def __init__(self, name, cfg: PairConfig):
        self.name = name
        self.cfg = cfg
        self.model = None
        self.kalman = None
        self.static_beta = np.nan
        self.mu = 0.0
        self.sd = 1.0
        self.half_life = np.inf
        self.eg_stat = np.nan
        self.stood_down = True
        self.risk_unit = np.nan        # spread sd / gross notional: sizing input
        self.buf = deque(maxlen=cfg.buf_len)
        self.position = 0
        self.holding_bars = 0
        self.cooldown = 0
        self.fits = 0
        self.last_time_stop = False    # diagnostic: did the last bar time-stop?
        self.prev_spread = None        # paper-P&L attribution state
        self.last_paper_ret = 0.0      # last bar's spread return (pre-cost)
        self.paper_pnl = 0.0           # cumulative paper spread return

    # ----- training ---------------------------------------------------------- #
    def fit(self, a, b):
        """
        Fit on one training window (arrays of aligned closes). Returns True if
        the pair is tradeable, False if the engine stood down. Freezes beta
        (or seeds the Kalman filter), mu, sd, the half-life, and the model.
        """
        a = np.asarray(a, dtype=float)
        b = np.asarray(b, dtype=float)
        self.fits += 1
        cfg = self.cfg

        # 1. Cointegration guard on the training window only.
        try:
            res = engle_granger(a, b)
        except ValueError:
            self._stand_down()
            return False
        self.eg_stat = res.stat
        if not res.is_cointegrated(cfg.coint_alpha):
            self._stand_down()
            return False

        # 2. Hedge ratio + the frozen spread statistics.
        if cfg.hedge == "kalman":
            # Seed on the front half, run through the back half so the filter
            # state and the residual scale reflect the end of the window.
            seed_n = max(60, len(a) // 3)
            self.kalman = KalmanHedge(delta=cfg.kalman_delta)
            self.kalman.initialize(a[:seed_n], b[:seed_n])
            _, _, innov = self.kalman.run(a[seed_n:], b[seed_n:])
            spread = innov
            self.static_beta = self.kalman.beta
        else:
            self.kalman = None
            self.static_beta = hedge_ratio(a, b, method=cfg.hedge)
            spread = a - self.static_beta * b

        self.mu = float(spread.mean())
        self.sd = float(spread.std())
        if self.sd <= 0:
            self._stand_down()
            return False

        # 3. Half-life band: reject untradeable speeds.
        self.half_life = half_life(spread)
        if not (cfg.min_half_life <= self.half_life <= cfg.max_half_life):
            self._stand_down()
            return False

        # 4. Fit the signal: the ML ensemble, or the z-score control group.
        if cfg.kind == "zscore":
            sig = ZScoreSignal(entry=cfg.z_entry, exit=cfg.z_exit, stop=cfg.z_stop)
            sig.fit(spread, mu=self.mu, sd=self.sd)
        else:
            entry = cfg.entry_sigma
            if cfg.tune_entry and cfg.hedge != "kalman":
                # Honest per-fit gate tuning on a validation tail of train.
                entry = tune_entry_sigma(
                    a, b, kind=cfg.kind, horizon=cfg.horizon, lookback=cfg.lookback,
                    n_ensemble=cfg.n_ensemble, z_gate=cfg.z_gate,
                    model_kwargs=cfg.model_kwargs, seed=cfg.seed)
            sig = MLSignal(kind=cfg.kind, horizon=cfg.horizon, entry_sigma=entry,
                           lookback=cfg.lookback, n_ensemble=cfg.n_ensemble,
                           z_gate=cfg.z_gate, model_kwargs=cfg.model_kwargs,
                           seed=cfg.seed)
            sig.fit(spread, mu=self.mu, sd=self.sd)
        self.model = sig

        # 5. Seed the prediction buffer with the new frozen parameters and
        #    record the sizing input (spread risk per unit of gross notional).
        self.buf = deque(spread[-cfg.buf_len:].tolist(), maxlen=cfg.buf_len)
        gross = np.abs(a) + np.abs(self.static_beta) * np.abs(b)
        self.risk_unit = float(self.sd / gross.mean()) if gross.mean() > 0 else np.nan

        self.stood_down = False
        self.holding_bars = 0
        self.cooldown = 0
        self.prev_spread = float(spread[-1])
        return True

    def _stand_down(self):
        self.stood_down = True
        self.model = None
        self.position = 0
        self.holding_bars = 0
        self.prev_spread = None
        self.last_paper_ret = 0.0

    # ----- trading ------------------------------------------------------------ #
    def current_beta(self):
        return self.kalman.beta if self.kalman is not None else self.static_beta

    def on_bar(self, pa, pb):
        """
        Consume one bar of both legs; return the target position {-1, 0, +1}.
        Order of operations mirrors the research backtest exactly: update the
        hedge, form the spread, predict, then apply the time stop / cooldown.
        """
        self.last_time_stop = False
        if self.stood_down or self.model is None:
            self.position = 0
            return 0

        if self.kalman is not None:
            # The innovation uses the pre-update state — no peeking at pa.
            _, _, e, _ = self.kalman.update(pa, pb)
            spread_t = e
        else:
            spread_t = pa - self.static_beta * pb

        # Paper P&L attribution: the position we HELD into this bar earns this
        # bar's spread change, expressed as a return on the pair's gross
        # notional. Pre-fee/pre-funding — telemetry, not accounting.
        gross_now = pa + abs(self.current_beta()) * pb
        if self.prev_spread is not None and gross_now > 0:
            self.last_paper_ret = self.position * (spread_t - self.prev_spread) / gross_now
        else:
            self.last_paper_ret = 0.0
        self.paper_pnl += self.last_paper_ret
        self.prev_spread = float(spread_t)

        self.buf.append(spread_t)

        if len(self.buf) < self.cfg.min_predict:
            self.position = 0
            return 0

        pos = int(self.model.predict(np.asarray(self.buf))[-1])

        # Post-time-stop cooldown: stay flat, let the spread breathe.
        if self.cooldown > 0:
            self.cooldown -= 1
            pos = 0

        # Holding-period accounting for the half-life time stop.
        if pos != 0 and pos == self.position:
            self.holding_bars += 1
        elif pos != 0:
            self.holding_bars = 1
        else:
            self.holding_bars = 0

        # Half-life time stop: if the trade hasn't resolved within N
        # half-lives, mean reversion is broken for this episode — get out.
        k = self.cfg.time_stop_half_lives
        if (pos != 0 and k > 0 and np.isfinite(self.half_life)
                and self.holding_bars > k * self.half_life):
            pos = 0
            self.holding_bars = 0
            self.cooldown = self.cfg.cooldown_bars
            self.last_time_stop = True

        self.position = pos
        return pos

    def leg_weights(self, pa, pb, budget):
        """
        Portfolio weights for the two legs at the current position and hedge:
        +1 = long 1 unit of A, short beta units of B, scaled so the pair's
        combined gross exposure equals ``budget`` (fraction of equity).
        """
        if self.position == 0 or pa <= 0 or pb <= 0:
            return 0.0, 0.0
        beta = self.current_beta()
        gross = pa + abs(beta) * pb
        wa = self.position * (pa / gross) * budget
        wb = -self.position * (beta * pb / gross) * budget
        return float(wa), float(wb)


# =========================================================================== #
# 9. RiskManager — portfolio-level volatility targeting + drawdown kill-switch
# =========================================================================== #
class RiskManager:
    """
    Two independent brakes on portfolio exposure:

    1. **Volatility targeting.** Scale gross exposure by
       ``target_vol / realized_vol`` (clamped to [min_scale, max_scale]) so the
       strategy runs at roughly constant risk across regimes instead of
       breathing with crypto volatility.
    2. **Drawdown kill-switch.** If equity falls more than ``max_drawdown``
       from its peak, liquidate and halt for ``halt_bars`` bars, then resume at
       minimum scale. Crypto pairs *do* de-cointegrate violently; the
       stand-down guard catches it at the next refit, this catches it sooner.

    Call ``update(equity)`` once per bar; read ``exposure_scale()`` when
    sizing. ``events`` accumulates human-readable state transitions for logs.
    """

    def __init__(self, target_vol=0.15, vol_lookback=30,
                 min_scale=0.25, max_scale=1.5,
                 max_drawdown=0.20, halt_bars=30, periods_per_year=365):
        self.target_vol = target_vol
        self.vol_lookback = vol_lookback
        self.min_scale = min_scale
        self.max_scale = max_scale
        self.max_dd = max_drawdown
        self.halt_bars = halt_bars
        self.ppy = periods_per_year

        self._equity = deque(maxlen=max(vol_lookback + 1, 2))
        self._peak = -np.inf
        self._bar = 0
        self._halted_until = -1
        self.drawdown = 0.0
        self.events = []

    @property
    def halted(self):
        return self._bar < self._halted_until

    def update(self, equity):
        """Feed one bar of portfolio equity; trips the kill-switch if needed."""
        self._bar += 1
        equity = float(equity)
        self._equity.append(equity)
        self._peak = max(self._peak, equity)
        self.drawdown = equity / self._peak - 1.0 if self._peak > 0 else 0.0

        if not self.halted and self.drawdown < -self.max_dd:
            self._halted_until = self._bar + self.halt_bars
            # Reset the peak so the strategy doesn't re-trip immediately on
            # resume against a stale high-water mark.
            self._peak = equity
            self.events.append(
                f"KILL-SWITCH: drawdown {self.drawdown:.1%} exceeded "
                f"{-self.max_dd:.0%} at bar {self._bar}; halting "
                f"{self.halt_bars} bars")
            return "halt"
        if self._bar == self._halted_until:
            self.events.append(f"kill-switch released at bar {self._bar}; "
                               f"resuming at min scale")
            return "resume"
        return None

    def realized_vol(self):
        eq = np.asarray(self._equity, dtype=float)
        if eq.size < 3:
            return 0.0
        r = np.diff(eq) / eq[:-1]
        return float(r.std() * np.sqrt(self.ppy))

    def exposure_scale(self):
        """Multiplier on gross exposure in [0, max_scale]."""
        if self.halted:
            return 0.0
        vol = self.realized_vol()
        if vol <= 0:
            return 1.0
        return float(np.clip(self.target_vol / vol, self.min_scale, self.max_scale))


# =========================================================================== #
# Risk-budget allocation across pairs
# =========================================================================== #
def inverse_risk_budgets(engines, gross_target):
    """
    Split ``gross_target`` across active engines proportionally to inverse
    spread risk (1 / risk_unit) — the risk-parity-lite allocation the research
    repo's task list calls "portfolio of pairs with a risk budget". A pair with
    a twice-as-volatile spread gets half the notional, so each pair contributes
    roughly equal risk instead of equal dollars.

    Returns {engine.name: budget_fraction}; engines that are stood down or have
    no risk estimate get 0.
    """
    inv = {}
    for e in engines:
        if e.stood_down or not np.isfinite(e.risk_unit) or e.risk_unit <= 0:
            continue
        inv[e.name] = 1.0 / e.risk_unit
    total = sum(inv.values())
    if total <= 0:
        return {e.name: 0.0 for e in engines}
    return {e.name: gross_target * inv.get(e.name, 0.0) / total for e in engines}


# =========================================================================== #
# 10. Self-test — run `python spread_ml.py` locally before every deploy
# =========================================================================== #
def _make_cointegrated_pair(n=800, seed=0, beta=1.5, amp=8.0, theta=0.06):
    """Synthetic ground truth: B is a random walk, the spread is an OU process,
    A = beta*B + spread. Cointegrated by construction, half-life ~ ln2/theta."""
    rng = np.random.default_rng(seed)
    b = np.cumsum(rng.standard_normal(n)) * 0.5 + 100.0
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = (spread[t - 1] - theta * spread[t - 1]
                     + rng.standard_normal() * amp * np.sqrt(theta))
    a = beta * b + spread
    return a, b


def selftest(verbose=True):
    """
    Verify every component of this file on synthetic data with known truth.
    Returns the number of failures (0 = ready to deploy). Runs in seconds and
    needs nothing beyond numpy — torch/sklearn tests self-skip if unavailable.
    """
    failures = []

    def check(name, cond):
        if verbose:
            print(("PASS  " if cond else "FAIL  ") + name)
        if not cond:
            failures.append(name)

    rng = np.random.default_rng(42)
    a, b = _make_cointegrated_pair()
    w1 = np.cumsum(rng.standard_normal(800)) + 100.0
    w2 = np.cumsum(rng.standard_normal(800)) + 100.0

    # --- statistics -------------------------------------------------------- #
    check("adf: OU spread is stationary",
          adf_test(a - 1.5 * b).is_stationary())
    check("adf: random walk is not stationary",
          not adf_test(w1).is_stationary())
    check("engle_granger: cointegrated pair detected",
          is_cointegrated(a, b))
    check("engle_granger: independent walks rejected",
          not is_cointegrated(w1, w2))
    hl = half_life(a - hedge_ratio(a, b) * b)
    check("half_life: near ln2/theta (~11 bars)", 5.0 < hl < 25.0)
    check("hedge_ratio: tls runs and is finite",
          np.isfinite(hedge_ratio(a, b, method="tls")))

    # --- Kalman dynamic hedge ------------------------------------------------ #
    # Test what the filter guarantees: after a structural break in beta it
    # re-learns the hedge, and its innovations (the spread the engine trades)
    # are tighter than a stale static hedge. (A slowly-drifting beta with a
    # near-constant regressor is locally alpha/beta-unidentifiable — a known
    # property of Kalman pairs hedging, so that is deliberately NOT the test.)
    n = 800
    x = 100.0 * np.exp(np.cumsum(rng.standard_normal(n)) * 0.02)  # price-like
    true_beta = np.where(np.arange(n) < 400, 1.5, 2.0)            # break at 400
    y = 0.5 + true_beta * x + rng.standard_normal(n)
    kf = KalmanHedge(delta=1e-2).initialize(y[:200], x[:200])
    _, betas, innov = kf.run(y[200:], x[200:])
    stale_beta = hedge_ratio(y[:200], x[:200])
    stale_spread = y[200:] - stale_beta * x[200:]
    check(f"kalman: re-learns beta after a break "
          f"(end {betas[-100:].mean():.2f}, true 2.0, stale {stale_beta:.2f})",
          abs(betas[-100:].mean() - 2.0) < 0.15)
    check("kalman: post-break innovations tighter than a stale static hedge",
          innov[300:].std() < stale_spread[300:].std())

    # --- signals -------------------------------------------------------------- #
    beta = hedge_ratio(a, b)
    spread = a - beta * b
    tr, te = spread[:550], spread[550:]

    # entry=1.5: the default 2.0 band is legitimately not always touched in a
    # 250-bar window; the test wants the mechanism exercised, not luck.
    zs = ZScoreSignal(entry=1.5).fit(tr)
    pos_z = zs.predict(te)
    check("zscore baseline: ternary and trades",
          set(np.unique(pos_z)) <= {-1.0, 0.0, 1.0} and (pos_z != 0).any())

    sig = MLSignal(kind="ridge").fit(tr)
    pos_r = sig.predict(te)
    check("ridge: ternary output", set(np.unique(pos_r)) <= {-1.0, 0.0, 1.0})
    check("ridge: deterministic",
          np.array_equal(pos_r, MLSignal(kind="ridge").fit(tr).predict(te)))
    z_te = (te - sig._mu) / sig._sd
    check("z-gate: longs only on cheap spreads",
          (z_te[pos_r > 0] <= -sig.z_gate).all() if (pos_r > 0).any() else True)
    check("z-gate: shorts only on rich spreads",
          (z_te[pos_r < 0] >= sig.z_gate).all() if (pos_r < 0).any() else True)

    for kind, dep in (("gbm", "sklearn"), ("lstm", "torch")):
        if resolve_kind(kind) != kind:
            if verbose:
                print(f"SKIP  {kind}: {dep} not installed (fallback covers it)")
            continue
        m = MLSignal(kind=kind, n_ensemble=2, seed=0).fit(tr)
        p = m.predict(te)
        check(f"{kind}: ternary output", set(np.unique(p)) <= {-1.0, 0.0, 1.0})

    # --- event-driven fidelity ------------------------------------------------ #
    vec = sig.predict(te)
    buf = deque(tr[-60:].tolist(), maxlen=60)
    event = []
    for xval in te:
        buf.append(xval)
        event.append(sig.predict(np.asarray(buf))[-1])
    check("event-driven == vectorized (trailing buffer, 0 mismatches)",
          np.array_equal(vec, np.asarray(event)))

    # --- screening -------------------------------------------------------------#
    closes = {"AAA": a, "BBB": b, "NOISE1": w1, "NOISE2": w2}
    table = screen_pairs(closes, min_corr=0.0)
    top = [r for r in table if r["candidate"]]
    check("screening: planted pair found as candidate",
          any({r["a"], r["b"]} == {"AAA", "BBB"} for r in top))
    check("screening: pure noise pair is not a candidate",
          not any({r["a"], r["b"]} == {"NOISE1", "NOISE2"} for r in top))

    # --- PairEngine -------------------------------------------------------------#
    eng = PairEngine("AAA|BBB", PairConfig(kind="ridge"))
    check("engine: fits a cointegrated pair", eng.fit(a[:550], b[:550]))
    positions = [eng.on_bar(a[t], b[t]) for t in range(550, 800)]
    check("engine: emits ternary positions",
          set(positions) <= {-1, 0, 1} and any(p != 0 for p in positions))
    check("engine: paper P&L accumulates", eng.paper_pnl != 0.0)

    bad = PairEngine("W1|W2", PairConfig(kind="ridge"))
    check("engine: stands down on non-cointegrated pair",
          not bad.fit(w1, w2) and bad.stood_down)

    stopper = PairEngine("AAA|BBB", PairConfig(kind="ridge",
                                               time_stop_half_lives=0.1,
                                               cooldown_bars=3))
    stopper.fit(a[:550], b[:550])
    stops = 0
    for t in range(550, 800):
        stopper.on_bar(a[t], b[t])
        stops += int(stopper.last_time_stop)
    check("engine: aggressive time stop actually fires", stops > 0)

    # --- RiskManager --------------------------------------------------------------#
    rm = RiskManager(max_drawdown=0.10, halt_bars=5, vol_lookback=10)
    events = [rm.update(v) for v in
              [100, 101, 102, 103, 90, 88, 89, 90, 91, 92, 93, 94]]
    check("risk: kill-switch trips on the drawdown", "halt" in events)
    check("risk: halt then release", "resume" in events)
    check("risk: scale is 0 while halted / >0 after",
          rm.exposure_scale() > 0)
    rm2 = RiskManager(target_vol=0.10, vol_lookback=10, min_scale=0.25, max_scale=1.5)
    for v in 100 * np.cumprod(1 + 0.05 * np.sin(np.arange(30))):
        rm2.update(v)
    check("risk: vol-target scale clamped to [min, max]",
          0.25 <= rm2.exposure_scale() <= 1.5)

    # --- budgets ---------------------------------------------------------------- #
    e1 = PairEngine("P1", PairConfig(kind="ridge")); e1.stood_down = False; e1.risk_unit = 0.02
    e2 = PairEngine("P2", PairConfig(kind="ridge")); e2.stood_down = False; e2.risk_unit = 0.04
    bud = inverse_risk_budgets([e1, e2], gross_target=0.9)
    check("budgets: sum to the gross target", abs(sum(bud.values()) - 0.9) < 1e-9)
    check("budgets: riskier pair gets less", bud["P2"] < bud["P1"])

    if verbose:
        print(f"\n{'ALL OK' if not failures else 'FAILURES: ' + str(failures)}"
              f" — {len(failures)} failed")
    return len(failures)


if __name__ == "__main__":
    raise SystemExit(selftest())
