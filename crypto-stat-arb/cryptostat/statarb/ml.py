"""
Machine-learning / neural-network signal for the stat-arb spread.

The baseline in ``signals.py`` is a hand-written z-score band: enter at ±2σ,
exit near the mean. That rule encodes one belief — *the spread mean-reverts and
its distance from the mean predicts the reversion*. This module lets the data
speak instead: engineer features from the spread's recent history and **learn**
the position with a model, validated strictly out-of-sample.

Three models, one interface:

    * ``SpreadNet``  — a small PyTorch LSTM that reads a window of the spread's
      recent behaviour (the sequence) and predicts the forward spread-trade
      return. This is the "neural network" the project is built around.
    * ``GBMSignal``  — a scikit-learn gradient-boosting regressor on the same
      engineered features. A strong, fast classical-ML baseline to beat.
    * ``RidgeSignal`` — an L2 linear model; the maximally regularized reference.
      If ridge ties the fancier models OOS, their extra capacity bought only
      overfit.

All are wrapped by ``MLSignal``, which exposes the two-call contract the
walk-forward harness needs:

    sig = MLSignal(kind="lstm").fit(spread_train)     # learn on train window ONLY
    positions = sig.predict(spread_test)              # {-1,0,+1} on unseen window

Design decisions that keep this honest
--------------------------------------
* **Label = the forward return of the long-spread trade**, i.e. the n-step-ahead
  change in the spread, normalized by its training-window scale. A positive
  prediction ⇒ the spread is expected to *rise* ⇒ go long the spread (long A /
  short β·B); negative ⇒ short it. The model therefore generalizes the z-score
  rule rather than replacing it blindly — the current z-score is one of its
  inputs, so it *can* recover the baseline if that is all the data supports.
* **Features and labels are built only from the spread handed to ``fit``.** The
  walk-forward driver (``walk_forward_ml``) fits β and the z-mean/std on the
  training window and freezes them for the test window, exactly like the
  baseline harness — nothing from the future leaks into scaling or labels.
* **Trades are gated by conviction, not by every wiggle.** ``predict`` only
  takes a position when |prediction| clears a threshold (in units of the
  training-window return σ), which controls turnover and cost.

Overfitting defences (each one measurable via the in-sample→OOS Sharpe gap):
  * **Seed ensembling** (``n_ensemble``): average predictions from several
    independently-initialized models — the cheapest variance reduction there is
    for nets trained on a few hundred bars.
  * **The z-agreement gate** (``z_gate``): a trade also needs the frozen
    z-score to agree with its direction as *mean reversion* (long only a cheap
    spread, short only a rich one). The model ranks and times entries; it
    cannot invent trades the cointegration doesn't support.
  * **Capacity control**: dropout + weight decay + early stopping in the LSTM;
    shallow subsampled trees with internal early stopping in the GBM; ridge as
    the fully-regularized reference point.
  * **Honest hyperparameter tuning** (``tune_entry``): if you must tune the
    conviction gate, it is chosen per fold on a validation tail of the
    *training* window — never on test. (Off by default: on short daily windows
    the tuning itself can overfit the tail.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..common.metrics import performance_summary, sharpe
from ..common.stats import engle_granger, hedge_ratio
from .walkforward import WalkForwardResult, _spread_returns


# --------------------------------------------------------------------------- #
# Feature engineering
# --------------------------------------------------------------------------- #
def spread_features(spread: np.ndarray, mu: float, sd: float,
                    lookback: int = 10) -> np.ndarray:
    """
    Per-timestep features describing where the spread is and how it is moving.

    Everything is standardized with the *training* mean/std (``mu``, ``sd``) so
    the model sees the same scale in train and test. Returns an ``(n, F)`` array
    aligned to ``spread`` (early rows use only the history available, no NaNs).

    Features per row t:
        z_t                              current standardized level
        z_{t-1..t-k}                     lagged levels (the sequence shape)
        Δz over 1, 3, 5 steps            momentum / velocity of the spread
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


def forward_label(spread: np.ndarray, horizon: int, sd: float) -> np.ndarray:
    """
    Regression target: the spread's change ``horizon`` steps ahead, in σ units.

    ``label[t] = (spread[t+horizon] - spread[t]) / sd``. The last ``horizon``
    rows have no future and are returned as NaN (the caller drops them from the
    training set). Positive ⇒ spread rises ⇒ long-spread trade profits.
    """
    s = np.asarray(spread, dtype=float)
    sd = sd if sd > 0 else 1.0
    n = s.size
    out = np.full(n, np.nan)
    if horizon < n:
        out[:n - horizon] = (s[horizon:] - s[:n - horizon]) / sd
    return out


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
def _build_sequences(feats: np.ndarray, seq_len: int) -> np.ndarray:
    """Stack each row's trailing ``seq_len`` feature vectors into a sequence
    tensor of shape ``(n, seq_len, F)`` (front-padded by repeating row 0)."""
    n, f = feats.shape
    pad = np.repeat(feats[:1], seq_len - 1, axis=0)
    padded = np.vstack([pad, feats])
    return np.stack([padded[i:i + seq_len] for i in range(n)])


class SpreadNet:
    """
    A compact LSTM regressor: sequence of spread features → forward return.

    Kept deliberately small (one LSTM layer + a linear head) because pairs data
    is short and daily — a big network would only memorize. Standardizes inputs
    with training-set statistics, trains with Adam + early-stopping on a held-out
    tail of the training window, and is fully deterministic given a seed.
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

    def fit(self, feats: np.ndarray, labels: np.ndarray):
        import torch

        rng = np.random.default_rng(self.seed)
        self._fmu = feats.mean(axis=0)
        self._fsd = feats.std(axis=0)
        self._fsd[self._fsd == 0] = 1.0
        fz = (feats - self._fmu) / self._fsd

        seqs = _build_sequences(fz, self.seq_len)
        X = torch.tensor(seqs, dtype=torch.float32)
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
        _ = rng  # reserved for future stochastic batching
        return self

    def predict(self, feats: np.ndarray) -> np.ndarray:
        import torch
        fz = (feats - self._fmu) / self._fsd
        seqs = _build_sequences(fz, self.seq_len)
        self._model.eval()
        with torch.no_grad():
            return self._model(torch.tensor(seqs, dtype=torch.float32)).numpy()


class GBMSignal:
    """Gradient-boosting regressor on the same features — the classical-ML
    baseline the neural net has to beat. No sequence windowing; the lagged
    features already carry the recent shape.

    Regularized against small, autocorrelated financial samples: shallow trees,
    row subsampling, a minimum leaf size, and internal early stopping on a
    held-out validation fraction (``n_iter_no_change``) so the boosting run
    stops as soon as it starts memorizing."""

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


class RidgeSignal:
    """L2-regularized linear model on the same features — the maximally
    regularized end of the model spectrum. If ridge ties the fancier models
    out-of-sample, the extra capacity was buying only overfit."""

    def __init__(self, alpha=10.0, seed=0):
        self.alpha = alpha
        _ = seed                               # deterministic; kept for interface parity
        self._model = None

    def fit(self, feats, labels):
        from sklearn.linear_model import Ridge
        self._model = Ridge(alpha=self.alpha).fit(feats, labels)
        return self

    def predict(self, feats):
        return self._model.predict(feats)


# --------------------------------------------------------------------------- #
# The signal wrapper
# --------------------------------------------------------------------------- #
class MLSignal:
    """
    Learn a spread-trading position from data.

    Parameters
    ----------
    kind : "lstm" (SpreadNet), "gbm" (GBMSignal) or "ridge" (RidgeSignal).
    horizon : how many steps ahead the label looks (the reversion horizon).
    entry_sigma : take a position only when the predicted return exceeds this
        many training-prediction σ (conviction gate; higher ⇒ fewer,
        higher-quality trades).
    lookback : window for the rolling/RSI features.
    n_ensemble : train this many models with different seeds and average their
        predictions. Ensembling is the cheapest variance-reduction there is for
        small-data nets — the seed lottery washes out.
    z_gate : if set, a prediction only becomes a trade when the *frozen* z-score
        also agrees with it as mean-reversion: long the spread only when
        z ≤ -z_gate, short only when z ≥ +z_gate. The model can rank and time
        entries, but it cannot invent trades the cointegration doesn't support —
        a structural cap on how much damage an overfit model can do.
    """

    def __init__(self, kind="lstm", horizon=5, entry_sigma=0.5, lookback=10,
                 n_ensemble=1, z_gate=None, model_kwargs=None, seed=0):
        self.kind = kind
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
        if self.kind == "lstm":
            return SpreadNet(seed=seed, **self.model_kwargs)
        if self.kind == "gbm":
            return GBMSignal(seed=seed, **self.model_kwargs)
        if self.kind == "ridge":
            return RidgeSignal(seed=seed, **self.model_kwargs)
        raise ValueError("kind must be 'lstm', 'gbm' or 'ridge'")

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

        feats = spread_features(s, self._mu, self._sd, self.lookback)
        labels = forward_label(s, self.horizon, self._sd)
        ok = ~np.isnan(labels)
        Xf, yf = feats[ok], labels[ok]

        self._models = [self._new_model(self.seed + k).fit(Xf, yf)
                        for k in range(self.n_ensemble)]
        # Scale of in-sample predictions sets the conviction gate for test.
        insample_pred = self._ensemble_predict(Xf)
        self._pred_sd = float(np.std(insample_pred)) or 1.0
        return self

    def predict(self, spread_test) -> np.ndarray:
        """Position array in {-1,0,+1} for an unseen spread window, using the
        β/μ/σ and model(s) frozen at ``fit`` time."""
        s = np.asarray(spread_test, dtype=float)
        feats = spread_features(s, self._mu, self._sd, self.lookback)
        pred = self._ensemble_predict(feats)
        gate = self.entry_sigma * self._pred_sd
        pos = np.zeros(s.size)
        pos[pred >= gate] = 1.0
        pos[pred <= -gate] = -1.0
        if self.z_gate is not None:
            z = (s - self._mu) / self._sd
            pos[(pos > 0) & (z > -self.z_gate)] = 0.0     # long needs a cheap spread
            pos[(pos < 0) & (z < self.z_gate)] = 0.0      # short needs a rich spread
        return pos

    # convenience so an already-fit MLSignal can be dropped in as signal_fn-style
    def __call__(self, spread_test):
        return self.predict(spread_test)


# --------------------------------------------------------------------------- #
# Walk-forward driver for the learned signal
# --------------------------------------------------------------------------- #
_ENTRY_GRID = (0.25, 0.5, 0.75, 1.0, 1.5)


def _tune_entry_sigma(a_tr, b_tr, kind, horizon, lookback, n_ensemble, z_gate,
                      cost_bps, hedge_method, model_kwargs, seed,
                      periods_per_year, grid=_ENTRY_GRID, val_frac=0.25):
    """
    Pick ``entry_sigma`` on a validation tail of the TRAINING window only.

    Fits the model on the front of the training window, replays each candidate
    gate on the held-back tail (with costs), and returns the gate with the best
    validation Sharpe. Nothing from the test window is touched — this is how you
    optimize a hyperparameter without paying for it in hidden look-ahead.
    """
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
        ret = _spread_returns(a_val, b_val, beta, pos)
        ret = ret - np.abs(np.diff(pos, prepend=0.0)) * (cost_bps / 1e4)
        s = sharpe(ret, periods_per_year)
        if s > best_sharpe:
            best_sharpe, best_gate = s, gate
    return best_gate


def walk_forward_ml(
    price_a, price_b, train=250, test=40, anchored=False,
    kind="lstm", horizon=5, entry_sigma=0.5, lookback=10,
    n_ensemble=3, z_gate=1.0, tune_entry=False,
    cost_bps=10.0, hedge_method="ols", recheck_coint=False, coint_alpha=0.05,
    model_kwargs=None, periods_per_year=365, seed=0,
) -> WalkForwardResult:
    """
    Out-of-sample validation for the ML signal — the honest judge.

    Identical rolling protocol to ``statarb.walk_forward``, but each fold also
    **re-trains the model on the training window** before predicting the unseen
    test window. β and the spread mean/std are estimated on train and frozen for
    test; the model never sees test data during fitting. Returns the same
    ``WalkForwardResult`` so ``.summary()`` and the in-sample-vs-OOS Sharpe gap
    (the overfitting tax) work unchanged.

    Anti-overfitting levers (all leakage-free):
    n_ensemble : average several differently-seeded models per fold.
    z_gate : require the frozen z-score to agree with each trade's direction.
    tune_entry : choose ``entry_sigma`` per fold on a validation tail of the
        training window instead of trusting a fixed guess.
    """
    a_full = np.asarray(price_a, dtype=float)
    b_full = np.asarray(price_b, dtype=float)
    idx = price_a.index if isinstance(price_a, pd.Series) else pd.RangeIndex(len(a_full))
    n = a_full.size

    oos_ret = np.full(n, np.nan)
    insample_ret = []
    fold_rows = []

    t = train
    while t + test <= n:
        tr = slice(0 if anchored else t - train, t)
        te = slice(t, t + test)
        a_tr, b_tr = a_full[tr], b_full[tr]
        a_te, b_te = a_full[te], b_full[te]

        beta = hedge_ratio(a_tr, b_tr, method=hedge_method)
        spread_tr = a_tr - beta * b_tr
        mu, sd = spread_tr.mean(), spread_tr.std()

        stood_down = False
        fold_entry = entry_sigma
        if recheck_coint and not engle_granger(a_tr, b_tr).is_cointegrated(coint_alpha):
            stood_down = True
            pos_te = np.zeros(a_te.size)
            ret_te = np.zeros(a_te.size)
            pos_tr = np.zeros(a_tr.size)
        else:
            if tune_entry:
                fold_entry = _tune_entry_sigma(
                    a_tr, b_tr, kind, horizon, lookback, n_ensemble, z_gate,
                    cost_bps, hedge_method, model_kwargs, seed, periods_per_year)
            sig = MLSignal(kind=kind, horizon=horizon, entry_sigma=fold_entry,
                           lookback=lookback, n_ensemble=n_ensemble, z_gate=z_gate,
                           model_kwargs=model_kwargs, seed=seed)
            sig.fit(spread_tr, mu=mu, sd=sd)

            spread_te = a_te - beta * b_te
            pos_te = sig.predict(spread_te)
            ret_te = _spread_returns(a_te, b_te, beta, pos_te)
            ret_te = ret_te - np.abs(np.diff(pos_te, prepend=0.0)) * (cost_bps / 1e4)

            # In-sample (train-window) trace for the overfitting diagnostic.
            pos_tr = sig.predict(spread_tr)

        oos_ret[te] = ret_te
        ret_tr = _spread_returns(a_tr, b_tr, beta, pos_tr)
        insample_ret.append(ret_tr)

        fold_rows.append({
            "train_start": idx[tr.start], "test_start": idx[t],
            "test_end": idx[min(t + test, n) - 1],
            "beta": beta,
            "train_sharpe": sharpe(ret_tr, periods_per_year),
            "test_sharpe": sharpe(ret_te, periods_per_year),
            "n_trades": int((np.abs(np.diff(pos_te, prepend=0.0)) > 0).sum()),
            "entry_sigma": fold_entry,
            "stood_down": stood_down,
        })
        t += test

    oos = pd.Series(oos_ret, index=idx).dropna()
    folds = pd.DataFrame(fold_rows)
    insample = sharpe(np.concatenate(insample_ret), periods_per_year) if insample_ret else 0.0

    return WalkForwardResult(
        oos_returns=oos, folds=folds, insample_sharpe=float(insample),
        oos_sharpe=float(sharpe(oos, periods_per_year)),
        periods_per_year=periods_per_year,
    )
