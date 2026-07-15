// delta-orderflow3d.jsx — live 3D order-flow topography panel (Plotly.js)
// Registers window.DeltaPanels.OrderFlow3DPanel  (tab code OF3)
(function () {
  const { useState, useEffect, useRef } = React;

  const METLAB = {
    gex:     'GEX ($mm / 1% move)',
    volume:  'Contract volume',
    netflow: 'Net flow (call − put)',
    oi:      'Open interest',
  };
  const COLORSCALE = { gex: 'Earth', volume: 'Viridis', netflow: 'RdBu', oi: 'Hot' };

  function cssVar(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }

  function OrderFlow3DPanel() {
    const [input, setInput]   = useState('SPY');
    const [ticker, setTicker] = useState('SPY');
    const [metric, setMetric] = useState('gex');
    const [data, setData]     = useState(null);
    const [err, setErr]       = useState(null);
    const [loading, setLoad]  = useState(false);
    const [auto, setAuto]     = useState(true);
    const [updated, setUpd]   = useState(null);
    const [ready, setReady]   = useState(!!window.Plotly);
    const plotRef = useRef(null);

    // Wait for the Plotly CDN script to finish loading.
    useEffect(() => {
      if (window.Plotly) { setReady(true); return; }
      const id = setInterval(() => {
        if (window.Plotly) { setReady(true); clearInterval(id); }
      }, 300);
      return () => clearInterval(id);
    }, []);

    async function load(t) {
      setLoad(true); setErr(null);
      try {
        const r = await fetch(`/api/orderflow-surface?symbol=${encodeURIComponent(t)}&expiries=6`);
        const j = await r.json();
        if (j.error) { setErr(j.error); }
        else { setData(j); setUpd(new Date()); }
      } catch (e) { setErr(String(e)); }
      setLoad(false);
    }

    useEffect(() => { load(ticker); }, [ticker]);

    // Live auto-refresh.
    useEffect(() => {
      if (!auto) return;
      const id = setInterval(() => load(ticker), 45000);
      return () => clearInterval(id);
    }, [auto, ticker]);

    // Render / update the Plotly surface.
    useEffect(() => {
      if (!ready || !data || !plotRef.current || !window.Plotly) return;
      const text = cssVar('--text', '#d8d8d8');
      const grid = cssVar('--border', '#222');
      const z = (data.z && data.z[metric]) || [];
      const trace = {
        type: 'surface', x: data.x, y: data.y, z: z,
        colorscale: COLORSCALE[metric] || 'Viridis',
        reversescale: metric === 'netflow',
        showscale: true,
        colorbar: { title: { text: METLAB[metric], font: { color: text, size: 10 } },
                    tickfont: { color: text, size: 9 }, thickness: 10, len: 0.6 },
        contours: { z: { show: true, usecolormap: true, project: { z: true } } },
      };
      const ax = (title) => ({
        title: { text: title, font: { color: text, size: 11 } },
        color: text, gridcolor: grid, zerolinecolor: grid,
        backgroundcolor: 'rgba(0,0,0,0)', showbackground: true,
      });
      const layout = {
        margin: { l: 0, r: 0, t: 0, b: 0 },
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'JetBrains Mono, monospace', color: text, size: 10 },
        scene: {
          xaxis: ax('Strike'), yaxis: ax('Days to expiry'), zaxis: ax(METLAB[metric]),
          camera: { eye: { x: 1.7, y: -1.7, z: 0.85 } },
          aspectratio: { x: 1.3, y: 1, z: 0.7 },
          bgcolor: 'rgba(0,0,0,0)',
          annotations: data.spot ? [{
            x: data.spot, y: (data.y && data.y[0]) || 0,
            z: 0, text: `spot ${data.spot}`, font: { color: cssVar('--cyan', '#0ff'), size: 10 },
            showarrow: true, arrowcolor: cssVar('--cyan', '#0ff'),
          }] : [],
        },
      };
      window.Plotly.react(plotRef.current, [trace], layout,
        { displayModeBar: false, responsive: true });
    }, [ready, data, metric]);

    // Cleanup on unmount.
    useEffect(() => () => {
      if (plotRef.current && window.Plotly) window.Plotly.purge(plotRef.current);
    }, []);

    const META = ['gex', 'volume', 'netflow', 'oi'];
    return (
      <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="panel-head">
          <span>ORDER FLOW · 3D TOPOGRAPHY{!ready ? ' · loading plotly…' : ''}</span>
          <span className="meta">
            {data ? `${data.ticker} · spot ${Number(data.spot).toFixed(2)} · ${(data.y || []).length} expiries` : '—'}
            {updated ? ' · ' + updated.toLocaleTimeString() : ''}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap',
                      padding: '4px 8px', borderBottom: '1px solid var(--border)' }}>
          <input className="btn" style={{ width: 76 }} value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => { if (e.key === 'Enter') setTicker(input.trim() || 'SPY'); }}
            placeholder="TICKER" />
          <button className="btn" onClick={() => setTicker(input.trim() || 'SPY')}>LOAD</button>
          <span className="dim">|</span>
          {META.map((m) => (
            <button key={m} className={'btn' + (metric === m ? ' on' : '')}
              onClick={() => setMetric(m)}>{m.toUpperCase()}</button>
          ))}
          <span className="dim">|</span>
          <button className={'btn' + (auto ? ' on' : '')} onClick={() => setAuto((a) => !a)}>
            {auto ? '● LIVE' : '○ LIVE'}
          </button>
          <button className="btn" onClick={() => load(ticker)}>↻</button>
          {loading && <span className="mut blink">loading…</span>}
          {err && <span className="down">err: {err}</span>}
          {data && (data.call_wall || data.put_wall) && (
            <span className="meta" style={{ marginLeft: 'auto' }}>
              <span className="up">call wall {data.call_wall}</span>
              {' · '}
              <span className="warn">put wall {data.put_wall}</span>
            </span>
          )}
        </div>

        <div ref={plotRef} style={{ flex: 1, minHeight: 0, width: '100%' }} />

        {!data && !err && (
          <div className="mut" style={{ padding: 12, fontSize: 11 }}>
            Fetching live option chains… (needs network; large names like SPY/QQQ/NVDA work best)
          </div>
        )}
      </div>
    );
  }

  window.DeltaPanels = Object.assign(window.DeltaPanels || {}, { OrderFlow3DPanel });
})();
