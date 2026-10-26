"""
ML / neural-network crypto statistical-arbitrage portfolio on QuantConnect.

A complete, walk-forward-honest pairs-trading system — the full port of the
cryptostat research repo's strategy plus the extensions its "Research tasks"
list calls for, implemented for LEAN's event-driven model:

    ┌─────────────────────────────────────────────────────────────────────┐
    │ monthly REBUILD (self.Train — extended time budget, off data thread)│
    │                                                                     │
    │  1. pull trailing TRAIN_DAYS of daily closes for the whole universe │
    │  2. SCREEN every pair for cointegration on that window only         │
    │     (walk-forward pair selection — no selection bias)               │
    │  3. pick the top MAX_PAIRS candidates (optionally one leg per coin) │
    │  4. for each pair: re-fit hedge (OLS / TLS / Kalman), freeze mu/sd, │
    │     measure half-life, train the ML ensemble, seed buffers          │
    │  5. pairs that de-cointegrated STAND DOWN until the next rebuild    │
    ├─────────────────────────────────────────────────────────────────────┤
    │ daily ONDATA                                                        │
    │                                                                     │
    │  1. each PairEngine consumes its two bars -> target {-1, 0, +1}     │
    │     (Kalman beta update, ML prediction, z-agreement gate,           │
    │      half-life time stop, post-stop cooldown)                       │
    │  2. RiskManager: volatility targeting + drawdown kill-switch        │
    │  3. inverse-risk budgets across active pairs (risk parity lite)     │
    │  4. aggregate per-symbol weights, rebalance inside a tolerance band │
    └─────────────────────────────────────────────────────────────────────┘

Mapping from the research repo:

    walk_forward_ml fold retraining    ->  the monthly rebuild
    recheck_coint stand-down           ->  full Engle-Granger guard per refit
    screen_pairs (scripts/02)          ->  walk-forward screening per rebuild
    "portfolio of pairs" (task 4)      ->  multi-pair book, inverse-risk budgets
    "Kalman dynamic hedge" (task 2)    ->  PairConfig(hedge="kalman")
    "half-life time stops" (task 3)    ->  PairEngine time stop + cooldown
    cost_bps proxy                     ->  REMOVED: QC's fee models price trades

Availability workarounds (per the "make it work on QC" rule):

    * Coinbase spot on QC is a CASH account (no shorting) -> default is
      Binance USDT-margined PERPETUAL FUTURES, where shorting is native.
      Set USE_PERPS = False for Bitfinex margin spot instead.
    * torch / sklearn may be absent in a local LEAN docker -> the model
      degrades lstm -> gbm -> pure-numpy ridge automatically (logged).
    * statsmodels / scipy -> never used; all statistics are numpy-only.

Tunable from the cloud without editing code: every major knob reads an
optional QC project Parameter of the same name (see _param calls in
Initialize), so cloud parameter optimization jobs work out of the box.

Troubleshooting
---------------
    "No module named 'spread_ml'"   -> you deployed the two-file layout without
                                       adding spread_ml.py; use the standalone
                                       build or add the second file.
    "staying flat / no history"     -> QC has no data yet for those perps at
                                       your start date; move SetStartDate
                                       forward or trim PERP_UNIVERSE.
    "fewer than 4 universe symbols" -> the venue/data subscription resolved
                                       almost nothing; check the venue toggle.
    algo trades nothing for months  -> normal when no pair passes the
                                       cointegration screen: check the rebuild
                                       logs; the strategy prefers flat over
                                       trading a broken relationship.

Single-file build: run build_standalone.py to regenerate main_standalone.py
with spread_ml embedded (one paste = whole project, no second file to forget).
"""

from AlgorithmImports import *  # noqa: F401,F403  (QC injects the LEAN API)

from collections import deque

import numpy as np

# [STANDALONE-EMBED spread_ml]
from spread_ml import (  # [STANDALONE-STRIP]
    PairConfig, PairEngine, PerformanceTracker, RiskManager,  # [STANDALONE-STRIP]
    inverse_risk_budgets, resolve_kind, screen_pairs,  # [STANDALONE-STRIP]
)  # [STANDALONE-STRIP]


class CryptoMLPairsTrading(QCAlgorithm):
    """
    Multi-pair ML statistical arbitrage over crypto perpetual futures.

    Every parameter below can be overridden per-backtest with a QC project
    Parameter of the same name — numbers stay numbers, booleans accept
    true/false, and the strategy logs the resolved configuration at start.
    """

    # ----- venue -------------------------------------------------------------- #
    USE_PERPS = True                    # False -> Bitfinex margin spot
    PERP_UNIVERSE = [
        "BTCUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "ADAUSDT", "XRPUSDT",
        "DOGEUSDT", "SOLUSDT", "AVAXUSDT", "DOTUSDT", "ATOMUSDT", "ETCUSDT",
        "BCHUSDT", "XLMUSDT",
    ]
    SPOT_UNIVERSE = [                   # Bitfinex margin alternative
        "BTCUSD", "ETHUSD", "LINKUSD", "LTCUSD", "ADAUSD", "XRPUSD",
        "SOLUSD", "AVAXUSD", "DOTUSD", "ETCUSD",
    ]

    # ----- walk-forward protocol ---------------------------------------------- #
    TRAIN_DAYS = 250                    # training window (matches the research)
    MIN_TRAIN = 200                     # skip a rebuild below this much history

    # ----- pair selection ------------------------------------------------------ #
    MAX_PAIRS = 4                       # book size (pairs traded concurrently)
    MIN_CORR = 0.5                      # correlation prefilter for screening
    COINT_ALPHA = 0.05                  # EG significance for candidacy/stand-down
    MIN_HALF_LIFE = 2.0                 # tradeable half-life band, in days
    MAX_HALF_LIFE = 90.0
    ONE_LEG_PER_COIN = True             # greedy selection: no shared legs

    # ----- signal ---------------------------------------------------------------#
    MODEL_KIND = "lstm"                 # lstm -> gbm -> ridge auto-fallback,
                                        # or "zscore" = the research baseline
                                        # (run it first: it is the control group)
    HORIZON = 5                         # label horizon (days ahead)
    ENTRY_SIGMA = 0.5                   # conviction gate (prediction sigmas)
    N_ENSEMBLE = 3                      # seed ensemble per refit
    Z_GATE = 1.0                        # z-score agreement gate (0 disables)
    TUNE_ENTRY = False                  # per-refit gate tuning (opt-in; mixed
                                        # results in research — see repo README)
    HEDGE_METHOD = "ols"                # "ols" | "tls" | "kalman"
    KALMAN_DELTA = 1e-4                 # beta drift speed when hedge="kalman"

    # ----- risk ------------------------------------------------------------------#
    GROSS_TARGET = 0.90                 # total gross exposure across all pairs
    TARGET_VOL = 0.15                   # annualized portfolio vol target
    VOL_LOOKBACK = 30                   # bars for realized-vol estimate
    MAX_DRAWDOWN = 0.20                 # kill-switch threshold (fraction)
    HALT_BARS = 30                      # bars to stay flat after kill-switch
    TIME_STOP_HL = 3.0                  # exit after N half-lives held (0 = off)
    COOLDOWN_BARS = 5                   # bars flat after a time stop
    REBALANCE_BAND = 0.02               # min |weight change| to trade (2%)

    # ----- plumbing ---------------------------------------------------------------#
    BUF_LEN = 60                        # trailing spread buffer for prediction
    MIN_PREDICT = 40                    # bars needed before first prediction
    PLOT_EVERY = 5                      # chart cadence (bars) — QC point limits
    SEED = 0

    # ======================================================================= #
    # Initialization
    # ======================================================================= #
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self._load_parameters()

        # --- venue & universe ------------------------------------------------ #
        self.symbols = []
        if self.USE_PERPS:
            # Workaround: QC's Coinbase (cash account) can't short — Binance
            # USDT-margined perpetuals short natively.
            self.SetAccountCurrency("USDT")
            self.SetCash(100_000)
            self.SetBrokerageModel(BrokerageName.BinanceFutures, AccountType.Margin)
            for ticker in self.PERP_UNIVERSE:
                try:
                    sec = self.AddCryptoFuture(ticker, Resolution.Daily)
                    self.symbols.append(sec.Symbol)
                except Exception as err:  # data not provisioned for this ticker
                    self.Log(f"universe: skipping {ticker} ({err})")
        else:
            self.SetCash(100_000)
            self.SetBrokerageModel(BrokerageName.Bitfinex, AccountType.Margin)
            for ticker in self.SPOT_UNIVERSE:
                try:
                    sec = self.AddCrypto(ticker, Resolution.Daily, Market.Bitfinex)
                    self.symbols.append(sec.Symbol)
                except Exception as err:
                    self.Log(f"universe: skipping {ticker} ({err})")

        if len(self.symbols) < 4:
            raise ValueError("fewer than 4 universe symbols resolved — "
                             "check data availability for the venue")

        # Allow small rebalances (the band, not QC's margin buffer, gates them).
        self.Settings.MinimumOrderMarginPortfolioPercentage = 0

        # --- state ------------------------------------------------------------ #
        self.engines = {}               # pair name -> PairEngine
        self.pair_symbols = {}          # pair name -> (Symbol, Symbol)
        self.last_bar_time = {}         # pair name -> last consumed EndTime
        self.tracker = PerformanceTracker(periods_per_year=365)
        self.risk = RiskManager(
            target_vol=self.TARGET_VOL, vol_lookback=self.VOL_LOOKBACK,
            max_drawdown=self.MAX_DRAWDOWN, halt_bars=self.HALT_BARS,
            periods_per_year=365)
        self.total_fees = 0.0
        self.fill_count = 0
        self._bars_seen = 0
        self._rebuilds = 0

        # --- schedules ---------------------------------------------------------#
        # Monthly rebuild mirrors the research repo's test=30 walk-forward
        # cadence; Train() runs off the data thread with an extended time
        # budget — the right place for screening + the LSTM ensemble fits.
        self.Train(self.DateRules.MonthStart(), self.TimeRules.Midnight,
                   self.RebuildPortfolio)
        self.Train(self.RebuildPortfolio)      # initial build at start

        # Weekly book-state snapshot — the log you actually read when checking
        # on a running algorithm, without waiting for the end-of-run report.
        self.Schedule.On(self.DateRules.Every(DayOfWeek.Monday),
                         self.TimeRules.Midnight, self.LogBookState)

        self._log_config()

    # ----- cloud parameter overrides ------------------------------------------- #
    def _param(self, name, default):
        """Read a QC project Parameter, falling back to the class default.
        Accepts int/float/bool/str depending on the default's type."""
        raw = self.GetParameter(name)
        if raw is None or raw == "":
            return default
        try:
            if isinstance(default, bool):
                return str(raw).strip().lower() in ("1", "true", "yes", "on")
            return type(default)(raw)
        except (TypeError, ValueError):
            self.Log(f"parameter {name}={raw!r} unparsable; using {default}")
            return default

    def _load_parameters(self):
        self.TRAIN_DAYS = self._param("TRAIN_DAYS", self.TRAIN_DAYS)
        self.MAX_PAIRS = self._param("MAX_PAIRS", self.MAX_PAIRS)
        self.MODEL_KIND = self._param("MODEL_KIND", self.MODEL_KIND)
        self.HORIZON = self._param("HORIZON", self.HORIZON)
        self.ENTRY_SIGMA = self._param("ENTRY_SIGMA", self.ENTRY_SIGMA)
        self.N_ENSEMBLE = self._param("N_ENSEMBLE", self.N_ENSEMBLE)
        self.Z_GATE = self._param("Z_GATE", self.Z_GATE)
        self.TUNE_ENTRY = self._param("TUNE_ENTRY", self.TUNE_ENTRY)
        self.HEDGE_METHOD = self._param("HEDGE_METHOD", self.HEDGE_METHOD)
        self.GROSS_TARGET = self._param("GROSS_TARGET", self.GROSS_TARGET)
        self.TARGET_VOL = self._param("TARGET_VOL", self.TARGET_VOL)
        self.MAX_DRAWDOWN = self._param("MAX_DRAWDOWN", self.MAX_DRAWDOWN)
        self.TIME_STOP_HL = self._param("TIME_STOP_HL", self.TIME_STOP_HL)
        self.MIN_CORR = self._param("MIN_CORR", self.MIN_CORR)
        self.COINT_ALPHA = self._param("COINT_ALPHA", self.COINT_ALPHA)
        self.KALMAN_DELTA = self._param("KALMAN_DELTA", self.KALMAN_DELTA)
        self.HALT_BARS = self._param("HALT_BARS", self.HALT_BARS)
        self.REBALANCE_BAND = self._param("REBALANCE_BAND", self.REBALANCE_BAND)
        self.ONE_LEG_PER_COIN = self._param("ONE_LEG_PER_COIN", self.ONE_LEG_PER_COIN)

    def _log_config(self):
        """Echo the resolved configuration once at start — when a cloud
        parameter override typos its name, this is where you catch it."""
        self.Log("config | venue=" + ("binance-perps" if self.USE_PERPS else "bitfinex-margin")
                 + f" universe={len(self.symbols)}")
        self.Log(f"config | walk-forward: TRAIN_DAYS={self.TRAIN_DAYS} "
                 f"MIN_TRAIN={self.MIN_TRAIN} rebuild=monthly")
        self.Log(f"config | selection: MAX_PAIRS={self.MAX_PAIRS} "
                 f"MIN_CORR={self.MIN_CORR} COINT_ALPHA={self.COINT_ALPHA} "
                 f"HL=[{self.MIN_HALF_LIFE},{self.MAX_HALF_LIFE}]d "
                 f"ONE_LEG_PER_COIN={self.ONE_LEG_PER_COIN}")
        self.Log(f"config | signal: MODEL_KIND={self.MODEL_KIND} "
                 f"(resolves {resolve_kind(self.MODEL_KIND)}) HORIZON={self.HORIZON} "
                 f"ENTRY_SIGMA={self.ENTRY_SIGMA} N_ENSEMBLE={self.N_ENSEMBLE} "
                 f"Z_GATE={self.Z_GATE} TUNE_ENTRY={self.TUNE_ENTRY}")
        self.Log(f"config | hedge: {self.HEDGE_METHOD}"
                 + (f" delta={self.KALMAN_DELTA}" if self.HEDGE_METHOD == "kalman" else ""))
        self.Log(f"config | risk: GROSS={self.GROSS_TARGET} TARGET_VOL={self.TARGET_VOL} "
                 f"MAX_DD={self.MAX_DRAWDOWN} HALT={self.HALT_BARS} "
                 f"TIME_STOP={self.TIME_STOP_HL}HL BAND={self.REBALANCE_BAND}")

    def _pair_config(self):
        return PairConfig(
            kind=self.MODEL_KIND, horizon=self.HORIZON,
            entry_sigma=self.ENTRY_SIGMA, n_ensemble=self.N_ENSEMBLE,
            z_gate=(self.Z_GATE if self.Z_GATE > 0 else None),
            tune_entry=self.TUNE_ENTRY,
            hedge=self.HEDGE_METHOD, kalman_delta=self.KALMAN_DELTA,
            coint_alpha=self.COINT_ALPHA,
            min_half_life=self.MIN_HALF_LIFE, max_half_life=self.MAX_HALF_LIFE,
            time_stop_half_lives=self.TIME_STOP_HL,
            cooldown_bars=self.COOLDOWN_BARS,
            buf_len=self.BUF_LEN, min_predict=self.MIN_PREDICT, seed=self.SEED)

    # ======================================================================= #
    # Monthly rebuild: screen -> select -> fit  (one walk-forward fold)
    # ======================================================================= #
    def RebuildPortfolio(self):
        self._rebuilds += 1
        closes, times = self._training_panel()
        if closes is None:
            self.Log("rebuild: insufficient history — book unchanged")
            return

        # --- 1. screen every pair on the TRAINING window only ----------------- #
        table = screen_pairs(
            closes, alpha=self.COINT_ALPHA, min_corr=self.MIN_CORR,
            min_half_life=self.MIN_HALF_LIFE, max_half_life=self.MAX_HALF_LIFE)
        candidates = [r for r in table if r["candidate"]]
        self.Log(f"rebuild #{self._rebuilds}: screened "
                 f"{len(table)} correlated pairs -> {len(candidates)} candidates")

        # --- 2. greedy selection (optionally one leg per coin) ---------------- #
        selected, used = [], set()
        for row in candidates:
            if len(selected) >= self.MAX_PAIRS:
                break
            if self.ONE_LEG_PER_COIN and (row["a"] in used or row["b"] in used):
                continue
            selected.append(row)
            used.update((row["a"], row["b"]))

        # --- 3. fit / refit engines ------------------------------------------- #
        new_engines, new_pairs = {}, {}
        for row in selected:
            name = f"{row['a']}|{row['b']}"
            engine = self.engines.get(name) or PairEngine(name, self._pair_config())
            ok = engine.fit(closes[row["a"]], closes[row["b"]])
            self.tracker.record_refit(name)
            if not ok:
                # Candidate on log-prices but rejected on raw (or half-life
                # drifted out of band between screen and fit) — skip it.
                self.tracker.record_stand_down(name)
                self.Log(f"rebuild: {name} stood down at fit "
                         f"(EG {engine.eg_stat:.2f}, HL {engine.half_life:.1f})")
                continue
            new_engines[name] = engine
            new_pairs[name] = (self._symbol_of(row["a"]), self._symbol_of(row["b"]))
            self.last_bar_time[name] = times[-1]
            self.Log(f"rebuild: {name} fit {engine.model.resolved_kind}"
                     f" x{engine.cfg.n_ensemble} | beta {engine.current_beta():.3f}"
                     f" | EG {engine.eg_stat:.2f} | HL {engine.half_life:.1f}d"
                     f" | gate {engine.model.entry_sigma:.2f}")

        # --- 4. retire pairs that fell out of the book ------------------------- #
        for name in set(self.engines) - set(new_engines):
            self.Log(f"rebuild: retiring {name}")
        self.engines = new_engines
        self.pair_symbols = new_pairs

        if not self.engines:
            self.Log("rebuild: NO tradeable pairs this fold — going flat")
            if self.Portfolio.Invested:
                self.Liquidate()

    def _training_panel(self):
        """Trailing TRAIN_DAYS of aligned daily closes for the whole universe.
        Returns ({ticker: np.ndarray}, DatetimeIndex) or (None, None)."""
        hist = self.History(self.symbols, self.TRAIN_DAYS + 20, Resolution.Daily)
        if hist.empty or "close" not in hist.columns:
            return None, None
        panel = hist["close"].unstack(level=0)
        keep = [s for s in self.symbols
                if s in panel.columns and panel[s].notna().sum() >= self.MIN_TRAIN]
        if len(keep) < 4:
            return None, None
        panel = panel[keep].dropna()
        if len(panel) < self.MIN_TRAIN:
            return None, None
        panel = panel.iloc[-self.TRAIN_DAYS:]
        closes = {self._ticker_of(s): panel[s].to_numpy(dtype=float) for s in keep}
        return closes, panel.index

    def _ticker_of(self, symbol):
        return str(symbol.Value)

    def _symbol_of(self, ticker):
        for s in self.symbols:
            if str(s.Value) == ticker:
                return s
        raise KeyError(ticker)

    # ======================================================================= #
    # Daily trading
    # ======================================================================= #
    def OnData(self, data):
        if not self.engines:
            return
        bars = data.Bars
        prices, progressed = {}, False

        # --- 1. feed each pair engine its bar ---------------------------------- #
        for name, engine in self.engines.items():
            sym_a, sym_b = self.pair_symbols[name]
            if not (bars.ContainsKey(sym_a) and bars.ContainsKey(sym_b)):
                continue
            t = bars[sym_a].EndTime
            if t <= self.last_bar_time.get(name, t.min):
                continue                       # rebuild History already saw it
            self.last_bar_time[name] = t

            pa, pb = float(bars[sym_a].Close), float(bars[sym_b].Close)
            if pa <= 0 or pb <= 0:
                continue
            # Data-quality guard: a zero-volume daily bar on a major perp is a
            # stale/synthetic print — don't let it move the spread state.
            if (getattr(bars[sym_a], "Volume", 1) == 0
                    or getattr(bars[sym_b], "Volume", 1) == 0):
                continue
            prices[sym_a], prices[sym_b] = pa, pb

            prev = engine.position
            pos = engine.on_bar(pa, pb)
            progressed = True
            self.tracker.record_bar(name, pos)
            self.tracker.record_pair_return(name, engine.last_paper_ret)
            if pos != prev:
                self.tracker.record_trade(name)
                self.Debug(f"{self.Time.date()} {name}: {prev:+d} -> {pos:+d} "
                           f"(beta {engine.current_beta():.3f})")
            if engine.last_time_stop:
                self.tracker.record_time_stop(name)
                self.Log(f"{self.Time.date()} {name}: half-life time stop after "
                         f"{engine.cfg.time_stop_half_lives:.0f} HLs; "
                         f"cooldown {engine.cfg.cooldown_bars} bars")

        if not progressed:
            return
        self._bars_seen += 1

        # --- 2. portfolio risk: vol targeting + drawdown kill-switch ------------ #
        equity = float(self.Portfolio.TotalPortfolioValue)
        self.tracker.record_equity(self.Time, equity)
        event = self.risk.update(equity)
        if event == "halt":
            self.Log(self.risk.events[-1])
            self.Liquidate()
            return
        if event == "resume":
            self.Log(self.risk.events[-1])
        if self.risk.halted:
            return

        # --- 3. size the book: inverse-risk budgets, then aggregate ------------- #
        scale = self.risk.exposure_scale()
        budgets = inverse_risk_budgets(list(self.engines.values()),
                                       self.GROSS_TARGET * scale)
        targets = self._aggregate_targets(budgets, prices)
        self._apply_targets(targets)

        # --- 4. telemetry --------------------------------------------------------#
        if self._bars_seen % self.PLOT_EVERY == 0:
            gross = sum(abs(w) for w in targets.values())
            active = sum(1 for e in self.engines.values() if e.position != 0)
            self.Plot("Risk", "ExposureScale", round(scale, 3))
            self.Plot("Risk", "Drawdown %", round(self.risk.drawdown * 100, 2))
            self.Plot("Book", "GrossTarget", round(gross, 3))
            self.Plot("Book", "PairsActive", active)

    def _aggregate_targets(self, budgets, prices):
        """
        Sum leg weights across pairs into one target per symbol. A coin can
        appear in two pairs (when ONE_LEG_PER_COIN is off) — its weights simply
        net. Symbols currently held but no longer targeted get an explicit 0 so
        retired pairs are unwound.
        """
        targets = {}
        for name, engine in self.engines.items():
            sym_a, sym_b = self.pair_symbols[name]
            if sym_a not in prices or sym_b not in prices:
                continue
            wa, wb = engine.leg_weights(prices[sym_a], prices[sym_b],
                                        budgets.get(name, 0.0))
            targets[sym_a] = targets.get(sym_a, 0.0) + wa
            targets[sym_b] = targets.get(sym_b, 0.0) + wb
        for sym in self.symbols:
            if sym not in targets and self.Portfolio[sym].Invested:
                targets[sym] = 0.0
        return targets

    def _apply_targets(self, targets):
        """Send orders only where the weight moved more than REBALANCE_BAND —
        without the band, hedge drift would churn fees every single bar."""
        equity = float(self.Portfolio.TotalPortfolioValue)
        if equity <= 0:
            return
        changes = []
        for sym, w in targets.items():
            current = float(self.Portfolio[sym].HoldingsValue) / equity
            if abs(w - current) > self.REBALANCE_BAND:
                changes.append(PortfolioTarget(sym, w))
        if changes:
            self.SetHoldings(changes)

    # ======================================================================= #
    # Telemetry
    # ======================================================================= #
    def OnOrderEvent(self, order_event):
        if order_event.Status == OrderStatus.Filled:
            self.fill_count += 1
            try:
                self.total_fees += float(order_event.OrderFee.Value.Amount)
            except Exception:
                pass                         # fee currency conversion edge case

    def LogBookState(self):
        """One line per pair: position, hedge, where the spread sits (z),
        how long the trade has been on, and cumulative paper attribution."""
        if not self.engines:
            self.Log("book: empty (no tradeable pairs this fold)")
            return
        for name, engine in self.engines.items():
            if engine.stood_down or not engine.buf:
                self.Log(f"book | {name}: stood down")
                continue
            z = (engine.buf[-1] - engine.mu) / engine.sd if engine.sd > 0 else 0.0
            self.Log(f"book | {name}: pos {engine.position:+d} | "
                     f"beta {engine.current_beta():.3f} | z {z:+.2f} | "
                     f"held {engine.holding_bars}d | "
                     f"paper {engine.paper_pnl:+.2%} | HL {engine.half_life:.0f}d")
        self.Log(f"book | risk: scale {self.risk.exposure_scale():.2f} | "
                 f"dd {self.risk.drawdown:+.1%} | "
                 f"halted {self.risk.halted} | fees {self.total_fees:,.0f}")

    def OnMarginCallWarning(self):
        """LEAN fires this when margin usage approaches the limit. The book is
        sized to GROSS_TARGET < 1 so this should never fire — if it does,
        something (funding drag, a gap) ate the buffer: de-risk immediately
        rather than wait for forced liquidation at the broker's prices."""
        self.Log("MARGIN CALL WARNING — halving exposure defensively")
        equity = float(self.Portfolio.TotalPortfolioValue)
        if equity <= 0:
            return
        targets = []
        for sym in self.symbols:
            holding = self.Portfolio[sym]
            if holding.Invested:
                current = float(holding.HoldingsValue) / equity
                targets.append(PortfolioTarget(sym, current * 0.5))
        if targets:
            self.SetHoldings(targets)

    def OnMarginCall(self, requests):
        """Actual margin call: log what LEAN is about to liquidate so the
        post-mortem has the full picture, then let the default handling run."""
        for request in requests:
            self.Log(f"MARGIN CALL: liquidating {request.Symbol} "
                     f"qty {request.Quantity}")
        return requests

    def OnEndOfAlgorithm(self):
        self.Log("=" * 72)
        self.Log(f"END OF RUN | equity {self.Portfolio.TotalPortfolioValue:,.2f} "
                 f"{self.AccountCurrency} | {self.fill_count} fills | "
                 f"fees {self.total_fees:,.2f} | {self._rebuilds} rebuilds")
        for line in self.tracker.summary_lines():
            self.Log(line)
        for event in self.risk.events:
            self.Log(f"risk: {event}")
        self.Log("=" * 72)
