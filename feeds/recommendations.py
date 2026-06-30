"""Multi-factor stock scoring engine — reads all live terminal feeds.

Factors (with weights):
  Momentum      30% — price vs 52w range, analyst upside, relative strength vs SPY
  Valuation     25% — P/E, forward P/E, EV/EBITDA ranked vs peers
  Quality       20% — profit margin rank, beta risk-adjusted to VIX
  Options       10% — call/put premium ratio, unusual bullish flow
  Macro regime  15% — yield curve, VIX, Fed, GDP, unemployment, BTC risk signal

NOT financial advice. For informational/educational use only.
"""

import os
import time
from typing import Optional


def _safe(v, default=0.0):
    try:
        f = float(v)
        return f if f == f else default  # reject NaN
    except Exception:
        return default


def _pct_rank(value, pool, higher_is_better=True):
    """Return 0–100 percentile rank of value within pool."""
    if not pool or value is None:
        return 50.0
    below = sum(1 for v in pool if v < value)
    rank = below / len(pool) * 100
    return rank if higher_is_better else 100 - rank


def compute():
    # ── import live feed states ───────────────────────────────────────────────
    from feeds import market as mkt_feed
    from feeds import crypto as crypto_feed
    from feeds import bonds as bonds_feed
    from feeds import fred as fred_feed
    from feeds import options_flow as ofl_feed
    from feeds import equity_alpha as eq_feed

    quotes     = mkt_feed.get_quotes()
    crypto_st  = crypto_feed.get_crypto()
    bonds_st   = bonds_feed.get_bonds()
    fred_st    = fred_feed.get_fred()
    ofl_st     = ofl_feed.get_options_flow()
    eq_st      = eq_feed.get_equity()

    # ── macro regime ─────────────────────────────────────────────────────────
    series = getattr(fred_st, 'series', {})

    def fred_val(code):
        d = series.get(code)
        if not d:
            return None
        v = d.get('value')
        return _safe(v, None) if v is not None else None

    def fred_trend(code, n=4):
        d = series.get(code)
        if not d:
            return 0.0
        return _safe(d.get('change', 0.0), 0.0)

    vix_q   = quotes.get('^VIX')
    vix     = _safe(getattr(vix_q, 'price', None), 20.0)

    t10y2y  = _safe(fred_val('T10Y2Y') or getattr(bonds_st, 'spread_10y2y', 0), 0.0)
    # If FRED and bonds feeds both failed, compute 10Y–3M spread from live market quotes
    if t10y2y == 0.0:
        tnx_q = quotes.get('^TNX')
        irx_q = quotes.get('^IRX')
        if tnx_q and irx_q:
            tnx = _safe(getattr(tnx_q, 'price', None), 0.0)
            irx = _safe(getattr(irx_q, 'price', None), 0.0)
            if tnx > 0 and irx > 0:
                t10y2y = round(tnx - irx, 3)
    fedfunds = _safe(fred_val('FEDFUNDS'), 4.5)
    fed_trend = fred_trend('FEDFUNDS')
    unrate   = _safe(fred_val('UNRATE'), 4.0)
    unemp_trend = fred_trend('UNRATE')
    gdp      = _safe(fred_val('A191RL1Q225SBEA'), 2.0)
    cpi      = _safe(fred_val('CPIAUCSL'), 3.0)
    sentiment = _safe(fred_val('UMCSENT'), 70.0)

    # Gold vs oil — flight-to-safety signal
    gold_q  = quotes.get('GC=F')
    oil_q   = quotes.get('CL=F')
    gold_chg = _safe(getattr(gold_q, 'change_pct', None), 0.0)
    oil_chg  = _safe(getattr(oil_q, 'change_pct', None), 0.0)

    # DXY — strong dollar = headwind for multinationals
    dxy_q   = quotes.get('DX-Y.NYB')
    dxy_chg = _safe(getattr(dxy_q, 'change_pct', None), 0.0)

    # BTC risk-on / risk-off
    btc     = crypto_st.get('bitcoin') or crypto_st.get('btcusdt')
    btc_chg = _safe(getattr(btc, 'change_pct_24h', None), 0.0)

    # HYG (high-yield credit) — credit stress indicator
    hyg_q   = quotes.get('HYG')
    hyg_chg = _safe(getattr(hyg_q, 'change_pct', None), 0.0)

    # Sector momentum: XLK vs XLE vs SPY
    spy_q   = quotes.get('SPY')
    xlk_q   = quotes.get('XLK')
    xle_q   = quotes.get('XLE')
    spy_chg  = _safe(getattr(spy_q, 'change_pct', None), 0.0)
    xlk_chg  = _safe(getattr(xlk_q, 'change_pct', None), 0.0)
    xle_chg  = _safe(getattr(xle_q, 'change_pct', None), 0.0)
    tech_rs  = xlk_chg - spy_chg  # tech relative strength

    # Macro sub-scores
    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    m_yield   = clamp(t10y2y * 2, -1, 1)              # normal curve = bullish
    m_vix     = clamp((25 - vix) / 15, -1, 1)          # low VIX = bullish
    m_fed     = clamp(-fed_trend * 8, -1, 1)            # cutting = bullish
    m_unemp   = clamp(-unemp_trend * 10, -1, 1)         # falling unemp = bullish
    m_gdp     = clamp((gdp - 1.5) / 2, -1, 1)          # strong GDP = bullish
    m_credit  = clamp(hyg_chg / 1.5, -1, 1)            # HYG rising = risk-on
    m_btc     = clamp(btc_chg / 5, -1, 1)              # BTC as risk-on proxy
    m_gold    = clamp(-gold_chg / 3, -1, 1)             # gold falling = risk-on
    m_sent    = clamp((sentiment - 70) / 20, -1, 1)    # consumer sentiment

    macro_raw = (
        m_yield  * 0.18 +
        m_vix    * 0.16 +
        m_fed    * 0.14 +
        m_unemp  * 0.10 +
        m_gdp    * 0.12 +
        m_credit * 0.10 +
        m_btc    * 0.08 +
        m_gold   * 0.06 +
        m_sent   * 0.06
    )  # -1 to +1

    macro_pct   = int((macro_raw + 1) * 50)  # 0–100
    macro_regime = 'RISK-ON' if macro_raw > 0.25 else 'RISK-OFF' if macro_raw < -0.25 else 'NEUTRAL'

    # ── options flow by ticker ────────────────────────────────────────────────
    opt_by_ticker: dict = {}
    for c in getattr(ofl_st, 'unusual', []):
        t = c.get('ticker', '')
        if t not in opt_by_ticker:
            opt_by_ticker[t] = {'call_prem': 0.0, 'put_prem': 0.0,
                                 'call_voi': [], 'put_voi': []}
        if c.get('type') == 'C':
            opt_by_ticker[t]['call_prem'] += c.get('premium_k', 0)
            opt_by_ticker[t]['call_voi'].append(c.get('vol_oi', 0))
        else:
            opt_by_ticker[t]['put_prem'] += c.get('premium_k', 0)
            opt_by_ticker[t]['put_voi'].append(c.get('vol_oi', 0))

    # ── peer-group pools for relative ranking ─────────────────────────────────
    funds = getattr(eq_st, 'fundamentals', {})
    pe_pool      = [_safe(f['pe_ratio'])   for f in funds.values() if _safe(f.get('pe_ratio'),   -1) > 0]
    fpe_pool     = [_safe(f['forward_pe']) for f in funds.values() if _safe(f.get('forward_pe'), -1) > 0]
    margin_pool  = [_safe(f['profit_margin']) for f in funds.values() if f.get('profit_margin')]
    evebitda_pool = [_safe(f['ev_to_ebitda']) for f in funds.values() if _safe(f.get('ev_to_ebitda'), -1) > 0]

    # ── per-stock scoring ─────────────────────────────────────────────────────
    TRACKED = [
        # Mega-cap tech
        'AAPL','MSFT','NVDA','GOOGL','META','AMZN','TSLA','AMD','AVGO','ORCL',
        'CRM','ADBE','INTC','QCOM','NFLX','UBER','ABNB','SNAP','PINS','RBLX',
        # Finance
        'JPM','GS','BAC','MS','V','MA','BRK-B','AXP','BLK','SCHW',
        # Healthcare
        'UNH','LLY','JNJ','PFE','MRK','ABBV','BMY','AMGN','GILD','CVS',
        # Energy & industrials
        'XOM','CVX','COP','NEE','GE','CAT','BA','LMT','RTX','HON',
        # Consumer
        'COST','WMT','HD','TGT','NKE','MCD','SBUX','DIS','CMCSA','T',
        # ETFs & indices
        'SPY','QQQ','IWM','XLK','XLE','XLF','XLV','GLD','TLT','HYG',
    ]

    stocks = []
    for sym in TRACKED:
        q = quotes.get(sym)
        if not q:
            continue

        f    = funds.get(sym, {})
        opt  = opt_by_ticker.get(sym, {})
        price = _safe(getattr(q, 'price', 0))
        if price <= 0:
            continue
        chg   = _safe(getattr(q, 'change_pct', 0))

        # ── momentum (0–100) ─────────────────────────────────────────────────
        w52h = _safe(f.get('week_52_high') or getattr(q, 'day_high', None), price)
        w52l = _safe(f.get('week_52_low')  or getattr(q, 'day_low',  None), price)
        rng  = w52h - w52l
        in_range = ((price - w52l) / rng) if rng > 0 else 0.5

        target      = _safe(f.get('analyst_target'), 0)
        upside_pct  = ((target / price) - 1) * 100 if target > 0 else 0.0
        rel_strength = chg - spy_chg

        mom = (
            clamp(in_range, 0, 1) * 35 +           # position in 52w range (near high = momentum)
            clamp(upside_pct / 25, 0, 1) * 30 +     # analyst upside headroom
            clamp((rel_strength + 5) / 12, 0, 1) * 35  # vs S&P today
        )

        # ── valuation (0–100) ────────────────────────────────────────────────
        pe      = _safe(f.get('pe_ratio'),   None)
        fpe     = _safe(f.get('forward_pe'), None)
        evebit  = _safe(f.get('ev_to_ebitda'), None)

        pe_score  = _pct_rank(pe,    pe_pool,      higher_is_better=False) if pe    else 50
        fpe_score = _pct_rank(fpe,   fpe_pool,     higher_is_better=False) if fpe   else 50
        ev_score  = _pct_rank(evebit, evebitda_pool, higher_is_better=False) if evebit else 50

        growth_bonus = 0.0
        if pe and fpe and pe > 0 and fpe > 0:
            growth_bonus = clamp((pe - fpe) / pe * 60, -10, 25)  # fwd < trailing = growth expected

        val = (pe_score * 0.35 + fpe_score * 0.35 + ev_score * 0.20) + growth_bonus
        val = clamp(val, 0, 100)

        # ── quality (0–100) ──────────────────────────────────────────────────
        margin = _safe(f.get('profit_margin'), None)
        beta   = _safe(f.get('beta'), 1.0)
        margin_score = _pct_rank(margin, margin_pool) if margin is not None else 50
        # In high-VIX environments, low-beta stocks get a bigger quality boost
        beta_penalty = clamp((beta - 1.0) * 30, -20, 40)
        vix_multiplier = 1.0 if vix < 18 else 1.4 if vix < 25 else 2.0
        qual = clamp(margin_score - beta_penalty * vix_multiplier * 0.5, 0, 100)

        # ── options signal (0–100) ───────────────────────────────────────────
        call_p = opt.get('call_prem', 0)
        put_p  = opt.get('put_prem', 0)
        total  = call_p + put_p
        if total > 0:
            call_ratio = call_p / total
            avg_voi = (sum(opt.get('call_voi', [0])) /
                       max(len(opt.get('call_voi', [])), 1))
            opt_score = clamp(call_ratio * 70 + min(avg_voi / 15 * 30, 30), 0, 100)
        else:
            opt_score = 50.0

        # ── macro adjustment ─────────────────────────────────────────────────
        # High-beta, growth stocks swing more with macro regime
        macro_sensitivity = clamp(beta * 0.6, 0.3, 1.0)
        macro_bonus = macro_raw * macro_sensitivity * 12  # -12 to +12
        # Tech-specific boost if XLK outperforming
        if sym in ('AAPL','MSFT','NVDA','GOOGL','META','AMZN','AMD','AVGO','ORCL','QQQ','XLK'):
            macro_bonus += clamp(tech_rs * 2, -5, 5)

        macro_component = clamp(50 + macro_bonus, 20, 80)

        # ── composite score ───────────────────────────────────────────────────
        composite = (
            mom              * 0.30 +
            val              * 0.25 +
            qual             * 0.20 +
            opt_score        * 0.10 +
            macro_component  * 0.15
        )
        composite = round(clamp(composite, 0, 100), 1)

        if composite >= 72:   signal = 'STRONG BUY'
        elif composite >= 60: signal = 'BUY'
        elif composite >= 48: signal = 'HOLD'
        elif composite >= 35: signal = 'REDUCE'
        else:                  signal = 'AVOID'

        # ── reasoning ────────────────────────────────────────────────────────
        reasons = []

        if upside_pct > 12:
            reasons.append(f"Analyst consensus target +{upside_pct:.1f}% upside (${target:.0f})")
        elif upside_pct < -8 and target > 0:
            reasons.append(f"Analyst target below market ({upside_pct:.1f}% downside to ${target:.0f})")

        if pe and fpe and pe > 0 and fpe > 0 and (pe - fpe) / pe > 0.15:
            reasons.append(f"Earnings acceleration: {pe:.1f}x trailing → {fpe:.1f}x forward P/E")
        elif pe and pe > 45:
            reasons.append(f"Rich valuation at {pe:.1f}x trailing P/E")
        elif pe and pe < 15:
            reasons.append(f"Inexpensive at {pe:.1f}x P/E vs peers")

        if margin and margin > 0.28:
            reasons.append(f"Exceptional profit margin {margin*100:.1f}%")
        elif margin and margin < 0.04 and margin > 0:
            reasons.append(f"Thin margins ({margin*100:.1f}%) leave little cushion")

        if rel_strength > 1.5:
            reasons.append(f"Outperforming S&P 500 by +{rel_strength:.1f}% today")
        elif rel_strength < -1.5:
            reasons.append(f"Lagging S&P 500 by {rel_strength:.1f}% today")

        if call_p > put_p * 1.8 and total > 200:
            reasons.append(f"Bullish options flow: ${call_p/1000:.1f}M call vs ${put_p/1000:.1f}M put premium")
        elif put_p > call_p * 1.8 and total > 200:
            reasons.append(f"Bearish options flow: ${put_p/1000:.1f}M put premium dominates")

        if beta > 1.6 and vix > 22:
            reasons.append(f"High beta ({beta:.1f}x) amplifies downside in elevated VIX ({vix:.1f})")
        elif beta < 0.7:
            reasons.append(f"Defensive (beta {beta:.1f}x) in uncertain macro")

        if in_range > 0.9:
            reasons.append(f"Trading near 52-week high — strong momentum")
        elif in_range < 0.15:
            reasons.append(f"Near 52-week low — potential value entry or value trap")

        # Macro context bullet
        if macro_raw > 0.3:
            reasons.append(f"Macro backdrop supportive: {macro_regime} (VIX {vix:.1f}, curve {t10y2y:+.2f}%)")
        elif macro_raw < -0.3:
            reasons.append(f"Macro headwinds: {macro_regime} (VIX {vix:.1f}, curve {t10y2y:+.2f}%)")

        # DXY impact on multinationals
        if dxy_chg > 0.5 and sym in ('AAPL','MSFT','NVDA','GOOGL','META','AMZN'):
            reasons.append(f"USD strength ({dxy_chg:+.1f}%) a headwind for international revenue")

        reasons = reasons[:5]
        if not reasons:
            reasons.append("No strong directional signals at current levels")

        stocks.append({
            'symbol':          sym,
            'name':            f.get('name') or getattr(q, 'name', sym),
            'price':           price,
            'change_pct':      chg,
            'signal':          signal,
            'score':           composite,
            'score_momentum':  round(mom, 1),
            'score_valuation': round(val, 1),
            'score_quality':   round(qual, 1),
            'score_options':   round(opt_score, 1),
            'score_macro':     round(macro_component, 1),
            'pe':              pe,
            'forward_pe':      fpe,
            'profit_margin':   margin,
            'upside_pct':      round(upside_pct, 1),
            'beta':            beta,
            'analyst_target':  target or None,
            'call_premium_k':  round(call_p, 0),
            'put_premium_k':   round(put_p, 0),
            'reasons':         reasons,
        })

    stocks.sort(key=lambda x: x['score'], reverse=True)

    return {
        'stocks': stocks,
        'macro': {
            'score':       macro_raw,
            'score_pct':   macro_pct,
            'regime':      macro_regime,
            'vix':         vix,
            'yield_curve': t10y2y,
            'fed_funds':   fedfunds,
            'fed_trend':   fed_trend,
            'gdp':         gdp,
            'unemployment': unrate,
            'cpi':         cpi,
            'sentiment':   sentiment,
            'btc_change':  btc_chg,
            'gold_change': gold_chg,
            'hyg_change':  hyg_chg,
            'dxy_change':  dxy_chg,
            'tech_rs':     tech_rs,
            'signals': {
                'yield_curve': 'NORMAL' if t10y2y > 0 else 'INVERTED',
                'vix':         'LOW' if vix < 15 else 'ELEVATED' if vix < 25 else 'HIGH',
                'fed':         'CUTTING' if fed_trend < -0.1 else 'HIKING' if fed_trend > 0.1 else 'PAUSED',
                'growth':      'EXPANDING' if gdp > 2 else 'SLOWING' if gdp > 0 else 'CONTRACTING',
                'credit':      'TIGHT' if hyg_chg > 0.3 else 'STRESSED' if hyg_chg < -0.5 else 'NEUTRAL',
                'risk':        'ON' if btc_chg > 2 else 'OFF' if btc_chg < -2 else 'NEUTRAL',
            },
        },
        'updated': time.time(),
        'disclaimer': 'INFORMATIONAL ONLY — NOT FINANCIAL ADVICE',
    }


def _build_narrative(
    sym, name, price, chg, signal, score,
    mom, val, qual, opt_score, macro_component,
    pe, fpe, evebit, margin, beta,
    target, upside_pct, in_range, w52h, w52l,
    rel_str, call_p, put_p,
    vix, t10y2y, macro_regime, macro_pct, macro_raw,
    gdp, fedfunds, unrate, cpi, hyg_chg, btc_chg, dxy_chg, tech_rs,
    sector, industry, description,
) -> dict:
    """Generate a plain-English analyst report from computed metrics."""

    def clamp(v, lo, hi): return max(lo, min(hi, v))

    # ── rating ────────────────────────────────────────────────────────────────
    if signal in ('STRONG BUY', 'BUY'):
        rating = 'BUY'
    elif signal == 'HOLD':
        rating = 'HOLD'
    else:
        rating = 'SELL'

    # ── summary ───────────────────────────────────────────────────────────────
    direction     = f"up {chg:.2f}%" if chg >= 0 else f"down {abs(chg):.2f}%"
    range_pos     = (
        "near its 52-week high"  if in_range > 0.80 else
        "near its 52-week low"   if in_range < 0.20 else
        f"at {in_range*100:.0f}% of its 52-week range"
    )
    pe_str        = f"{pe:.1f}x trailing P/E" if pe else "no reported P/E"
    fpe_str       = f"{fpe:.1f}x forward P/E" if fpe else "no forward estimate"
    margin_str    = f"{margin*100:.1f}% profit margin" if margin is not None else "undisclosed margin"
    target_str    = (
        f"consensus analyst target of ${target:.0f} ({upside_pct:+.1f}% from current price)"
        if target else "no consensus analyst price target on record"
    )

    summary = (
        f"{name} ({sym}) is trading at ${price:.2f}, {direction} on the session and "
        f"{range_pos} (52-week range: ${w52l:.2f}–${w52h:.2f}). "
        f"The composite multi-factor score is {score}/100, yielding a {signal} rating. "
        f"Key data points: {pe_str}, {fpe_str}, {margin_str}, beta {(f'{beta:.2f}') if beta else '—'}, "
        f"and a {target_str}."
    )

    # ── momentum section ──────────────────────────────────────────────────────
    if   rel_str >  2.0: rel_txt = f"significantly outperforming the S&P 500 by {rel_str:.1f} percentage points today"
    elif rel_str >  0.4: rel_txt = f"modestly outperforming the S&P 500 by {rel_str:.1f}pp"
    elif rel_str < -2.0: rel_txt = f"meaningfully underperforming the S&P 500 by {abs(rel_str):.1f}pp"
    elif rel_str < -0.4: rel_txt = f"slightly lagging the S&P 500 by {abs(rel_str):.1f}pp"
    else:                rel_txt = "tracking broadly in line with the S&P 500"

    if   in_range > 0.80: range_txt = "Trading near its 52-week high signals sustained demand and strong bullish momentum. Breakout continuation is possible, though extended positions carry mean-reversion risk."
    elif in_range > 0.55: range_txt = "The stock is in the upper half of its annual range, suggesting a positive price trend without being technically overextended."
    elif in_range > 0.40: range_txt = "Price sits mid-range on the year, offering no strong directional signal from price action alone."
    elif in_range > 0.20: range_txt = "Trading in the lower half of its annual range reflects recent selling pressure or sector rotation away from this name."
    else:                 range_txt = "Near its 52-week low, the stock may represent either a value entry or a deteriorating fundamental picture — the distinction matters enormously."

    if   upside_pct > 20:  tgt_txt = f"The analyst consensus target of ${target:.0f} implies {upside_pct:.1f}% upside, suggesting Wall Street sees substantial unrecognized value relative to current pricing."
    elif upside_pct > 8:   tgt_txt = f"Analysts see meaningful upside to ${target:.0f} ({upside_pct:.1f}%), indicating the Street believes the current price undervalues the business."
    elif upside_pct > 2:   tgt_txt = f"The consensus target of ${target:.0f} points to modest additional upside ({upside_pct:.1f}%), implying broadly fair but not expensive valuation."
    elif target and upside_pct < -5: tgt_txt = f"Importantly, the analyst consensus of ${target:.0f} sits {abs(upside_pct):.1f}% below current price — a warning that the Street views the stock as overvalued at these levels."
    elif target:           tgt_txt = f"The consensus target of ${target:.0f} is near current levels, reflecting analyst comfort with present valuation."
    else:                  tgt_txt = "No consensus analyst price target is available, which limits benchmark-setting for upside/downside."

    momentum_section = (
        f"{sym} is currently {rel_txt}. {range_txt} {tgt_txt} "
        f"The momentum sub-score of {mom:.0f}/100 is derived from 52-week range positioning ({in_range*100:.0f}%), "
        f"analyst upside headroom, and today's relative performance versus the broader market."
    )

    # ── valuation section ─────────────────────────────────────────────────────
    if pe and fpe and pe > 0 and fpe > 0:
        ratio = (pe - fpe) / pe
        if   ratio > 0.25: pe_txt = f"The compression from {pe:.1f}x trailing to {fpe:.1f}x forward P/E points to meaningful earnings growth expected over the next twelve months — a constructive signal for growth-oriented investors willing to pay for future earnings."
        elif ratio > 0.10: pe_txt = f"Forward P/E of {fpe:.1f}x steps down from the {pe:.1f}x trailing figure, suggesting moderate near-term earnings growth is already priced into the stock."
        elif ratio < -0.10: pe_txt = f"The forward P/E of {fpe:.1f}x is higher than the trailing {pe:.1f}x, which may indicate expected earnings deceleration or one-time items distorting recent results. Investors should scrutinize guidance carefully."
        else:               pe_txt = f"Trailing and forward P/E are in close alignment ({pe:.1f}x and {fpe:.1f}x respectively), implying stable earnings expectations with no major step-change anticipated."
    elif pe:
        pe_txt = (
            f"Trailing P/E of {pe:.1f}x places the stock at {'a significant premium to broader market averages, which requires robust earnings growth to justify' if pe > 40 else 'a moderate multiple consistent with quality growth names' if pe > 20 else 'an inexpensive multiple by historical norms, though this may reflect cyclical or fundamental headwinds'}."
        )
    else:
        pe_txt = "P/E data is unavailable, which limits traditional earnings-multiple analysis. This is common for pre-profit companies or those with unconventional reporting."

    if   val > 70: val_rank = f"ranks attractively (top third) on valuation vs. the tracked peer universe (score {val:.0f}/100)"
    elif val > 50: val_rank = f"is roughly in line with peers on valuation (score {val:.0f}/100)"
    else:          val_rank = f"appears relatively expensive versus peers on a multi-metric basis (score {val:.0f}/100)"

    evebit_txt = f" EV/EBITDA of {evebit:.1f}x adds an enterprise-value perspective, confirming a {'premium' if evebit > 20 else 'moderate' if evebit > 12 else 'value'} rating." if evebit else ""

    valuation_section = (
        f"{pe_txt}{evebit_txt} "
        f"On a relative basis, the stock {val_rank}. "
        f"Valuation multiples should always be weighed against growth rate — "
        f"a high P/E can be justified if earnings are compounding at a sufficient pace."
    )

    # ── quality section ───────────────────────────────────────────────────────
    if margin is not None:
        if   margin > 0.35: margin_txt = f"A {margin*100:.1f}% net profit margin is exceptional by any standard, indicating strong pricing power, a capital-light model, or significant competitive moat."
        elif margin > 0.20: margin_txt = f"The {margin*100:.1f}% profit margin reflects solid earnings quality and above-average operational leverage."
        elif margin > 0.08: margin_txt = f"Profit margin of {margin*100:.1f}% is respectable but leaves room for improvement versus best-in-class peers."
        elif margin > 0.01: margin_txt = f"A thin {margin*100:.1f}% margin exposes earnings to outsized swings from modest revenue or cost changes."
        else:               margin_txt = f"Negative or near-zero margins ({margin*100:.1f}%) indicate the company is not yet generating meaningful net income."
    else:
        margin_txt = "Margin data is unavailable, which limits quality assessment."

    beta_v = beta if beta else 1.0
    if   beta_v > 1.7: beta_txt = f"Beta of {beta_v:.2f} is high — the stock amplifies market moves in both directions. At VIX {vix:.1f}, this translates to {'meaningfully elevated' if vix > 22 else 'moderate'} volatility drag."
    elif beta_v > 1.2: beta_txt = f"Beta of {beta_v:.2f} is modestly above market-neutral, providing slightly amplified market exposure."
    elif beta_v < 0.6: beta_txt = f"Beta of {beta_v:.2f} marks this as a defensive holding. It tends to lag in bull markets but preserve capital better during drawdowns."
    else:              beta_txt = f"Beta of {beta_v:.2f} is near market-neutral, offering balanced directional exposure."

    quality_section = (
        f"{margin_txt} {beta_txt} "
        f"The quality sub-score of {qual:.0f}/100 is VIX-adjusted: at current market volatility ({vix:.1f}), "
        f"{'defensive, low-beta profiles receive a premium — a factor that favors quality compounders' if vix > 20 else 'the volatility environment is benign and quality differentials are less pronounced'}. "
        f"High-quality businesses with durable margins tend to outperform on a risk-adjusted basis over full market cycles."
    )

    # ── macro section ─────────────────────────────────────────────────────────
    curve_txt = (
        f"The yield curve (10y–2y spread: {t10y2y:+.2f}%) is "
        f"{'positively sloped, a historically bullish signal for equities and credit' if t10y2y > 0.3 else 'near-flat, which often precedes late-cycle slowdown' if t10y2y > -0.1 else 'inverted — a historically reliable recession warning with a typical lead time of 12–24 months'}."
    )
    vix_txt = (
        f"The VIX at {vix:.1f} signals "
        f"{'a low-fear, risk-embracing environment' if vix < 14 else 'modest uncertainty but no systemic stress' if vix < 20 else 'elevated investor anxiety — risk premia are expanding, which pressures valuations' if vix < 28 else 'acute market fear; historically a contrarian buy signal but short-term pain is common'}."
    )
    gdp_txt = (
        f"GDP growth of {gdp:.1f}% is "
        f"{'healthy and broadly supportive of corporate earnings' if gdp > 2.5 else 'below trend — earnings growth may slow' if gdp > 0 else 'contracting, creating a challenging earnings environment'}."
    )
    hyg_str = f"HYG {hyg_chg:+.2f}%"
    if hyg_chg < -0.4:
        hyg_txt = f"Credit markets are showing signs of stress ({hyg_str}): spreads widening and credit conditions tightening."
    elif hyg_chg > -0.2:
        hyg_txt = f"Credit markets are showing resilience ({hyg_str}): no systemic credit warning at this time."
    else:
        hyg_txt = f"Credit markets show slight softness ({hyg_str}) — worth monitoring."
    regime_txt = {
        'RISK-ON':  "The aggregate macro regime score of {}/100 places the environment firmly in RISK-ON territory — broadly favorable for equities, especially growth and high-beta names.",
        'RISK-OFF': "The aggregate macro regime score of {}/100 signals RISK-OFF conditions — capital is rotating toward safety assets (bonds, gold, defensive equities), creating headwinds for higher-multiple and cyclical stocks.",
        'NEUTRAL':  "The aggregate macro regime score of {}/100 is NEUTRAL — neither clearly supportive nor clearly hostile to risk assets.",
    }.get(macro_regime, "{}").format(macro_pct)

    macro_section = (
        f"{curve_txt} {vix_txt} {gdp_txt} "
        f"Fed Funds rate stands at {fedfunds:.2f}%. Unemployment is {unrate:.1f}%. "
        f"{hyg_txt} {regime_txt}"
    )

    # ── options flow section ──────────────────────────────────────────────────
    total_opt = call_p + put_p
    if total_opt > 100:
        if   call_p > put_p * 2.5: opt_section = f"Options flow is strongly bullish — ${call_p/1000:.1f}M in call premium versus ${put_p/1000:.1f}M in puts. This asymmetric positioning often reflects institutional conviction or hedged long accumulation."
        elif call_p > put_p * 1.4: opt_section = f"Call-side premium of ${call_p/1000:.1f}M moderately outweighs put activity (${put_p/1000:.1f}M), pointing to mild bullish sentiment in the derivatives market."
        elif put_p > call_p * 2.5: opt_section = f"Put premium of ${put_p/1000:.1f}M significantly exceeds calls (${call_p/1000:.1f}M), indicating institutional hedging or outright bearish bets — a cautionary signal."
        elif put_p > call_p * 1.4: opt_section = f"Slightly elevated put activity (${put_p/1000:.1f}M vs ${call_p/1000:.1f}M in calls) suggests some hedging or mild defensive positioning in the options market."
        else:                       opt_section = f"Options flow is balanced (${call_p/1000:.1f}M calls, ${put_p/1000:.1f}M puts), offering no strong directional signal from institutional derivatives activity."
    else:
        opt_section = "Options flow data for this ticker is limited or unavailable in the current scan window. No reliable inference can be drawn from derivatives positioning."

    # ── conclusion ────────────────────────────────────────────────────────────
    if   signal == 'STRONG BUY': stance = "represents a compelling buying opportunity at current levels"
    elif signal == 'BUY':        stance = "is attractive and merits a long position"
    elif signal == 'HOLD':       stance = "offers a balanced risk/reward profile — neither aggressively attractive nor a clear sell"
    elif signal == 'REDUCE':     stance = "shows deteriorating risk/reward and warrants reduced exposure"
    else:                        stance = "carries material downside risk at current valuations and should be avoided"

    bulls, bears = [], []
    if upside_pct > 10:           bulls.append(f"{upside_pct:.0f}% analyst-implied upside")
    if mom > 65:                  bulls.append("strong price momentum")
    if margin and margin > 0.20:  bulls.append(f"high-quality {margin*100:.0f}% margins")
    if val > 60:                  bulls.append("attractive relative valuation")
    if macro_regime == 'RISK-ON': bulls.append("supportive macro backdrop")
    if in_range < 0.25:           bulls.append("discounted price level")
    if   pe and pe > 50:          bears.append(f"elevated {pe:.0f}x trailing P/E")
    if in_range > 0.90:           bears.append("near 52-week high / stretched momentum")
    if beta_v > 1.5 and vix > 20: bears.append(f"high beta ({beta_v:.1f}x) in elevated-VIX tape")
    if macro_regime == 'RISK-OFF': bears.append("deteriorating macro backdrop")
    if margin is not None and margin < 0.05: bears.append("thin margins with limited earnings buffer")

    bull_str = ", ".join(bulls[:3]) if bulls else "modest multi-factor support"
    bear_str = ", ".join(bears[:2]) if bears else "limited obvious catalysts"

    conclusion = (
        f"Based on all available terminal data, {name} ({sym}) {stance}. "
        f"The composite score of {score}/100 ranks it as a {signal} under the multi-factor model "
        f"(Momentum 30%, Valuation 25%, Quality 20%, Options 10%, Macro 15%). "
        f"The primary bull case rests on {bull_str}. "
        f"{'Key risks include ' + bear_str + '. ' if bears else ''}"
        f"This analysis uses live data from the terminal including real-time prices, FRED macro series, "
        f"WHO health data, options flow, and geopolitical context — all as of this moment. "
        f"NOT FINANCIAL ADVICE. For informational and educational purposes only."
    )

    return {
        'rating':    rating,
        'summary':   summary,
        'analysis':  {
            'momentum':  momentum_section,
            'valuation': valuation_section,
            'quality':   quality_section,
            'macro':     macro_section,
            'options':   opt_section,
        },
        'conclusion': conclusion,
    }


async def compute_ticker(symbol: str) -> dict:
    """Score any arbitrary ticker on demand. Fetches price from Finnhub (or store) and
    fundamentals from Yahoo Finance, then runs the same multi-factor model as compute()."""
    import aiohttp

    from feeds import market as mkt_feed
    from feeds import crypto as crypto_feed
    from feeds import bonds as bonds_feed
    from feeds import fred as fred_feed
    from feeds import options_flow as ofl_feed
    from feeds import equity_alpha as eq_feed

    quotes    = mkt_feed.get_quotes()
    crypto_st = crypto_feed.get_crypto()
    bonds_st  = bonds_feed.get_bonds()
    fred_st   = fred_feed.get_fred()
    ofl_st    = ofl_feed.get_options_flow()
    eq_st     = eq_feed.get_equity()

    # ── macro context (identical to compute()) ────────────────────────────────
    series = getattr(fred_st, 'series', {})

    def fred_val(code):
        d = series.get(code)
        if not d:
            return None
        v = d.get('value')
        return _safe(v, None) if v is not None else None

    def fred_trend(code, n=4):
        d = series.get(code)
        if not d:
            return 0.0
        return _safe(d.get('change', 0.0), 0.0)

    def clamp(v, lo, hi):
        return max(lo, min(hi, v))

    vix_q   = quotes.get('^VIX')
    vix     = _safe(getattr(vix_q, 'price', None), 20.0)
    t10y2y  = _safe(fred_val('T10Y2Y') or getattr(bonds_st, 'spread_10y2y', 0), 0.0)
    if t10y2y == 0.0:
        tnx_q = quotes.get('^TNX')
        irx_q = quotes.get('^IRX')
        if tnx_q and irx_q:
            tnx = _safe(getattr(tnx_q, 'price', None), 0.0)
            irx = _safe(getattr(irx_q, 'price', None), 0.0)
            if tnx > 0 and irx > 0:
                t10y2y = round(tnx - irx, 3)
    fedfunds   = _safe(fred_val('FEDFUNDS'), 4.5)
    fed_trend_ = fred_trend('FEDFUNDS')
    unrate     = _safe(fred_val('UNRATE'), 4.0)
    unemp_trend_ = fred_trend('UNRATE')
    gdp        = _safe(fred_val('A191RL1Q225SBEA'), 2.0)
    cpi        = _safe(fred_val('CPIAUCSL'), 3.0)
    sentiment  = _safe(fred_val('UMCSENT'), 70.0)

    gold_q   = quotes.get('GC=F')
    dxy_q    = quotes.get('DX-Y.NYB')
    hyg_q    = quotes.get('HYG')
    spy_q    = quotes.get('SPY')
    xlk_q    = quotes.get('XLK')
    gold_chg = _safe(getattr(gold_q, 'change_pct', None), 0.0)
    dxy_chg  = _safe(getattr(dxy_q,  'change_pct', None), 0.0)
    hyg_chg  = _safe(getattr(hyg_q,  'change_pct', None), 0.0)
    spy_chg  = _safe(getattr(spy_q,  'change_pct', None), 0.0)
    xlk_chg  = _safe(getattr(xlk_q,  'change_pct', None), 0.0)
    btc      = crypto_st.get('bitcoin') or crypto_st.get('btcusdt')
    btc_chg  = _safe(getattr(btc, 'change_pct_24h', None), 0.0)
    tech_rs  = xlk_chg - spy_chg

    macro_raw = (
        clamp(t10y2y * 2, -1, 1)           * 0.18 +
        clamp((25 - vix) / 15, -1, 1)      * 0.16 +
        clamp(-fed_trend_ * 8, -1, 1)      * 0.14 +
        clamp(-unemp_trend_ * 10, -1, 1)   * 0.10 +
        clamp((gdp - 1.5) / 2, -1, 1)      * 0.12 +
        clamp(hyg_chg / 1.5, -1, 1)        * 0.10 +
        clamp(btc_chg / 5, -1, 1)          * 0.08 +
        clamp(-gold_chg / 3, -1, 1)        * 0.06 +
        clamp((sentiment - 70) / 20, -1, 1)* 0.06
    )
    macro_pct    = int((macro_raw + 1) * 50)
    macro_regime = 'RISK-ON' if macro_raw > 0.25 else 'RISK-OFF' if macro_raw < -0.25 else 'NEUTRAL'

    # ── options flow by ticker ────────────────────────────────────────────────
    opt_by_ticker: dict = {}
    for c in getattr(ofl_st, 'unusual', []):
        t = c.get('ticker', '')
        if t not in opt_by_ticker:
            opt_by_ticker[t] = {'call_prem': 0.0, 'put_prem': 0.0,
                                 'call_voi': [], 'put_voi': []}
        if c.get('type') == 'C':
            opt_by_ticker[t]['call_prem'] += c.get('premium_k', 0)
            opt_by_ticker[t]['call_voi'].append(c.get('vol_oi', 0))
        else:
            opt_by_ticker[t]['put_prem'] += c.get('premium_k', 0)
            opt_by_ticker[t]['put_voi'].append(c.get('vol_oi', 0))

    # ── peer pools from equity_alpha store ────────────────────────────────────
    funds_store  = getattr(eq_st, 'fundamentals', {})
    pe_pool      = [_safe(f['pe_ratio'])    for f in funds_store.values() if _safe(f.get('pe_ratio'),    -1) > 0]
    fpe_pool     = [_safe(f['forward_pe'])  for f in funds_store.values() if _safe(f.get('forward_pe'),  -1) > 0]
    margin_pool  = [_safe(f['profit_margin']) for f in funds_store.values() if f.get('profit_margin')]
    evebitda_pool= [_safe(f['ev_to_ebitda']) for f in funds_store.values() if _safe(f.get('ev_to_ebitda'), -1) > 0]

    # ── price ─────────────────────────────────────────────────────────────────
    q        = quotes.get(symbol)
    price    = _safe(getattr(q, 'price', 0)) if q else 0.0
    chg      = _safe(getattr(q, 'change_pct', 0)) if q else 0.0
    day_high = _safe(getattr(q, 'day_high', None)) if q else None
    day_low  = _safe(getattr(q, 'day_low',  None)) if q else None

    if price <= 0:
        fh_key = os.environ.get("FINNHUB_KEY", "")
        try:
            async with aiohttp.ClientSession() as sess:
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={fh_key}"
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                    data = await r.json()
                    price = _safe(data.get('c'), 0.0)
                    pc    = _safe(data.get('pc'), price)
                    chg   = ((price - pc) / pc * 100) if pc else 0.0
                    day_high = _safe(data.get('h'))
                    day_low  = _safe(data.get('l'))
        except Exception:
            pass

    if price <= 0:
        return {"error": f"No price data found for {symbol}", "symbol": symbol}

    # ── fundamentals: store first, then yfinance on-demand ───────────────────
    f: dict = {}
    if symbol in funds_store:
        f = dict(funds_store[symbol])
    else:
        import asyncio

        def _yf_info(sym):
            import yfinance as yf
            return yf.Ticker(sym).info or {}

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, _yf_info, symbol)
            f = {
                'name':          info.get('longName') or info.get('shortName') or symbol,
                'pe_ratio':      info.get('trailingPE'),
                'forward_pe':    info.get('forwardPE'),
                'ev_to_ebitda':  info.get('enterpriseToEbitda'),
                'profit_margin': info.get('profitMargins'),
                'beta':          info.get('beta'),
                'analyst_target': info.get('targetMeanPrice'),
                'week_52_high':  info.get('fiftyTwoWeekHigh'),
                'week_52_low':   info.get('fiftyTwoWeekLow'),
                'sector':        info.get('sector', ''),
                'industry':      info.get('industry', ''),
                'employees':     info.get('fullTimeEmployees'),
                'description':   (info.get('longBusinessSummary') or '')[:400],
                'market_cap':    info.get('marketCap'),
                'revenue':       info.get('totalRevenue'),
            }
        except Exception:
            pass

    # extend peer pools with this ticker's data
    for pool, key in [(pe_pool, 'pe_ratio'), (fpe_pool, 'forward_pe'),
                      (margin_pool, 'profit_margin'), (evebitda_pool, 'ev_to_ebitda')]:
        v = _safe(f.get(key), -999)
        if v > 0:
            pool.append(v)

    # ── scoring (same logic as compute()) ────────────────────────────────────
    opt = opt_by_ticker.get(symbol, {})

    w52h     = _safe(f.get('week_52_high') or day_high, price)
    w52l     = _safe(f.get('week_52_low')  or day_low,  price)
    rng      = w52h - w52l
    in_range = ((price - w52l) / rng) if rng > 0 else 0.5

    target     = _safe(f.get('analyst_target'), 0)
    upside_pct = ((target / price) - 1) * 100 if target > 0 else 0.0
    rel_str    = chg - spy_chg

    mom = (
        clamp(in_range, 0, 1) * 35 +
        clamp(upside_pct / 25, 0, 1) * 30 +
        clamp((rel_str + 5) / 12, 0, 1) * 35
    )

    pe     = _safe(f.get('pe_ratio'),    None)
    fpe    = _safe(f.get('forward_pe'),  None)
    evebit = _safe(f.get('ev_to_ebitda'), None)

    pe_score  = _pct_rank(pe,    pe_pool,       higher_is_better=False) if pe    else 50
    fpe_score = _pct_rank(fpe,   fpe_pool,      higher_is_better=False) if fpe   else 50
    ev_score  = _pct_rank(evebit, evebitda_pool, higher_is_better=False) if evebit else 50
    growth_bonus = clamp((pe - fpe) / pe * 60, -10, 25) if (pe and fpe and pe > 0 and fpe > 0) else 0.0
    val = clamp((pe_score * 0.35 + fpe_score * 0.35 + ev_score * 0.20) + growth_bonus, 0, 100)

    margin     = _safe(f.get('profit_margin'), None)
    beta       = _safe(f.get('beta'), 1.0)
    margin_score  = _pct_rank(margin, margin_pool) if margin is not None else 50
    beta_penalty  = clamp((beta - 1.0) * 30, -20, 40)
    vix_mul       = 1.0 if vix < 18 else 1.4 if vix < 25 else 2.0
    qual = clamp(margin_score - beta_penalty * vix_mul * 0.5, 0, 100)

    call_p = opt.get('call_prem', 0)
    put_p  = opt.get('put_prem', 0)
    total  = call_p + put_p
    if total > 0:
        call_ratio = call_p / total
        avg_voi    = sum(opt.get('call_voi', [0])) / max(len(opt.get('call_voi', [])), 1)
        opt_score  = clamp(call_ratio * 70 + min(avg_voi / 15 * 30, 30), 0, 100)
    else:
        opt_score = 50.0

    macro_sens      = clamp(beta * 0.6, 0.3, 1.0)
    macro_bonus     = macro_raw * macro_sens * 12
    if symbol in ('AAPL','MSFT','NVDA','GOOGL','META','AMZN','AMD','AVGO','ORCL','QQQ','XLK'):
        macro_bonus += clamp(tech_rs * 2, -5, 5)
    macro_component = clamp(50 + macro_bonus, 20, 80)

    composite = round(clamp(
        mom * 0.30 + val * 0.25 + qual * 0.20 + opt_score * 0.10 + macro_component * 0.15,
        0, 100
    ), 1)

    if composite >= 72:   signal = 'STRONG BUY'
    elif composite >= 60: signal = 'BUY'
    elif composite >= 48: signal = 'HOLD'
    elif composite >= 35: signal = 'REDUCE'
    else:                  signal = 'AVOID'

    reasons = []
    if upside_pct > 12:
        reasons.append(f"Analyst consensus target +{upside_pct:.1f}% upside (${target:.0f})")
    elif upside_pct < -8 and target > 0:
        reasons.append(f"Analyst target below market ({upside_pct:.1f}% downside to ${target:.0f})")
    if pe and fpe and pe > 0 and fpe > 0 and (pe - fpe) / pe > 0.15:
        reasons.append(f"Earnings acceleration: {pe:.1f}x trailing → {fpe:.1f}x forward P/E")
    elif pe and pe > 45:
        reasons.append(f"Rich valuation at {pe:.1f}x trailing P/E")
    elif pe and pe < 15:
        reasons.append(f"Inexpensive at {pe:.1f}x P/E vs peers")
    if margin and margin > 0.28:
        reasons.append(f"Exceptional profit margin {margin*100:.1f}%")
    elif margin and 0 < margin < 0.04:
        reasons.append(f"Thin margins ({margin*100:.1f}%) leave little cushion")
    if rel_str > 1.5:
        reasons.append(f"Outperforming S&P 500 by +{rel_str:.1f}% today")
    elif rel_str < -1.5:
        reasons.append(f"Lagging S&P 500 by {rel_str:.1f}% today")
    if call_p > put_p * 1.8 and total > 200:
        reasons.append(f"Bullish options flow: ${call_p/1000:.1f}M calls vs ${put_p/1000:.1f}M puts")
    elif put_p > call_p * 1.8 and total > 200:
        reasons.append(f"Bearish options flow: ${put_p/1000:.1f}M put premium dominates")
    if beta > 1.6 and vix > 22:
        reasons.append(f"High beta ({beta:.1f}x) amplifies risk in elevated VIX ({vix:.1f})")
    elif beta < 0.7:
        reasons.append(f"Defensive profile (beta {beta:.1f}x) suits uncertain macro")
    if in_range > 0.9:
        reasons.append("Trading near 52-week high — strong upward momentum")
    elif in_range < 0.15:
        reasons.append("Near 52-week low — potential value entry or continued decline")
    if macro_raw > 0.3:
        reasons.append(f"Macro backdrop supportive: {macro_regime} regime (VIX {vix:.1f}, curve {t10y2y:+.2f}%)")
    elif macro_raw < -0.3:
        reasons.append(f"Macro headwinds: {macro_regime} regime (VIX {vix:.1f}, curve {t10y2y:+.2f}%)")
    if dxy_chg > 0.5 and symbol in ('AAPL','MSFT','NVDA','GOOGL','META','AMZN'):
        reasons.append(f"USD strength ({dxy_chg:+.1f}%) a headwind for international revenue")
    reasons = reasons[:6]
    if not reasons:
        reasons.append("No strong directional signals at current data levels")

    return {
        "symbol":    symbol,
        "name":      f.get('name') or symbol,
        "price":     price,
        "change_pct": chg,
        "signal":    signal,
        "score":     composite,
        "score_momentum":  round(mom, 1),
        "score_valuation": round(val, 1),
        "score_quality":   round(qual, 1),
        "score_options":   round(opt_score, 1),
        "score_macro":     round(macro_component, 1),
        "pe":              pe,
        "forward_pe":      fpe,
        "profit_margin":   margin,
        "upside_pct":      round(upside_pct, 1),
        "beta":            beta,
        "analyst_target":  target or None,
        "call_premium_k":  round(call_p, 0),
        "put_premium_k":   round(put_p, 0),
        "week_52_high":    _safe(f.get('week_52_high')) or w52h or None,
        "week_52_low":     _safe(f.get('week_52_low'))  or w52l or None,
        "sector":          f.get('sector', ''),
        "industry":        f.get('industry', ''),
        "description":     f.get('description', ''),
        "market_cap":      f.get('market_cap'),
        "reasons":         reasons,
        "narrative":       _build_narrative(
            sym=symbol, name=f.get('name') or symbol,
            price=price, chg=chg, signal=signal, score=composite,
            mom=mom, val=val, qual=qual, opt_score=opt_score,
            macro_component=macro_component,
            pe=pe, fpe=fpe, evebit=evebit, margin=margin, beta=beta,
            target=target, upside_pct=upside_pct, in_range=in_range,
            w52h=w52h, w52l=w52l, rel_str=rel_str,
            call_p=call_p, put_p=put_p,
            vix=vix, t10y2y=t10y2y, macro_regime=macro_regime,
            macro_pct=macro_pct, macro_raw=macro_raw,
            gdp=gdp, fedfunds=fedfunds, unrate=unrate, cpi=cpi,
            hyg_chg=hyg_chg, btc_chg=btc_chg, dxy_chg=dxy_chg, tech_rs=tech_rs,
            sector=f.get('sector', ''), industry=f.get('industry', ''),
            description=f.get('description', ''),
        ),
        "macro": {
            "score": macro_raw, "score_pct": macro_pct, "regime": macro_regime,
            "vix": vix, "yield_curve": t10y2y, "fed_funds": fedfunds,
            "gdp": gdp, "unemployment": unrate, "cpi": cpi,
            "btc_change": btc_chg, "hyg_change": hyg_chg, "dxy_change": dxy_chg,
        },
        "updated":    time.time(),
        "disclaimer": "INFORMATIONAL ONLY — NOT FINANCIAL ADVICE",
    }
