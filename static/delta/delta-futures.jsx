// delta-futures.jsx — FUT panel: CME-complex futures quotes + CFTC COT positioning
// Self-fetching from /api/futures; merges into window.DeltaPanels
(function () {
  const { useState, useEffect, useMemo } = React;

  function PH({ title, meta, right }) {
    return (
      <div className="panel-head">
        <span>◆ {title}</span><span style={{ flex: 1 }} />
        {meta && <span className="meta">{meta}</span>}
        {right && <span style={{ marginLeft: 8 }}>{right}</span>}
      </div>
    );
  }
  function Empty({ msg }) {
    return <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 11 }}>{msg || 'Awaiting data…'}</div>;
  }

  const fmtPx = (v) => {
    if (v == null) return '—';
    if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (v >= 10) return v.toFixed(2);
    return v.toFixed(4);
  };
  const fmtNet = (v) => {
    if (v == null) return '—';
    const a = Math.abs(v);
    const s = a >= 1e6 ? (a / 1e6).toFixed(2) + 'M' : a >= 1e3 ? (a / 1e3).toFixed(1) + 'K' : String(a);
    return (v > 0 ? '+' : v < 0 ? '-' : '') + s;
  };

  function FuturesPanel() {
    const [data, setData] = useState(null);
    const [err, setErr] = useState(null);
    const [grpFilter, setGrpFilter] = useState('ALL');

    useEffect(() => {
      let alive = true;
      const load = () => fetch('/api/futures', { signal: AbortSignal.timeout(8000) })
        .then(r => r.json())
        .then(d => { if (alive) { setData(d); setErr(d.error || null); } })
        .catch(e => { if (alive) setErr(String(e)); });
      load();
      const iv = setInterval(load, 60000);
      return () => { alive = false; clearInterval(iv); };
    }, []);

    const groups = (data && data.groups) || {};
    const quotes = (data && data.quotes) || {};
    const cot    = (data && data.cot) || {};
    const grpNames = Object.keys(groups);

    const rows = useMemo(() => {
      const out = [];
      for (const g of grpNames) {
        if (grpFilter !== 'ALL' && g !== grpFilter) continue;
        for (const sym of groups[g]) {
          const q = quotes[sym];
          if (q) out.push({ ...q, cot: cot[sym] });
        }
      }
      return out;
    }, [data, grpFilter]);

    let lastGroup = null;

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="FUTURES — CME COMPLEX" meta={`${rows.length} CONTRACTS`}
            right={
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {['ALL', ...grpNames].map(g => (
                  <button key={g} className={`btn${grpFilter === g ? ' on' : ''}`}
                    onClick={() => setGrpFilter(g)} style={{ padding: '1px 6px', fontSize: 10 }}>
                    {g.toUpperCase()}
                  </button>
                ))}
              </div>
            } />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {rows.length === 0 ? <Empty msg={err || 'Awaiting futures data…'} /> : (
              <table className="dense">
                <thead><tr>
                  <th>CONTRACT</th><th>SYM</th>
                  <th className="num">LAST</th><th className="num">CHG%</th>
                  <th className="num">DAY LO–HI</th>
                  <th className="num" title="CFTC large-spec net position (long − short)">SPEC NET</th>
                  <th className="num" title="Weekly change in spec net">WK Δ</th>
                  <th className="num" title="Commercial (hedger) net position">COMM NET</th>
                  <th className="num">OPEN INT</th>
                </tr></thead>
                <tbody>
                  {rows.map((r) => {
                    const header = r.complex !== lastGroup
                      ? <tr key={r.complex}><td colSpan={9} className="lbl" style={{
                          background: 'var(--surface-2)', fontSize: 9, letterSpacing: '.12em',
                          padding: '3px 8px' }}>{r.complex.toUpperCase()}</td></tr>
                      : null;
                    lastGroup = r.complex;
                    const c = r.cot;
                    return (
                      <React.Fragment key={r.symbol}>
                        {header}
                        <tr>
                          <td>{r.name}</td>
                          <td className="mut" style={{ fontSize: 10 }}>{r.symbol}</td>
                          <td className="num" style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtPx(r.price)}</td>
                          <td className={`num ${r.change_pct >= 0 ? 'up' : 'down'}`}>
                            {r.change_pct >= 0 ? '▲' : '▼'} {Math.abs(r.change_pct).toFixed(2)}%
                          </td>
                          <td className="num mut" style={{ fontSize: 10 }}>
                            {r.day_low ? `${fmtPx(r.day_low)}–${fmtPx(r.day_high)}` : '—'}
                          </td>
                          <td className="num" style={{ color: !c ? 'var(--muted)' : c.spec_net >= 0 ? 'var(--mint)' : 'var(--rose)' }}>
                            {c ? fmtNet(c.spec_net) : '—'}
                          </td>
                          <td className="num" style={{ color: !c ? 'var(--muted)' : c.spec_net_change >= 0 ? 'var(--mint)' : 'var(--rose)', fontSize: 10 }}>
                            {c ? fmtNet(c.spec_net_change) : '—'}
                          </td>
                          <td className="num mut" style={{ fontSize: 10 }}>{c ? fmtNet(c.comm_net) : '—'}</td>
                          <td className="num mut" style={{ fontSize: 10 }}>{c ? c.open_interest.toLocaleString() : '—'}</td>
                        </tr>
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Quotes: Yahoo (CME front month, delayed) · Positioning: CFTC COT legacy futures-only
            {data && data.cot_date ? ` · report ${data.cot_date}` : ''} · SPEC = large speculators, COMM = hedgers
          </div>
        </div>
      </div>
    );
  }

  window.DeltaPanels = window.DeltaPanels || {};
  Object.assign(window.DeltaPanels, { FuturesPanel });
})();
