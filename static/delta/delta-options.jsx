// delta-options.jsx — OPT tab: options mispricing scanner + Monte Carlo sim.
(function () {
  const { useState, useEffect, useRef } = React;

  const RICH = 'var(--rose)';   // IV rich vs smile → sell premium
  const CHEAP = 'var(--mint)';  // IV cheap vs smile → buy premium

  const pct = (v, dp = 1) => v == null ? '—' : (v * 100).toFixed(dp) + '%';
  const num = (v, dp = 2) => v == null ? '—' : Number(v).toFixed(dp);
  const sigColor = s => s === 'RICH' ? RICH : s === 'CHEAP' ? CHEAP : 'var(--muted)';

  function cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function Stat({ label, value, color }) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 64 }}>
        <span style={{ fontSize: 8, color: 'var(--muted)', letterSpacing: '.1em' }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: color || 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      </div>
    );
  }

  // ── Monte Carlo fan chart (Plotly) ────────────────────────────────────────────
  function MCChart({ mc }) {
    const plotRef = useRef(null);
    const [ready, setReady] = useState(!!window.Plotly);

    useEffect(() => {
      if (window.Plotly) { setReady(true); return; }
      const id = setInterval(() => { if (window.Plotly) { setReady(true); clearInterval(id); } }, 300);
      return () => clearInterval(id);
    }, []);

    useEffect(() => {
      if (!ready || !mc || mc.error || !plotRef.current || !window.Plotly) return;
      const text = cssVar('--text', '#d8d8d8');
      const grid = cssVar('--border', '#222');
      const cyan = cssVar('--cyan', '#38bdf8');
      const amber = cssVar('--amber', '#fbbf24');
      const muted = cssVar('--muted', '#778');
      const t = mc.times_days, b = mc.bands;
      const hide = { hoverinfo: 'skip', showlegend: false };

      const traces = [];
      // Sample paths (texture, behind everything).
      (mc.sample_paths || []).forEach(p => traces.push({
        x: t, y: p, mode: 'lines', line: { color: muted, width: 0.5 }, opacity: 0.22, ...hide,
      }));
      // P5–P95 envelope.
      traces.push({ x: t, y: b.p95, mode: 'lines', line: { width: 0 }, ...hide });
      traces.push({ x: t, y: b.p5, mode: 'lines', line: { width: 0 }, fill: 'tonexty',
                    fillcolor: 'rgba(56,189,248,.10)', name: '5–95%', ...hide });
      // P25–P75 envelope (darker).
      traces.push({ x: t, y: b.p75, mode: 'lines', line: { width: 0 }, ...hide });
      traces.push({ x: t, y: b.p25, mode: 'lines', line: { width: 0 }, fill: 'tonexty',
                    fillcolor: 'rgba(56,189,248,.18)', name: '25–75%', ...hide });
      // Median path.
      traces.push({ x: t, y: b.p50, mode: 'lines', line: { color: cyan, width: 2 },
                    name: 'median', hoverinfo: 'y' });

      const xmax = t[t.length - 1];
      const layout = {
        margin: { l: 44, r: 10, t: 8, b: 28 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'JetBrains Mono, monospace', color: text, size: 10 },
        showlegend: false,
        xaxis: { title: { text: 'days', font: { color: muted, size: 9 } },
                 color: text, gridcolor: grid, zerolinecolor: grid, range: [0, xmax] },
        yaxis: { color: text, gridcolor: grid, zerolinecolor: grid, fixedrange: false },
        shapes: [
          { type: 'line', x0: 0, x1: xmax, y0: mc.spot, y1: mc.spot,
            line: { color: text, width: 1, dash: 'dot' } },
          { type: 'line', x0: 0, x1: xmax, y0: mc.option.strike, y1: mc.option.strike,
            line: { color: amber, width: 1, dash: 'dash' } },
        ],
        annotations: [
          { x: 0, y: mc.spot, xanchor: 'left', yanchor: 'bottom', text: ' spot ' + mc.spot,
            font: { color: text, size: 9 }, showarrow: false },
          { x: 0, y: mc.option.strike, xanchor: 'left', yanchor: 'top', text: ' K ' + mc.option.strike,
            font: { color: amber, size: 9 }, showarrow: false },
        ],
      };
      window.Plotly.react(plotRef.current, traces, layout, { displayModeBar: false, responsive: true });
    }, [ready, mc]);

    useEffect(() => () => { if (plotRef.current && window.Plotly) window.Plotly.purge(plotRef.current); }, []);

    return <div ref={plotRef} style={{ flex: 1, minHeight: 0, width: '100%' }} />;
  }

  function MCView({ mc, loading, horizon, setHorizon, volSrc, setVolSrc }) {
    const o = mc && mc.option;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%' }}>
        {/* Controls */}
        <div className="panel" style={{ padding: '6px 12px', display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 9, color: 'var(--muted)', letterSpacing: '.1em' }}>HORIZON</span>
          {[7, 30, 60, 90].map(h => (
            <button key={h} onClick={() => setHorizon(h)} style={chip(horizon === h)}>{h}d</button>
          ))}
          <span style={{ width: 1, height: 14, background: 'var(--border-2)' }} />
          <span style={{ fontSize: 9, color: 'var(--muted)', letterSpacing: '.1em' }}>VOL</span>
          {[['iv', 'IMPLIED'], ['rv', 'REALIZED']].map(([k, lbl]) => (
            <button key={k} onClick={() => setVolSrc(k)} style={chip(volSrc === k)}>{lbl}</button>
          ))}
          {loading && <span style={{ color: 'var(--cyan)', fontSize: 10 }} className="blink">simulating…</span>}
        </div>

        {/* Stats */}
        {mc && !mc.error && o && (
          <div className="panel" style={{ padding: '8px 14px', display: 'flex', gap: 18, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap' }}>
            <Stat label="SPOT" value={num(mc.spot)} />
            <Stat label={'VOL (' + mc.vol_source.toUpperCase() + ')'} value={pct(mc.sigma)} color="var(--cyan)" />
            <Stat label="EXPECTED" value={num(mc.terminal.mean)} />
            <Stat label="5% / 95%" value={num(mc.terminal.p5) + ' / ' + num(mc.terminal.p95)} />
            <span style={{ width: 1, height: 26, background: 'var(--border-2)' }} />
            <Stat label={'ATM ' + o.strike + 'C · MC'} value={num(o.mc_price) + ' ±' + num(o.mc_ci95)} color="var(--mint)" />
            <Stat label="BLACK-SCHOLES" value={num(o.bs_price)} />
            <Stat label="PROB ITM" value={pct(o.prob_itm)} color="var(--amber)" />
            {mc.expiry_used && <Stat label="EXPIRY IV FROM" value={mc.expiry_used} />}
          </div>
        )}

        {/* Fan chart */}
        <div className="panel" style={{ flex: 1, minHeight: 0, padding: 6, display: 'flex', flexDirection: 'column' }}>
          {(!mc || loading) && <div style={empty}>{loading ? 'Running Monte Carlo…' : 'Scan a ticker to simulate.'}</div>}
          {mc && mc.error && <div style={{ ...empty, color: 'var(--rose)' }}>{mc.error}</div>}
          {mc && !mc.error && (
            <>
              <div style={{ fontSize: 9, color: 'var(--muted)', padding: '0 4px 2px', letterSpacing: '.06em' }}>
                {mc.n_paths.toLocaleString()} GBM paths · shaded = 5–95% & 25–75% · solid = median
              </div>
              <MCChart mc={mc} />
            </>
          )}
        </div>
      </div>
    );
  }

  function Row({ r }) {
    const sc = sigColor(r.smile_signal);
    return (
      <tr style={{ background: r.flagged ? 'rgba(56,189,248,.06)' : 'transparent',
                   borderLeft: r.flagged ? `2px solid ${sc}` : '2px solid transparent' }}>
        <td style={td}>{r.expiry}</td>
        <td style={{ ...td, color: 'var(--muted)' }}>{r.dte}</td>
        <td style={{ ...td, fontWeight: 700, color: r.type === 'C' ? 'var(--cyan)' : 'var(--amber)' }}>{r.type}</td>
        <td style={tdR}>{num(r.strike, 1)}</td>
        <td style={{ ...tdR, color: 'var(--muted)' }}>{num(r.moneyness, 3)}</td>
        <td style={tdR}>{num(r.mid, 2)}</td>
        <td style={tdR}>{pct(r.iv)}</td>
        <td style={{ ...tdR, color: 'var(--muted)' }}>{pct(r.atm_iv)}</td>
        <td style={{ ...tdR, fontWeight: 700, color: sc }}>{r.residual >= 0 ? '+' : ''}{pct(r.residual)}</td>
        <td style={{ ...tdR, fontWeight: 700, color: sc }}>{r.residual_z == null ? '—' : num(r.residual_z, 1)}</td>
        <td style={{ ...td, fontWeight: 700, color: sc }}>{r.smile_signal}</td>
        <td style={{ ...tdR, color: 'var(--muted)' }}>{r.volume}</td>
        <td style={{ ...tdR, color: 'var(--muted)' }}>{r.oi}</td>
      </tr>
    );
  }

  function SmileView({ data, showAll, setShowAll }) {
    const rows = showAll ? data.rows : (data.flagged && data.flagged.length ? data.flagged : data.rows);
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, height: '100%' }}>
        <div className="panel" style={{ padding: '8px 14px', display: 'flex', gap: 22, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap' }}>
          <Stat label="SPOT" value={num(data.spot)} />
          <Stat label="REALIZED VOL" value={pct(data.rv)} />
          <Stat label="CONTRACTS" value={data.n_contracts} />
          <Stat label="FLAGGED" value={data.n_flagged} color={data.n_flagged ? 'var(--amber)' : 'var(--muted)'} />
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 9, color: RICH }}>■ RICH sell</span>
            <span style={{ fontSize: 9, color: CHEAP }}>■ CHEAP buy</span>
            <button onClick={() => setShowAll(s => !s)} style={chip(false)}>{showAll ? 'SHOW FLAGGED' : 'SHOW ALL'}</button>
          </div>
        </div>
        <div className="panel" style={{ flex: 1, overflow: 'auto', padding: 0 }}>
          {rows.length === 0
            ? <div style={empty}>No {showAll ? 'liquid contracts' : 'flagged mispricings'} for {data.ticker}.</div>
            : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 10, fontFamily: 'var(--mono)' }}>
                <thead>
                  <tr style={{ position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 1 }}>
                    {['EXPIRY','DTE','T','STRIKE','MNY','MID','IV','ATM IV','RESID','Z','SIGNAL','VOL','OI'].map((h, i) => (
                      <th key={h} style={{ ...th, textAlign: i >= 3 && i !== 10 ? 'right' : 'left' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>{rows.map((r, i) => <Row key={r.expiry + r.type + r.strike + i} r={r} />)}</tbody>
              </table>
            )}
        </div>
      </div>
    );
  }

  function OptionsMispricingPanel() {
    const [query, setQuery] = useState('');
    const [sym, setSym] = useState('');
    const [view, setView] = useState('smile');   // 'smile' | 'mc'
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [showAll, setShowAll] = useState(false);
    const [mc, setMc] = useState(null);
    const [mcLoading, setMcLoading] = useState(false);
    const [horizon, setHorizon] = useState(30);
    const [volSrc, setVolSrc] = useState('iv');
    const inputRef = useRef(null);

    const runMC = async (s, h, v) => {
      if (!s) return;
      setMcLoading(true);
      const fn = window.DeltaLive && window.DeltaLive.fetchOptionsMC;
      const res = fn ? await fn(s, h, v) : { error: 'fetch unavailable' };
      setMc(res); setMcLoading(false);
    };

    const run = async () => {
      const s = query.trim().toUpperCase();
      if (!s) return;
      setLoading(true); setData(null); setShowAll(false); setMc(null); setSym(s);
      const fn = window.DeltaLive && window.DeltaLive.fetchOptionsMispricing;
      const res = fn ? await fn(s) : { error: 'fetch unavailable', rows: [], flagged: [] };
      setData(res); setLoading(false);
      if (view === 'mc') runMC(s, horizon, volSrc);
    };

    // Lazily run MC when the MC tab opens, and whenever its controls change.
    useEffect(() => {
      if (view === 'mc' && sym) runMC(sym, horizon, volSrc);
    }, [view, sym, horizon, volSrc]);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Search + view toggle */}
        <div className="panel" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span style={{ color: 'var(--cyan)', fontSize: 11, letterSpacing: '.1em', whiteSpace: 'nowrap' }}>◆ OPTIONS</span>
          <input
            ref={inputRef} value={query}
            onChange={e => setQuery(e.target.value.toUpperCase())}
            onKeyDown={e => { if (e.key === 'Enter') run(); }}
            placeholder="Enter any ticker — AAPL, NVDA, COIN, TSLA…"
            style={{ flex: 1, background: 'var(--bg)', border: '1px solid var(--border-2)', color: 'var(--text)',
              fontFamily: 'var(--mono)', fontSize: 11, padding: '4px 8px', outline: 'none', letterSpacing: '.05em' }}
          />
          <button onClick={run} disabled={loading} style={{ padding: '4px 14px', fontFamily: 'var(--mono)', fontSize: 10,
            letterSpacing: '.08em', background: 'var(--cyan)', color: 'var(--bg)', border: 'none',
            cursor: loading ? 'wait' : 'pointer', opacity: loading ? 0.6 : 1, fontWeight: 700 }}>
            {loading ? 'SCANNING…' : 'SCAN'}
          </button>
          <span style={{ width: 1, height: 16, background: 'var(--border-2)', margin: '0 2px' }} />
          <button onClick={() => setView('smile')} style={chip(view === 'smile')}>MISPRICING</button>
          <button onClick={() => setView('mc')} style={chip(view === 'mc')}>MONTE CARLO</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, minHeight: 0 }}>
          {!data && !loading && <div className="panel" style={{ height: '100%' }}><div style={empty}>Enter a ticker and hit SCAN.</div></div>}
          {loading && <div className="panel" style={{ height: '100%' }}><div style={empty}>Scanning live option chains…</div></div>}
          {data && data.error && view === 'smile' && <div className="panel" style={{ height: '100%' }}><div style={{ ...empty, color: 'var(--rose)' }}>{data.error}</div></div>}
          {data && !loading && view === 'smile' && !data.error && <SmileView data={data} showAll={showAll} setShowAll={setShowAll} />}
          {data && !loading && view === 'mc' && (
            <MCView mc={mc} loading={mcLoading} horizon={horizon} setHorizon={setHorizon} volSrc={volSrc} setVolSrc={setVolSrc} />
          )}
        </div>
      </div>
    );
  }

  const chip = on => ({
    padding: '3px 10px', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '.06em', cursor: 'pointer',
    background: on ? 'var(--cyan)' : 'transparent', color: on ? 'var(--bg)' : 'var(--cyan)',
    border: '1px solid var(--border-2)', fontWeight: 700,
  });
  const td = { padding: '3px 8px', borderBottom: '1px solid var(--border-2)', whiteSpace: 'nowrap', color: 'var(--text)' };
  const tdR = { ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
  const th = { padding: '5px 8px', fontSize: 8, letterSpacing: '.08em', color: 'var(--muted)',
    borderBottom: '1px solid var(--border-2)', fontWeight: 700, whiteSpace: 'nowrap' };
  const empty = { padding: 24, textAlign: 'center', color: 'var(--muted)', fontSize: 11 };

  window.DeltaPanels = window.DeltaPanels || {};
  Object.assign(window.DeltaPanels, { OptionsMispricingPanel });
})();
