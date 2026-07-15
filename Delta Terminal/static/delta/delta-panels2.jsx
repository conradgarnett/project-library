// delta-panels2.jsx — real-data panels for finance, cyber, science, geo, demog tabs
// Merges into window.DeltaPanels

(function () {
  const { useState, useMemo, useEffect, useCallback } = React;

  // ── Shared primitives ────────────────────────────────────────────────────────
  function PH({ title, meta, right }) {
    return (
      <div className="panel-head">
        <span>◆ {title}</span>
        <span style={{ flex: 1 }} />
        {meta && <span className="meta">{meta}</span>}
        {right && <span style={{ marginLeft: 8 }}>{right}</span>}
      </div>
    );
  }

  function Empty({ msg }) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 11 }}>
        {msg || 'Awaiting data…'}
      </div>
    );
  }

  function Filter({ value, onChange, placeholder }) {
    return (
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder || 'filter…'}
        style={{ background: 'var(--bg)', border: '1px solid var(--border-2)', color: 'var(--text)',
          fontFamily: 'var(--mono)', fontSize: 10, padding: '2px 6px', outline: 'none', width: 180 }} />
    );
  }

  function Sortable({ col, active, dir, onClick, children }) {
    return (
      <th onClick={() => onClick(col)} style={{ cursor: 'pointer' }}>
        {children}{active ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}
      </th>
    );
  }

  function useSort(items, defaultCol, defaultDir) {
    const [col, setCol] = useState(defaultCol);
    const [dir, setDir] = useState(defaultDir || 'asc');
    const toggle = useCallback((c) => {
      if (c === col) setDir(d => d === 'asc' ? 'desc' : 'asc');
      else { setCol(c); setDir('asc'); }
    }, [col]);
    const sorted = useMemo(() => {
      if (!col || !items.length) return items;
      return [...items].sort((a, b) => {
        const av = a[col], bv = b[col];
        if (av == null) return 1; if (bv == null) return -1;
        const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv;
        return dir === 'asc' ? cmp : -cmp;
      });
    }, [items, col, dir]);
    return { sorted, col, dir, toggle };
  }

  // ── BND — US Treasury Yield Curve ────────────────────────────────────────────
  function YieldCurveSVG({ pts }) {
    const W = 280, H = 150, PL = 38, PR = 12, PT = 14, PB = 24;
    const xs = pts.map(p => p.years), ys = pts.map(p => p.yield);
    const minX = xs[0], maxX = xs[xs.length - 1];
    const minY = Math.min.apply(null, ys) - 0.15;
    const maxY = Math.max.apply(null, ys) + 0.15;
    const sx = x => PL + (x - minX) / (maxX - minX) * (W - PL - PR);
    const sy = y => PT + (maxY - y) / (maxY - minY) * (H - PT - PB);
    const path = pts.map((p, i) => (i === 0 ? 'M' : 'L') + sx(p.years).toFixed(1) + ',' + sy(p.yield).toFixed(1)).join(' ');
    const isInverted = ys[0] > ys[ys.length - 1];
    const color = isInverted ? 'var(--rose)' : 'var(--mint)';
    const yTicks = [minY + 0.15, (minY + maxY) / 2, maxY - 0.15];
    return (
      <svg width={W} height={H} style={{ display: 'block', overflow: 'visible' }}>
        {yTicks.map((y, i) => (
          <g key={i}>
            <text x={PL - 4} y={sy(y) + 3} textAnchor="end" fontSize="8" fill="var(--muted)">{y.toFixed(2)}</text>
            <line x1={PL} y1={sy(y)} x2={W - PR} y2={sy(y)} stroke="var(--border)" strokeWidth="0.5" strokeDasharray="3,2" />
          </g>
        ))}
        {pts.filter((_, i) => i % 2 === 0).map(p => (
          <text key={p.label} x={sx(p.years)} y={H - PB + 14} textAnchor="middle" fontSize="8" fill="var(--muted)">{p.label}</text>
        ))}
        <path d={path} fill="none" stroke={color} strokeWidth="2" />
        {pts.map(p => <circle key={p.label} cx={sx(p.years)} cy={sy(p.yield)} r="2.5" fill={color} />)}
        {isInverted && (
          <text x={W / 2} y={PT - 2} textAnchor="middle" fontSize="8" fill="var(--rose)">INVERTED</text>
        )}
      </svg>
    );
  }

  function BondsPanel({ snap }) {
    const b = snap.bonds || { maturities: [], spread_10y2y: 0 };
    const spread = b.spread_10y2y || 0;
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="US TREASURY YIELD CURVE" meta={`UPDATING HOURLY`}
            right={<span className="pill pill-cyan">● US TREASURY</span>} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {b.maturities.length === 0 ? <Empty msg="Fetching yield curve… (updates hourly after restart)" /> : (
              <table className="dense">
                <thead><tr>
                  <th>MATURITY</th><th className="num">YIELD %</th><th className="num">YEARS</th>
                </tr></thead>
                <tbody>
                  {b.maturities.map(m => (
                    <tr key={m.label}>
                      <td className="lbl">{m.label}</td>
                      <td className="num" style={{ color: 'var(--text)', fontWeight: 600 }}>{m.yield.toFixed(3)}%</td>
                      <td className="num mut">{m.years}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <PH title="CURVE SHAPE" meta="VISUAL" />
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px 8px' }}>
            {b.maturities.length >= 2 ? <YieldCurveSVG pts={b.maturities} /> : (
              <Empty msg="Awaiting data…" />
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '8px 12px', fontSize: 11 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span className="mut" style={{ fontSize: 10 }}>10Y − 2Y SPREAD</span>
              <span style={{ color: spread >= 0 ? 'var(--mint)' : 'var(--rose)', fontWeight: 700 }}>
                {spread >= 0 ? '+' : ''}{spread.toFixed(3)}%
              </span>
            </div>
            <div style={{ fontSize: 9, color: 'var(--muted)' }}>Source: US Treasury Direct · No API key</div>
          </div>
        </div>
      </div>
    );
  }

  // ── FRX — Forex ──────────────────────────────────────────────────────────────
  function ForexPanel({ snap }) {
    const fx = snap.forex || { rates: {} };
    const [filter, setFilter] = useState('');
    const { sorted, col, dir, toggle } = useSort(
      Object.entries(fx.rates).map(([pair, v]) => ({ pair, ...v })),
      'pair', 'asc'
    );
    const rows = useMemo(() => {
      const f = filter.toUpperCase();
      return f ? sorted.filter(r => r.pair.includes(f)) : sorted;
    }, [sorted, filter]);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="FOREIGN EXCHANGE RATES"
            meta={`${rows.length} PAIRS`}
            right={<Filter value={filter} onChange={setFilter} placeholder="filter pair…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {rows.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <Sortable col="pair" active={col==='pair'} dir={dir} onClick={toggle}>PAIR</Sortable>
                  <Sortable col="rate" active={col==='rate'} dir={dir} onClick={toggle}>RATE</Sortable>
                  <Sortable col="prev" active={col==='prev'} dir={dir} onClick={toggle}>PREV</Sortable>
                  <Sortable col="change_pct" active={col==='change_pct'} dir={dir} onClick={toggle}>CHG %</Sortable>
                  <th>DIR</th>
                </tr></thead>
                <tbody>
                  {rows.map(r => {
                    const up = r.change_pct >= 0;
                    return (
                      <tr key={r.pair}>
                        <td className="lbl" style={{ fontWeight: 600 }}>{r.pair}</td>
                        <td className="num" style={{ fontWeight: 600 }}>{r.rate != null ? r.rate.toFixed(5) : '—'}</td>
                        <td className="num mut">{r.prev != null ? r.prev.toFixed(5) : '—'}</td>
                        <td className={'num ' + (up ? 'up' : 'down')}>
                          {r.change_pct != null ? (r.change_pct >= 0 ? '+' : '') + r.change_pct.toFixed(4) + '%' : '—'}
                        </td>
                        <td style={{ color: up ? 'var(--mint)' : 'var(--rose)' }}>{up ? '▲' : '▼'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: European Central Bank via Frankfurter · Updates daily
          </div>
        </div>
      </div>
    );
  }

  // ── FRD — FRED Macroeconomic ──────────────────────────────────────────────────
  function FredPanel({ snap }) {
    const fred = snap.fred || { series: {} };
    const series = Object.values(fred.series);
    const econCal = snap.econCalendar || { events: [] };
    const [view, setView] = useState('FRED');

    const ORDER = [
      'GDP Growth', 'Unemployment', 'CPI YoY', 'Core PCE YoY',
      'Fed Funds Rate', '10Y Treasury', '2Y Treasury', '10Y-2Y Spread',
      'Consumer Sentiment', 'Housing Starts', 'Retail Sales MoM',
      '5Y Breakeven', '10Y Breakeven', 'M2 YoY', 'US Debt/GDP', 'Trade Balance',
    ];

    const byName = {};
    series.forEach(s => { byName[s.name] = s; });
    const ordered = ORDER.map(n => byName[n]).filter(Boolean);
    const rest = series.filter(s => ORDER.indexOf(s.name) === -1);
    const all = ordered.concat(rest);

    const now = Date.now() / 1000;
    const upcomingEvents = econCal.events.filter(e => {
      const t = new Date(e.time).getTime() / 1000;
      return t >= now - 86400;
    }).slice(0, 80);

    function impactColor(impact) {
      if (impact === 'high')   return 'var(--rose)';
      if (impact === 'medium') return 'var(--amber)';
      return 'var(--muted)';
    }

    function impactPill(impact) {
      if (impact === 'high')   return 'pill-rose';
      if (impact === 'medium') return 'pill-amber';
      return '';
    }

    function fmtVal(v, unit) {
      if (v == null) return '—';
      const s = String(v);
      return unit ? `${s}${unit.startsWith('%') ? unit : ' '+unit}` : s;
    }

    const PCT_SERIES = new Set([
      'GDP Growth', 'CPI YoY', 'Unemployment', 'Fed Funds Rate',
      '10Y-2Y Spread', 'Core PCE YoY', 'Retail Sales MoM',
      '5Y Breakeven', '10Y Breakeven', 'M2 YoY', 'US Debt/GDP',
      '10Y Treasury', '2Y Treasury',
    ]);

    function fmtSeriesVal(name, value) {
      if (value == null) return '—';
      if (PCT_SERIES.has(name)) return value.toFixed(2) + '%';
      if (name === 'Housing Starts') return (value / 1000).toFixed(2) + 'M';
      if (name === 'Trade Balance') {
        const b = value / 1000;
        return (b >= 0 ? '$' : '-$') + Math.abs(b).toFixed(1) + 'B';
      }
      return value.toFixed(2);
    }

    function fmtSeriesChange(name, change) {
      if (change == null) return '—';
      const sign = change >= 0 ? '+' : '';
      if (PCT_SERIES.has(name)) return sign + change.toFixed(2) + '%';
      if (name === 'Housing Starts') return sign + (change / 1000).toFixed(2) + 'M';
      if (name === 'Trade Balance') {
        const b = change / 1000;
        return (b >= 0 ? '+$' : '-$') + Math.abs(b).toFixed(1) + 'B';
      }
      return sign + change.toFixed(3);
    }

    function surpriseColor(s) {
      if (s == null) return 'var(--muted)';
      return s > 0 ? 'var(--mint)' : s < 0 ? 'var(--rose)' : 'var(--muted)';
    }

    const TabBtn = ({ label, active }) => (
      <button onClick={() => setView(label)}
        style={{ padding: '2px 10px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
          border: '1px solid', letterSpacing: '.06em',
          borderColor: active ? 'var(--cyan)' : 'var(--border-2)',
          background: active ? 'rgba(56,189,248,.12)' : 'transparent',
          color: active ? 'var(--cyan)' : 'var(--text-2)' }}>
        {label}
      </button>
    );

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title={view === 'FRED' ? 'FRED MACROECONOMIC INDICATORS' : 'ECONOMIC CALENDAR'}
            meta={view === 'FRED' ? `${all.length} SERIES` : `${upcomingEvents.length} EVENTS`}
            right={
              <div style={{ display: 'flex', gap: 4 }}>
                <TabBtn label="FRED"     active={view === 'FRED'} />
                <TabBtn label="CALENDAR" active={view === 'CALENDAR'} />
              </div>
            } />

          {view === 'FRED' ? (
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {all.length === 0 ? <Empty msg="Fetching FRED data… (updates hourly)" /> : (
                <table className="dense">
                  <thead><tr>
                    <th>INDICATOR</th>
                    <th className="num">VALUE</th>
                    <th className="num">PREV</th>
                    <th className="num">CHANGE</th>
                    <th>DATE</th>
                  </tr></thead>
                  <tbody>
                    {all.map(s => {
                      const up = s.change >= 0;
                      return (
                        <tr key={s.series_id}>
                          <td className="lbl">{s.name}</td>
                          <td className="num" style={{ fontWeight: 600 }}>{fmtSeriesVal(s.name, s.value)}</td>
                          <td className="num mut">{fmtSeriesVal(s.name, s.prev)}</td>
                          <td className={'num ' + (up ? 'up' : 'down')}>{fmtSeriesChange(s.name, s.change)}</td>
                          <td className="mut" style={{ fontSize: 10 }}>{s.date || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          ) : (
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {upcomingEvents.length === 0 ? <Empty msg="Loading economic calendar…" /> : (
                <table className="dense">
                  <thead><tr>
                    <th>DATE/TIME</th>
                    <th>COUNTRY</th>
                    <th>EVENT</th>
                    <th>IMPACT</th>
                    <th className="num">ACTUAL</th>
                    <th className="num">ESTIMATE</th>
                    <th className="num">PREV</th>
                    <th className="num">SURPRISE</th>
                  </tr></thead>
                  <tbody>
                    {upcomingEvents.map((e, i) => {
                      const dt = new Date(e.time);
                      const isPast = dt.getTime() < Date.now();
                      return (
                        <tr key={i} style={{ opacity: isPast ? 0.7 : 1 }}>
                          <td className="mut" style={{ whiteSpace: 'nowrap', fontSize: 10 }}>
                            {dt.toLocaleDateString([], {month:'short', day:'numeric'})}
                            {' '}{dt.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                          </td>
                          <td><span className="lbl">{e.country}</span></td>
                          <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={e.event}>{e.event}</td>
                          <td>
                            <span className={`pill ${impactPill(e.impact)}`} style={{ fontSize: 9 }}>
                              {e.impact?.toUpperCase()}
                            </span>
                          </td>
                          <td className="num" style={{ fontWeight: isPast ? 600 : 400 }}>
                            {fmtVal(e.actual, e.unit)}
                          </td>
                          <td className="num mut">{fmtVal(e.estimate, e.unit)}</td>
                          <td className="num mut">{fmtVal(e.prev, e.unit)}</td>
                          <td className="num" style={{ color: surpriseColor(e.surprise) }}>
                            {e.surprise != null ? (e.surprise > 0 ? '+' : '') + e.surprise + '%' : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            {view === 'FRED'
              ? 'Source: Federal Reserve Bank of St. Louis (FRED)'
              : 'Source: Finnhub Economic Calendar · High + Medium impact events · US, EU, GB, JP, CN'}
          </div>
        </div>
      </div>
    );
  }

  // ── CVE — Vulnerabilities ────────────────────────────────────────────────────
  function CvePanel({ snap }) {
    const cve = snap.cve || { recent: [], kev: [] };
    const [tab, setTab] = useState('kev');
    const [filter, setFilter] = useState('');
    const rows = tab === 'kev' ? cve.kev : cve.recent;
    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      if (!f) return rows;
      return rows.filter(r =>
        (r.id || '').toLowerCase().includes(f) ||
        (r.vendor || '').toLowerCase().includes(f) ||
        (r.product || '').toLowerCase().includes(f) ||
        (r.name || r.description || '').toLowerCase().includes(f)
      );
    }, [rows, filter]);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="CYBER VULNERABILITIES"
            meta={`${filtered.length} OF ${rows.length}`}
            right={<Filter value={filter} onChange={setFilter} placeholder="search CVE / vendor…" />} />
          <div style={{ display: 'flex', gap: 4, padding: '4px 8px', borderBottom: '1px solid var(--border)' }}>
            {[['kev', `CISA KEV (${cve.kev.length})`], ['recent', `NVD RECENT (${cve.recent.length})`]].map(([code, label]) => (
              <button key={code} className={'btn' + (tab === code ? ' on' : '')} onClick={() => setTab(code)}
                style={{ fontSize: 10, padding: '2px 10px' }}>{label}</button>
            ))}
          </div>
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>CVE ID</th><th>VENDOR</th><th>PRODUCT</th>
                  <th style={{ maxWidth: 320 }}>VULNERABILITY</th>
                  {tab === 'kev' && <><th>ADDED</th><th>DUE</th><th>RANSOM</th></>}
                </tr></thead>
                <tbody>
                  {filtered.map(r => (
                    <tr key={r.id}>
                      <td><a href={'https://nvd.nist.gov/vuln/detail/' + r.id} target="_blank"
                        style={{ color: 'var(--cyan)', textDecoration: 'none' }}>{r.id}</a></td>
                      <td className="lbl">{r.vendor || '—'}</td>
                      <td className="mut">{r.product || '—'}</td>
                      <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.name || r.description || '—'}
                      </td>
                      {tab === 'kev' && (
                        <>
                          <td className="mut" style={{ fontSize: 10 }}>{r.date_added || '—'}</td>
                          <td className="warn" style={{ fontSize: 10 }}>{r.due_date || '—'}</td>
                          <td>{r.ransomware && r.ransomware !== 'Unknown'
                            ? <span className="pill pill-rose">{r.ransomware}</span>
                            : <span className="dim">—</span>}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: CISA Known Exploited Vulnerabilities · NIST NVD · No API key
          </div>
        </div>
      </div>
    );
  }

  // ── RKT — Rocket Launches ────────────────────────────────────────────────────
  function LaunchesPanel({ snap }) {
    const lnch = snap.launches || { upcoming: [], recent: [] };
    const [tab, setTab] = useState('upcoming');
    const rows = tab === 'upcoming' ? lnch.upcoming : lnch.recent;

    const statusColor = (s) => {
      if (!s) return '';
      const sl = s.toLowerCase();
      if (sl.includes('go') || sl.includes('success')) return 'up';
      if (sl.includes('fail') || sl.includes('partial')) return 'down';
      return 'warn';
    };

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="ROCKET LAUNCH SCHEDULE"
            meta={`${lnch.upcoming.length} UPCOMING · ${lnch.recent.length} RECENT`}
            right={<span className="pill pill-violet">● LAUNCH LIBRARY 2</span>} />
          <div style={{ display: 'flex', gap: 4, padding: '4px 8px', borderBottom: '1px solid var(--border)' }}>
            {[['upcoming', 'UPCOMING'], ['recent', 'RECENT']].map(([code, label]) => (
              <button key={code} className={'btn' + (tab === code ? ' on' : '')} onClick={() => setTab(code)}
                style={{ fontSize: 10, padding: '2px 10px' }}>{label}</button>
            ))}
          </div>
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {rows.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>MISSION</th><th>VEHICLE</th><th>AGENCY</th>
                  <th>PAD / LOCATION</th>
                  {tab === 'upcoming' ? <><th>NET (UTC)</th><th>T−MINUS</th></> : <th>DATE</th>}
                  <th>STATUS</th>
                </tr></thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.id}>
                      <td style={{ maxWidth: 200 }}>
                        <div style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 200 }}>
                          {r.mission_name || r.name}
                        </div>
                        {r.mission_type && <div className="mut" style={{ fontSize: 9 }}>{r.mission_type}</div>}
                      </td>
                      <td className="lbl">{r.vehicle || r.family || '—'}</td>
                      <td className="mut">{r.agency || '—'}</td>
                      <td style={{ maxWidth: 180 }}>
                        <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 180, fontSize: 10 }}>
                          {r.pad || '—'}
                        </div>
                        <div className="mut" style={{ fontSize: 9 }}>{(r.location || '').split(',').slice(-2).join(',').trim()}</div>
                      </td>
                      {tab === 'upcoming' ? (
                        <>
                          <td className="num" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{r.net || '—'}</td>
                          <td className="num" style={{ color: 'var(--cyan)', fontWeight: 700, whiteSpace: 'nowrap' }}>
                            {r.countdown || '—'}
                          </td>
                        </>
                      ) : (
                        <td className="num mut" style={{ fontSize: 10 }}>{r.net || '—'}</td>
                      )}
                      <td><span className={'pill pill-' + (statusColor(r.status) === 'up' ? 'mint' : statusColor(r.status) === 'down' ? 'rose' : 'amber')}>
                        {r.status || '—'}
                      </span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: The Space Devs — Launch Library 2 · Free, no API key
          </div>
        </div>
      </div>
    );
  }

  // ── WAR — Conflicts / GDELT ───────────────────────────────────────────────────
  function ConflictsPanel({ snap }) {
    const conf = snap.conflicts || { events: [] };
    const [filter, setFilter] = useState('');
    const [selTheme, setSelTheme] = useState('ALL');

    const themes = useMemo(() => {
      const s = new Set(['ALL']);
      conf.events.forEach(e => { if (e.theme) s.add(e.theme); });
      return Array.from(s);
    }, [conf.events]);

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      return conf.events.filter(e => {
        const themeOk = selTheme === 'ALL' || e.theme === selTheme;
        const textOk = !f || (e.title || '').toLowerCase().includes(f) || (e.country || '').toLowerCase().includes(f);
        return themeOk && textOk;
      });
    }, [conf.events, filter, selTheme]);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="GEOPOLITICAL EVENTS"
            meta={`${filtered.length} OF ${conf.events.length} EVENTS`}
            right={<Filter value={filter} onChange={setFilter} placeholder="filter keyword / country…" />} />
          <div style={{ display: 'flex', gap: 4, padding: '4px 8px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
            {themes.slice(0, 10).map(th => (
              <button key={th} className={'btn' + (selTheme === th ? ' on' : '')} onClick={() => setSelTheme(th)}
                style={{ fontSize: 9, padding: '1px 8px', textTransform: 'uppercase', letterSpacing: '.06em' }}>{th}</button>
            ))}
          </div>
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>HEADLINE</th><th>COUNTRY</th><th>THEME</th><th>DATE</th><th>SOURCE</th>
                </tr></thead>
                <tbody>
                  {filtered.map((e, i) => (
                    <tr key={i}>
                      <td style={{ maxWidth: 360 }}>
                        <a href={e.url} target="_blank"
                          style={{ color: 'var(--text)', textDecoration: 'none', display: 'block',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 360 }}>
                          {e.title || '—'}
                        </a>
                      </td>
                      <td><span className="pill pill-amber">{e.country || '—'}</span></td>
                      <td><span className="pill pill-rose" style={{ fontSize: 9 }}>{e.theme || '—'}</span></td>
                      <td className="mut" style={{ fontSize: 10 }}>{(e.date || '').slice(0, 8)}</td>
                      <td className="dim" style={{ fontSize: 9 }}>{e.domain || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: GDELT Project — Global event database · Free, no API key
          </div>
        </div>
      </div>
    );
  }

  // ── SAN — OFAC Sanctions ─────────────────────────────────────────────────────
  function SanctionsPanel({ snap }) {
    const san = snap.sanctions || { entries: [], count: 0, programs: [] };
    const [filter, setFilter] = useState('');
    const [prog, setProg] = useState('ALL');
    const { sorted, col, dir, toggle } = useSort(san.entries, 'name', 'asc');

    const programs = useMemo(() => {
      const s = new Set(['ALL']);
      san.entries.forEach(e => { if (e.program) s.add(e.program); });
      return Array.from(s).slice(0, 20);
    }, [san.entries]);

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      return sorted.filter(e => {
        const progOk = prog === 'ALL' || e.program === prog;
        const textOk = !f || (e.name || '').toLowerCase().includes(f) || (e.country || '').toLowerCase().includes(f);
        return progOk && textOk;
      });
    }, [sorted, filter, prog]);

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <PH title="PROGRAMS" meta={`${programs.length - 1}`} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {programs.map(p => (
              <div key={p} onClick={() => setProg(p)}
                style={{ padding: '4px 10px', cursor: 'pointer', fontSize: 10, letterSpacing: '.04em',
                  background: prog === p ? 'var(--surface-3)' : 'transparent',
                  color: prog === p ? 'var(--cyan)' : 'var(--text-2)',
                  borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {p}
              </div>
            ))}
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="OFAC CONSOLIDATED SANCTIONS LIST"
            meta={`${filtered.length} OF ${san.count || san.entries.length}`}
            right={<Filter value={filter} onChange={setFilter} placeholder="search entity / country…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <Sortable col="name" active={col==='name'} dir={dir} onClick={toggle}>ENTITY</Sortable>
                  <Sortable col="program" active={col==='program'} dir={dir} onClick={toggle}>PROGRAM</Sortable>
                  <Sortable col="country" active={col==='country'} dir={dir} onClick={toggle}>COUNTRY</Sortable>
                  <th>TYPE</th>
                  <th>REMARKS</th>
                </tr></thead>
                <tbody>
                  {filtered.slice(0, 500).map((e, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.name || '—'}</td>
                      <td><span className="pill pill-rose" style={{ fontSize: 9 }}>{e.program || '—'}</span></td>
                      <td className="mut">{e.country || '—'}</td>
                      <td className="dim" style={{ fontSize: 9 }}>{e.type !== '-0-' ? e.type || '—' : '—'}</td>
                      <td className="dim" style={{ fontSize: 9, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {e.remarks !== '-0-' ? e.remarks || '' : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: US Treasury OFAC Consolidated Sanctions List · Public domain
          </div>
        </div>
      </div>
    );
  }

  // ── NEO — Near Earth Objects ─────────────────────────────────────────────────
  function NeoPanel({ snap }) {
    const neo = snap.neo || { objects: [], count: 0 };
    const { sorted, col, dir, toggle } = useSort(neo.objects, 'miss_km', 'asc');

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="NEAR EARTH OBJECT CLOSE APPROACHES"
            meta={`${neo.count || neo.objects.length} OBJECTS TODAY`}
            right={<span className="pill pill-amber">● NASA JPL</span>} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {sorted.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>OBJECT</th>
                  <th>HAZ</th>
                  <Sortable col="diam_min_m" active={col==='diam_min_m'} dir={dir} onClick={toggle}>DIAM MIN (m)</Sortable>
                  <Sortable col="diam_max_m" active={col==='diam_max_m'} dir={dir} onClick={toggle}>DIAM MAX (m)</Sortable>
                  <Sortable col="miss_km" active={col==='miss_km'} dir={dir} onClick={toggle}>MISS DIST (km)</Sortable>
                  <Sortable col="miss_lunar" active={col==='miss_lunar'} dir={dir} onClick={toggle}>MISS (LD)</Sortable>
                  <Sortable col="velocity_kph" active={col==='velocity_kph'} dir={dir} onClick={toggle}>VEL (km/h)</Sortable>
                  <th>DATE</th>
                </tr></thead>
                <tbody>
                  {sorted.map(o => (
                    <tr key={o.id}>
                      <td className="lbl" style={{ fontWeight: 600 }}>{o.name}</td>
                      <td>{o.hazardous
                        ? <span className="pill pill-rose">⚠ HAZ</span>
                        : <span className="dim">—</span>}
                      </td>
                      <td className="num">{o.diam_min_m != null ? o.diam_min_m.toFixed(0) : '—'}</td>
                      <td className="num">{o.diam_max_m != null ? o.diam_max_m.toFixed(0) : '—'}</td>
                      <td className="num">{o.miss_km != null ? Math.round(o.miss_km).toLocaleString() : '—'}</td>
                      <td className="num">{o.miss_lunar != null ? o.miss_lunar.toFixed(2) : '—'}</td>
                      <td className="num">{o.velocity_kph != null ? Math.round(o.velocity_kph).toLocaleString() : '—'}</td>
                      <td className="mut" style={{ fontSize: 10 }}>{o.approach_date || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: NASA JPL Center for Near Earth Object Studies · Free, no API key · LD = Lunar Distance
          </div>
        </div>
      </div>
    );
  }

  // ── SOL — Space Weather ───────────────────────────────────────────────────────
  function SolarPanel({ snap }) {
    const sw = snap.spaceWeather || { kp_index: 0, solar_wind: {}, alerts: [], storm_level: '' };
    const kp = sw.kp_index || 0;
    const wind = sw.solar_wind || {};

    const kpColor = kp >= 7 ? 'var(--rose)' : kp >= 5 ? 'var(--amber)' : kp >= 3 ? 'var(--cyan)' : 'var(--mint)';
    const kpLabel = kp >= 7 ? 'SEVERE STORM' : kp >= 5 ? 'STORM' : kp >= 3 ? 'UNSETTLED' : 'QUIET';

    const Stat = ({ label, value, unit, color }) => (
      <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
        <div className="mut" style={{ fontSize: 9, letterSpacing: '.1em', marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: color || 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>
          {value}
        </div>
        {unit && <div className="dim" style={{ fontSize: 9, marginTop: 2 }}>{unit}</div>}
      </div>
    );

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <PH title="SOLAR CONDITIONS" meta={sw.storm_level || ''} />
          <Stat label="KP-INDEX (PLANETARY)" value={kp.toFixed(1)} unit="Geomagnetic activity 0–9" color={kpColor} />
          <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: kpColor }}>{kpLabel}</span>
          </div>
          <Stat label="SOLAR WIND SPEED" value={wind.speed != null ? Math.round(wind.speed) : '—'} unit="km/s" />
          <Stat label="SOLAR WIND DENSITY" value={wind.density != null ? wind.density.toFixed(2) : '—'} unit="particles/cm³" />
          <Stat label="SOLAR WIND TEMP" value={wind.temp != null ? Math.round(wind.temp).toLocaleString() : '—'} unit="Kelvin" />
          <Stat label="X-RAY FLUX" value={sw.x_ray_flux != null ? sw.x_ray_flux.toExponential(2) : '—'} unit="W/m²" />
          <div style={{ padding: '6px 10px', marginTop: 'auto', fontSize: 9, color: 'var(--muted)' }}>
            Source: NOAA Space Weather Prediction Center
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="ACTIVE ALERTS" meta={`${sw.alerts.length} ALERTS`}
            right={<span className="pill pill-amber">● NOAA SWPC</span>} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {sw.alerts.length === 0 ? <Empty msg="No active space weather alerts" /> : (
              <div style={{ padding: 8 }}>
                {sw.alerts.map((a, i) => (
                  <div key={i} style={{ marginBottom: 8, padding: '8px 10px',
                    background: 'var(--surface-2)', border: '1px solid var(--border-2)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span className="lbl" style={{ fontSize: 10 }}>{a.type || a.issue_time}</span>
                      <span className="mut" style={{ fontSize: 9 }}>{a.issue_time}</span>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-2)', whiteSpace: 'pre-wrap', lineHeight: 1.5, maxHeight: 120, overflow: 'hidden' }}>
                      {(a.message || '').trim().slice(0, 400)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── NET — Network / BGP Outages ───────────────────────────────────────────────
  function OutagesPanel({ snap }) {
    const out = snap.outages || { alerts: [], countries: [], bgp: [] };
    const bgp = out.bgp.filter(e => e.time);
    const announces = bgp.filter(e => e.type === 'A').length;
    const withdraws  = bgp.filter(e => e.type === 'W').length;

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="BGP ROUTING EVENTS"
            meta={`${bgp.length} EVENTS · ${announces} ANN · ${withdraws} WITH`}
            right={<span className="pill pill-cyan">● RIPE NCC / CAIDA</span>} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {bgp.length === 0 ? <Empty msg="No BGP anomalies detected" /> : (
              <table className="dense">
                <thead><tr>
                  <th>TYPE</th><th>PREFIX</th><th>ORIGIN ASN</th><th>PEER ASN</th><th>TIME (UTC)</th>
                </tr></thead>
                <tbody>
                  {bgp.slice(0, 200).map((e, i) => (
                    <tr key={i}>
                      <td>
                        <span className={'pill ' + (e.type === 'A' ? 'pill-mint' : 'pill-rose')} style={{ fontSize: 9 }}>
                          {e.type === 'A' ? 'ANN' : 'WDR'}
                        </span>
                      </td>
                      <td className="lbl">{e.prefix || '—'}</td>
                      <td className="num mut">{e.origin || '—'}</td>
                      <td className="num mut">{e.peer || '—'}</td>
                      <td className="mut" style={{ fontSize: 10 }}>{e.time ? e.time.slice(0, 19).replace('T', ' ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <PH title="OUTAGE ALERTS" meta={`${out.alerts.length}`} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: 8 }}>
            {out.alerts.length === 0 ? <Empty msg="No active outage alerts" /> : (
              out.alerts.map((a, i) => (
                <div key={i} style={{ marginBottom: 6, padding: '6px 8px',
                  background: 'var(--surface-2)', border: '1px solid var(--border-2)', fontSize: 10 }}>
                  <div className="lbl" style={{ marginBottom: 2 }}>{a.country || a.name || 'Unknown'}</div>
                  <div className="mut">{a.description || JSON.stringify(a).slice(0, 80)}</div>
                </div>
              ))
            )}
          </div>
          <div style={{ padding: '6px 10px', borderTop: '1px solid var(--border)', fontSize: 9, color: 'var(--muted)' }}>
            Source: RIPE NCC Routing Information Service · BGPView.io
          </div>
        </div>
      </div>
    );
  }

  // ── POP — World Population / Demographics ────────────────────────────────────
  function PopulationPanel({ snap }) {
    const pop = snap.population || { countries: [] };
    const [filter, setFilter] = useState('');
    const { sorted, col, dir, toggle } = useSort(
      pop.countries.filter(c => c.pop > 1000000),
      'pop', 'desc'
    );

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      if (!f) return sorted;
      return sorted.filter(c => (c.country || '').toLowerCase().includes(f));
    }, [sorted, filter]);

    const fmt = (n) => {
      if (n == null) return '—';
      if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
      if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
      return n.toLocaleString();
    };

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="WORLD DEMOGRAPHICS (WORLD BANK)"
            meta={`${filtered.length} COUNTRIES`}
            right={<Filter value={filter} onChange={setFilter} placeholder="search country…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>COUNTRY</th>
                  <Sortable col="pop" active={col==='pop'} dir={dir} onClick={toggle}>POPULATION</Sortable>
                  <Sortable col="gdp_pc" active={col==='gdp_pc'} dir={dir} onClick={toggle}>GDP/CAPITA ($)</Sortable>
                  <Sortable col="life_exp" active={col==='life_exp'} dir={dir} onClick={toggle}>LIFE EXP (yr)</Sortable>
                  <Sortable col="unemp" active={col==='unemp'} dir={dir} onClick={toggle}>UNEMP %</Sortable>
                  <Sortable col="urban_pct" active={col==='urban_pct'} dir={dir} onClick={toggle}>URBAN %</Sortable>
                </tr></thead>
                <tbody>
                  {filtered.slice(0, 200).map((c, i) => (
                    <tr key={c.code + i}>
                      <td className="lbl" style={{ fontWeight: 600 }}>{c.country}</td>
                      <td className="num">{fmt(c.pop)}</td>
                      <td className="num">{c.gdp_pc != null ? '$' + Math.round(c.gdp_pc).toLocaleString() : '—'}</td>
                      <td className="num">{c.life_exp != null ? c.life_exp.toFixed(1) : '—'}</td>
                      <td className="num">{c.unemp != null ? c.unemp.toFixed(1) + '%' : '—'}</td>
                      <td className="num">{c.urban_pct != null ? c.urban_pct.toFixed(1) + '%' : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: World Bank Open Data · Free, no API key · Latest available year
          </div>
        </div>
      </div>
    );
  }

  // ── ENERGY — EIA (OIL / GAS / NUC / REN / ELG) ──────────────────────────────
  function MiniSparkline({ data, color, w, h }) {
    if (!data || data.length < 2) return null;
    const vals = data.map(d => parseFloat(d.value)).filter(v => !isNaN(v));
    if (vals.length < 2) return null;
    const W = w || 80, H = h || 24;
    const min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    const range = max - min || 1;
    const pts = vals.map((v, i) => (i * (W / (vals.length - 1))).toFixed(1) + ',' + (H - ((v - min) / range) * (H - 2) - 1).toFixed(1)).join(' ');
    return (
      <svg width={W} height={H} style={{ display: 'block' }}>
        <polyline points={pts} fill="none" stroke={color || 'var(--mint)'} strokeWidth="1.5" />
      </svg>
    );
  }

  function EnergyStatRow({ label, value, unit, sparkData, sparkColor, children }) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 12px', borderBottom: '1px solid var(--border)', fontSize: 11 }}>
        <span className="mut" style={{ fontSize: 10, minWidth: 160 }}>{label}</span>
        <span style={{ fontWeight: 700, color: 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        {unit && <span className="dim" style={{ fontSize: 9, minWidth: 60 }}>{unit}</span>}
        {sparkData && <MiniSparkline data={sparkData} color={sparkColor} />}
        {children}
      </div>
    );
  }

  function OilPanel({ snap }) {
    const oil = (snap.energy || {}).oil || {};
    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <PH title="OIL MARKETS" meta={`${oil.wti_date || '—'}`}
            right={<span className="pill pill-amber">● EIA / US GOV</span>} />
          <EnergyStatRow label="WTI CRUDE SPOT" value={oil.wti_price != null ? '$' + Number(oil.wti_price).toFixed(2) : '—'} unit="$/bbl" sparkData={oil.wti_history} sparkColor="var(--amber)" />
          <EnergyStatRow label="BRENT CRUDE SPOT" value={oil.brent_price != null ? '$' + Number(oil.brent_price).toFixed(2) : '—'} unit="$/bbl" sparkData={oil.brent_history} sparkColor="var(--cyan)" />
          <EnergyStatRow label="US CRUDE PRODUCTION" value={oil.us_production_mbpd != null ? Number(oil.us_production_mbpd).toLocaleString() : '—'} unit="Mb/d" />
          <EnergyStatRow label="US CRUDE INVENTORIES" value={oil.us_inventory_mb != null ? Number(oil.us_inventory_mb).toLocaleString() : '—'} unit="Mb" />
          {oil.wti_history && oil.wti_history.length > 1 && (
            <div style={{ flex: 1, padding: '12px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 8 }}>WTI 30-DAY</div>
              <MiniSparkline data={oil.wti_history} color="var(--amber)" w={400} h={80} />
            </div>
          )}
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: US Energy Information Administration (EIA) · Updates daily
          </div>
        </div>
      </div>
    );
  }

  function GasPanel({ snap }) {
    const gas = (snap.energy || {}).gas || {};
    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <PH title="NATURAL GAS" meta={gas.henry_hub_date || '—'}
            right={<span className="pill pill-amber">● EIA</span>} />
          <EnergyStatRow label="HENRY HUB SPOT" value={gas.henry_hub_price != null ? '$' + Number(gas.henry_hub_price).toFixed(3) : '—'} unit="$/MMBtu" sparkData={gas.henry_hub_history} sparkColor="var(--mint)" />
          <EnergyStatRow label="US DRY GAS PRODUCTION" value={gas.us_production_bcf != null ? Number(gas.us_production_bcf).toFixed(1) : '—'} unit="Bcf/month" />
          {gas.henry_hub_history && gas.henry_hub_history.length > 1 && (
            <div style={{ flex: 1, padding: '12px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 8 }}>HENRY HUB 30-DAY</div>
              <MiniSparkline data={gas.henry_hub_history} color="var(--mint)" w={400} h={80} />
            </div>
          )}
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: US Energy Information Administration (EIA)
          </div>
        </div>
      </div>
    );
  }

  function NuclearPanel({ snap }) {
    const nuc = (snap.energy || {}).nuclear || {};
    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <PH title="US NUCLEAR GENERATION" meta={nuc.period || '—'}
            right={<span className="pill pill-violet">● EIA</span>} />
          <EnergyStatRow label="NET GENERATION" value={nuc.generation_gwh != null ? Number(nuc.generation_gwh).toLocaleString() : '—'} unit="GWh/month" />
          {nuc.history && nuc.history.length > 1 && (
            <div style={{ flex: 1, padding: '12px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 8 }}>12-MONTH GENERATION</div>
              <MiniSparkline data={nuc.history} color="var(--violet)" w={400} h={80} />
            </div>
          )}
          {(!nuc.generation_gwh && !nuc.history) && <Empty msg="Fetching nuclear data…" />}
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: US Energy Information Administration (EIA)
          </div>
        </div>
      </div>
    );
  }

  function RenewablesPanel({ snap }) {
    const ren = (snap.energy || {}).renewables || {};
    const sources = [
      { key: 'solar',  label: 'SOLAR',       color: 'var(--amber)' },
      { key: 'wind',   label: 'WIND',         color: 'var(--mint)' },
      { key: 'hydro',  label: 'HYDROELECTRIC',color: 'var(--cyan)' },
    ];
    const total = sources.reduce((s, src) => {
      const v = ren[src.key] && ren[src.key].generation_gwh;
      return s + (v ? Number(v) : 0);
    }, 0);
    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <PH title="US RENEWABLE GENERATION" meta="MONTHLY GWh"
            right={<span className="pill pill-mint">● EIA</span>} />
          {sources.map(src => {
            const d = ren[src.key] || {};
            const gwh = d.generation_gwh != null ? Number(d.generation_gwh) : null;
            const pct = total > 0 && gwh != null ? ((gwh / total) * 100).toFixed(1) : null;
            return (
              <div key={src.key} style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ color: src.color, fontWeight: 600, fontSize: 11 }}>{src.label}</span>
                  <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                    {gwh != null ? gwh.toLocaleString() + ' GWh' : '—'}
                    {pct && <span className="mut" style={{ fontSize: 9, marginLeft: 8 }}>{pct}% of shown</span>}
                  </span>
                </div>
                {gwh != null && total > 0 && (
                  <div style={{ height: 4, background: 'var(--surface-2)', borderRadius: 2 }}>
                    <div style={{ height: '100%', width: ((gwh / total) * 100) + '%', background: src.color, borderRadius: 2 }} />
                  </div>
                )}
                <div className="mut" style={{ fontSize: 9, marginTop: 2 }}>{d.period || '—'}</div>
              </div>
            );
          })}
          {sources.every(s => !ren[s.key]) && <Empty msg="Fetching renewables data…" />}
          <div style={{ flex: 1 }} />
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: US Energy Information Administration (EIA) · Monthly generation data
          </div>
        </div>
      </div>
    );
  }

  function GridPanel({ snap }) {
    const elec = (snap.energy || {}).electricity || {};
    const sources = Object.entries(elec.by_source || {});
    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="US POWER GRID" meta={`${sources.length} SOURCES`}
            right={<span className="pill pill-cyan">● EIA</span>} />
          <EnergyStatRow label="RETAIL PRICE (RESIDENTIAL)" value={elec.retail_price_cents_kwh != null ? Number(elec.retail_price_cents_kwh).toFixed(2) + ' ¢' : '—'} unit="/kWh" sparkData={elec.price_history} sparkColor="var(--cyan)" />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {sources.length === 0 ? <Empty msg="Fetching grid data…" /> : (
              <table className="dense">
                <thead><tr><th>FUEL TYPE</th><th className="num">GENERATION (GWh)</th><th>PERIOD</th></tr></thead>
                <tbody>
                  {sources.sort((a, b) => (b[1].generation_gwh || 0) - (a[1].generation_gwh || 0)).map(([fuel, d]) => (
                    <tr key={fuel}>
                      <td className="lbl">{fuel}</td>
                      <td className="num">{d.generation_gwh != null ? Number(d.generation_gwh).toLocaleString() : '—'}</td>
                      <td className="mut" style={{ fontSize: 10 }}>{d.period || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: EIA Electric Power Operational Data
          </div>
        </div>
      </div>
    );
  }

  // ── EQT — Equity Fundamentals (Alpha Vantage) ────────────────────────────────
  function EquityPanel({ snap }) {
    const ef = snap.equityFund || { fundamentals: {} };
    const rows = Object.values(ef.fundamentals);
    const [sel, setSel] = useState(null);
    const [filter, setFilter] = useState('');
    const { sorted, col, dir, toggle } = useSort(rows, 'market_cap', 'desc');

    const filtered = useMemo(() => {
      const f = filter.toUpperCase();
      if (!f) return sorted;
      return sorted.filter(r => (r.symbol || '').includes(f) || (r.name || '').toUpperCase().includes(f) || (r.sector || '').toUpperCase().includes(f));
    }, [sorted, filter]);

    const selected = sel ? (ef.fundamentals[sel] || null) : null;

    const fmtCap = (v) => {
      if (v == null) return '—';
      if (v >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T';
      if (v >= 1e9)  return '$' + (v / 1e9).toFixed(1) + 'B';
      if (v >= 1e6)  return '$' + (v / 1e6).toFixed(0) + 'M';
      return '$' + v.toLocaleString();
    };

    const fmtRev = (v) => {
      if (v == null) return '—';
      if (v >= 1e12) return (v / 1e12).toFixed(2) + 'T';
      if (v >= 1e9)  return (v / 1e9).toFixed(1) + 'B';
      return (v / 1e6).toFixed(0) + 'M';
    };

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="EQUITY FUNDAMENTALS"
            meta={`${filtered.length} STOCKS · ALPHA VANTAGE · DAILY`}
            right={<Filter value={filter} onChange={setFilter} placeholder="search symbol / sector…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? (
              <Empty msg={rows.length === 0 ? "Fetching fundamentals… (runs ~3 min on startup, 25 stocks/day limit)" : "No matches"} />
            ) : (
              <table className="dense">
                <thead><tr>
                  <Sortable col="symbol" active={col==='symbol'} dir={dir} onClick={toggle}>SYM</Sortable>
                  <th>COMPANY</th>
                  <th>SECTOR</th>
                  <Sortable col="market_cap" active={col==='market_cap'} dir={dir} onClick={toggle}>MKT CAP</Sortable>
                  <Sortable col="pe_ratio" active={col==='pe_ratio'} dir={dir} onClick={toggle}>P/E</Sortable>
                  <Sortable col="forward_pe" active={col==='forward_pe'} dir={dir} onClick={toggle}>FWD P/E</Sortable>
                  <Sortable col="eps" active={col==='eps'} dir={dir} onClick={toggle}>EPS</Sortable>
                  <Sortable col="dividend_yield" active={col==='dividend_yield'} dir={dir} onClick={toggle}>DIV %</Sortable>
                  <Sortable col="profit_margin" active={col==='profit_margin'} dir={dir} onClick={toggle}>MARGIN</Sortable>
                  <Sortable col="revenue_ttm" active={col==='revenue_ttm'} dir={dir} onClick={toggle}>REV TTM</Sortable>
                  <Sortable col="beta" active={col==='beta'} dir={dir} onClick={toggle}>BETA</Sortable>
                </tr></thead>
                <tbody>
                  {filtered.map(r => (
                    <tr key={r.symbol} onClick={() => setSel(sel === r.symbol ? null : r.symbol)}
                      className={sel === r.symbol ? 'selected' : ''}>
                      <td className="lbl" style={{ fontWeight: 700 }}>{r.symbol}</td>
                      <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</td>
                      <td className="mut" style={{ fontSize: 10 }}>{r.sector || '—'}</td>
                      <td className="num">{fmtCap(r.market_cap)}</td>
                      <td className="num">{r.pe_ratio != null ? r.pe_ratio.toFixed(1) : '—'}</td>
                      <td className="num">{r.forward_pe != null ? r.forward_pe.toFixed(1) : '—'}</td>
                      <td className="num">{r.eps != null ? r.eps.toFixed(2) : '—'}</td>
                      <td className="num">{r.dividend_yield != null ? (r.dividend_yield * 100).toFixed(2) + '%' : '—'}</td>
                      <td className="num">{r.profit_margin != null ? (r.profit_margin * 100).toFixed(1) + '%' : '—'}</td>
                      <td className="num">{fmtRev(r.revenue_ttm)}</td>
                      <td className="num">{r.beta != null ? r.beta.toFixed(2) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: Alpha Vantage · Updated daily · Free key (25 req/day)
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <PH title={selected ? selected.symbol : 'DETAIL'} meta={selected ? selected.exchange : 'SELECT ROW'} />
          {!selected ? (
            <div style={{ padding: 20, color: 'var(--muted)', fontSize: 10, textAlign: 'center' }}>
              Click a stock for detail
            </div>
          ) : (
            <div style={{ flex: 1, overflow: 'auto', padding: '8px 12px', fontSize: 11 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--cyan)', marginBottom: 2 }}>{selected.symbol}</div>
              <div style={{ marginBottom: 8, color: 'var(--text-2)', fontSize: 11 }}>{selected.name}</div>
              <div className="pill pill-cyan" style={{ marginBottom: 10, fontSize: 9 }}>{selected.sector} › {selected.industry}</div>
              {selected.description && (
                <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.5 }}>
                  {selected.description}
                </div>
              )}
              {[
                ['Market Cap', fmtCap(selected.market_cap)],
                ['Revenue TTM', fmtRev(selected.revenue_ttm)],
                ['Profit Margin', selected.profit_margin != null ? (selected.profit_margin * 100).toFixed(1) + '%' : '—'],
                ['P/E Ratio', selected.pe_ratio != null ? selected.pe_ratio.toFixed(2) : '—'],
                ['Forward P/E', selected.forward_pe != null ? selected.forward_pe.toFixed(2) : '—'],
                ['EPS', selected.eps != null ? '$' + selected.eps.toFixed(2) : '—'],
                ['Dividend Yield', selected.dividend_yield != null ? (selected.dividend_yield * 100).toFixed(2) + '%' : '—'],
                ['Beta', selected.beta != null ? selected.beta.toFixed(2) : '—'],
                ['52w High', selected.week_52_high != null ? '$' + selected.week_52_high.toFixed(2) : '—'],
                ['52w Low', selected.week_52_low != null ? '$' + selected.week_52_low.toFixed(2) : '—'],
                ['Price/Book', selected.price_to_book != null ? selected.price_to_book.toFixed(2) + 'x' : '—'],
                ['EV/EBITDA', selected.ev_to_ebitda != null ? selected.ev_to_ebitda.toFixed(1) + 'x' : '—'],
                ['Analyst Target', selected.analyst_target != null ? '$' + Number(selected.analyst_target).toFixed(2) : '—'],
                ['Ex-Div Date', selected.ex_div_date || '—'],
              ].map(([lbl, val]) => (
                <div key={lbl} style={{ display: 'flex', justifyContent: 'space-between',
                  padding: '4px 0', borderBottom: '1px solid var(--border)', fontSize: 10 }}>
                  <span className="mut">{lbl}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text)' }}>{val}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Climate Panel (NOAA CDO) ─────────────────────────────────────────────────
  function ClimatePanel({ snap }) {
    const { stations } = snap.climate || { stations: [] };
    const [sel, setSel] = useState(stations[0]?.city || null);
    const [view, setView] = useState('TEMP');

    const station = stations.find(s => s.city === sel) || stations[0];

    function TrendChart({ annual, field: fld, label, color }) {
      const pts = annual.filter(r => r[fld] != null).map(r => ({
        y: parseInt(r.date.slice(0,4)),
        v: r[fld],
      }));
      if (pts.length < 2) return <div style={{ color: 'var(--muted)', fontSize: 11, padding: 8 }}>Insufficient data</div>;

      const W = 500, H = 140, PL = 50, PR = 10, PT = 10, PB = 22;
      const cw = W - PL - PR, ch = H - PT - PB;
      const vals = pts.map(p => p.v);
      const minV = Math.min(...vals) - 1, maxV = Math.max(...vals) + 1;
      const range = maxV - minV;
      const x = (i) => PL + (i / (pts.length - 1)) * cw;
      const y = (v) => PT + ch - ((v - minV) / range) * ch;

      // Linear trend line
      const n = pts.length, xs = pts.map((_,i)=>i), ys = vals;
      const mx = xs.reduce((a,b)=>a+b)/n, my = ys.reduce((a,b)=>a+b)/n;
      const num = xs.reduce((s,xi,i)=>s+(xi-mx)*(ys[i]-my),0);
      const den = xs.reduce((s,xi)=>s+(xi-mx)**2,0);
      const slope = den ? num/den : 0;
      const intercept = my - slope*mx;
      const trendPts = `${x(0)},${y(intercept)} ${x(n-1)},${y(intercept+slope*(n-1))}`;
      const lineColor = color || 'var(--cyan)';
      const fillId = `cli_${fld}_${Math.random().toString(36).slice(2,6)}`;

      const linePts = pts.map((p,i)=>`${x(i)},${y(p.v)}`).join(' ');
      const areaPath = `M${x(0)},${y(pts[0].v)} ` + pts.slice(1).map((p,i)=>`L${x(i+1)},${y(p.v)}`).join(' ')
        + ` L${x(n-1)},${PT+ch} L${x(0)},${PT+ch} Z`;

      const yTicks = [minV+1, (minV+maxV)/2, maxV-1];

      return (
        <div>
          <div style={{ fontSize: 9, color: 'var(--muted)', padding: '0 0 2px 50px' }}>
            {label}  <span style={{ color: slope >= 0 ? 'var(--rose)' : 'var(--cyan)' }}>
              trend: {slope >= 0 ? '+' : ''}{(slope * 10).toFixed(2)}°F/decade
            </span>
          </div>
          <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
            <defs>
              <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={lineColor} stopOpacity="0.2" />
                <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
              </linearGradient>
            </defs>
            {yTicks.map((v,i) => (
              <line key={i} x1={PL} x2={W-PR} y1={y(v)} y2={y(v)}
                stroke="var(--border)" strokeWidth="0.5" strokeDasharray="3,3" />
            ))}
            <path d={areaPath} fill={`url(#${fillId})`} />
            <polyline points={linePts} fill="none" stroke={lineColor} strokeWidth="1.8" strokeLinejoin="round" />
            <polyline points={trendPts} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="4,2" />
            {pts.map((p,i) => (
              <circle key={i} cx={x(i)} cy={y(p.v)} r="2.5" fill={lineColor} opacity="0.9" />
            ))}
            {yTicks.map((v,i) => (
              <text key={i} x={PL-4} y={y(v)+3} textAnchor="end" fontSize="8.5" fill="var(--muted)" fontFamily="var(--mono)">{v.toFixed(1)}°F</text>
            ))}
            {pts.map((p,i) => (
              i % Math.max(1, Math.floor(n/6)) === 0 || i === n-1 ? (
                <text key={i} x={x(i)} y={H-3} textAnchor="middle" fontSize="8" fill="var(--muted)" fontFamily="var(--mono)">{p.y}</text>
              ) : null
            ))}
          </svg>
        </div>
      );
    }

    function PrecipChart({ annual }) {
      const pts = annual.filter(r => r.PRCP != null).map(r => ({
        y: parseInt(r.date.slice(0,4)), v: r.PRCP,
      }));
      if (pts.length < 2) return <div style={{ color: 'var(--muted)', fontSize: 11, padding: 8 }}>Insufficient data</div>;

      const W = 500, H = 120, PL = 50, PR = 10, PT = 10, PB = 22;
      const cw = W - PL - PR, ch = H - PT - PB;
      const maxV = Math.max(...pts.map(p=>p.v)) * 1.1;
      const bw = cw / pts.length * 0.7;
      const x = (i) => PL + (i / pts.length) * cw + bw * 0.15;
      const y = (v) => PT + ch - (v / maxV) * ch;
      const avg = pts.reduce((s,p)=>s+p.v,0)/pts.length;

      return (
        <div>
          <div style={{ fontSize: 9, color: 'var(--muted)', padding: '0 0 2px 50px' }}>
            ANNUAL PRECIPITATION (inches)  <span style={{ color: 'var(--cyan)' }}>avg: {avg.toFixed(1)}"</span>
          </div>
          <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
            <line x1={PL} x2={W-PR} y1={y(avg)} y2={y(avg)} stroke="var(--cyan)" strokeWidth="0.8" strokeDasharray="4,2" />
            {pts.map((p,i) => (
              <rect key={i} x={x(i)} y={y(p.v)} width={bw} height={ch-(y(p.v)-PT)}
                fill={p.v >= avg ? 'var(--cyan)' : 'var(--muted)'} opacity="0.7" />
            ))}
            {[0, maxV*0.5, maxV].map((v,i) => (
              <text key={i} x={PL-4} y={y(v)+3} textAnchor="end" fontSize="8.5" fill="var(--muted)" fontFamily="var(--mono)">{v.toFixed(0)}"</text>
            ))}
            {pts.map((p,i) => (
              i % Math.max(1, Math.floor(pts.length/6)) === 0 || i === pts.length-1 ? (
                <text key={i} x={x(i)+bw/2} y={H-3} textAnchor="middle" fontSize="8" fill="var(--muted)" fontFamily="var(--mono)">{p.y}</text>
              ) : null
            ))}
          </svg>
        </div>
      );
    }

    const TabBtn = ({ label, active }) => (
      <button onClick={() => setView(label)}
        style={{ padding: '2px 8px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
          border: '1px solid', borderColor: active ? 'var(--cyan)' : 'var(--border-2)',
          background: active ? 'rgba(56,189,248,.12)' : 'transparent',
          color: active ? 'var(--cyan)' : 'var(--text-2)' }}>
        {label}
      </button>
    );

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', gap: 6, minHeight: 0 }}>
        {/* Station list */}
        <div className="panel" style={{ width: 130, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="STATIONS" meta={`${stations.length} CITIES`} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {stations.length === 0 && <Empty msg="Loading NOAA data…" />}
            {stations.map(s => {
              const la = s.latest_annual || {};
              const trend = s.trend_per_year;
              return (
                <div key={s.city} onClick={() => setSel(s.city)}
                  style={{ padding: '5px 8px', cursor: 'pointer', borderBottom: '1px solid var(--border)',
                    background: sel === s.city ? 'rgba(56,189,248,.08)' : 'transparent',
                    borderLeft: sel === s.city ? '2px solid var(--cyan)' : '2px solid transparent' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: sel === s.city ? 'var(--cyan)' : 'var(--text)' }}>{s.city}</div>
                  <div style={{ fontSize: 9, color: 'var(--muted)' }}>{s.state}</div>
                  {la.TAVG != null && (
                    <div style={{ fontSize: 9, color: 'var(--text-2)' }}>{la.TAVG.toFixed(1)}°F avg</div>
                  )}
                  {trend != null && (
                    <div style={{ fontSize: 9, color: trend > 0 ? 'var(--rose)' : 'var(--cyan)' }}>
                      {trend > 0 ? '+' : ''}{(trend*10).toFixed(2)}°/dec
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Chart + data */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6, minHeight: 0 }}>
          {station ? (
            <>
              <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <PH title={`${station.city}, ${station.state} · CLIMATE HISTORY`}
                  meta={`${station.annual?.length || 0} YEARS · NOAA GHCND/GSOY`}
                  right={
                    <div style={{ display: 'flex', gap: 4 }}>
                      <TabBtn label="TEMP"   active={view==='TEMP'} />
                      <TabBtn label="PRECIP" active={view==='PRECIP'} />
                      <TabBtn label="TABLE"  active={view==='TABLE'} />
                    </div>
                  } />
                <div style={{ flex: 1, overflow: 'auto', minHeight: 0, padding: view !== 'TABLE' ? '8px 4px' : 0 }}>
                  {view === 'TEMP' && station.annual?.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <TrendChart annual={station.annual} field="TAVG" label="ANNUAL AVERAGE TEMPERATURE (°F)" color="var(--amber)" />
                      <TrendChart annual={station.annual} field="TMAX" label="ANNUAL MAXIMUM TEMPERATURE (°F)" color="var(--rose)" />
                      <TrendChart annual={station.annual} field="TMIN" label="ANNUAL MINIMUM TEMPERATURE (°F)" color="var(--cyan)" />
                    </div>
                  )}
                  {view === 'PRECIP' && station.annual?.length > 0 && (
                    <PrecipChart annual={station.annual} />
                  )}
                  {view === 'TABLE' && (
                    <table className="dense">
                      <thead><tr>
                        <th>YEAR</th>
                        <th className="num">AVG °F</th>
                        <th className="num">MAX °F</th>
                        <th className="num">MIN °F</th>
                        <th className="num">PRECIP"</th>
                        <th className="num">REC HI</th>
                        <th className="num">REC LO</th>
                      </tr></thead>
                      <tbody>
                        {(station.annual || []).slice().reverse().map((r, i) => (
                          <tr key={i}>
                            <td className="lbl">{r.date?.slice(0,4)}</td>
                            <td className="num">{r.TAVG?.toFixed(1) ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--rose)' }}>{r.TMAX?.toFixed(1) ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--cyan)' }}>{r.TMIN?.toFixed(1) ?? '—'}</td>
                            <td className="num">{r.PRCP?.toFixed(2) ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--amber)' }}>{r.EMXT ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--violet)' }}>{r.EMNT ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {!station.annual?.length && <Empty msg="Loading climate data from NOAA CDO…" />}
                </div>
                <div style={{ borderTop: '1px solid var(--border)', padding: '3px 8px', fontSize: 9, color: 'var(--muted)' }}>
                  Source: NOAA Climate Data Online (CDO) · GHCND/GSOY · Standard units °F / inches
                </div>
              </div>

              {/* All-cities summary grid */}
              <div className="panel" style={{ flexShrink: 0 }}>
                <PH title="US CITY COMPARISON · LATEST ANNUAL" meta="TEMP °F · PRECIP INCHES" />
                <div style={{ overflowX: 'auto' }}>
                  <table className="dense">
                    <thead><tr>
                      <th>CITY</th>
                      <th className="num">AVG °F</th>
                      <th className="num">MAX °F</th>
                      <th className="num">MIN °F</th>
                      <th className="num">PRECIP"</th>
                      <th className="num">REC HI</th>
                      <th className="num">REC LO</th>
                      <th className="num">TREND/DEC</th>
                    </tr></thead>
                    <tbody>
                      {stations.map(s => {
                        const la = s.latest_annual || {};
                        const tr = s.trend_per_year;
                        return (
                          <tr key={s.city} style={{ cursor: 'pointer', background: sel===s.city?'rgba(56,189,248,.05)':undefined }}
                            onClick={() => setSel(s.city)}>
                            <td><span className="lbl">{s.city}</span> <span className="mut">{s.state}</span></td>
                            <td className="num">{la.TAVG?.toFixed(1) ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--rose)' }}>{la.TMAX?.toFixed(1) ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--cyan)' }}>{la.TMIN?.toFixed(1) ?? '—'}</td>
                            <td className="num">{la.PRCP?.toFixed(1) ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--amber)' }}>{la.EMXT ?? '—'}</td>
                            <td className="num" style={{ color: 'var(--violet)' }}>{la.EMNT ?? '—'}</td>
                            <td className="num" style={{ color: tr == null ? 'var(--muted)' : tr > 0 ? 'var(--rose)' : 'var(--mint)' }}>
                              {tr != null ? (tr > 0 ? '+' : '') + (tr*10).toFixed(2) + '°' : '—'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="panel" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Empty msg="Fetching NOAA CDO climate data…" />
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Merge into window.DeltaPanels ────────────────────────────────────────────
  Object.assign(window.DeltaPanels, {
    BondsPanel,
    ForexPanel,
    FredPanel,
    CvePanel,
    LaunchesPanel,
    ConflictsPanel,
    SanctionsPanel,
    NeoPanel,
    SolarPanel,
    OutagesPanel,
    PopulationPanel,
    EquityPanel,
    OilPanel,
    GasPanel,
    NuclearPanel,
    RenewablesPanel,
    GridPanel,
    ClimatePanel,
  });
})();
