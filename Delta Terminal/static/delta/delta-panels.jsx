// delta-panels.jsx — tab panel components
// Exposes window.DeltaPanels

(function () {
  const { useState, useMemo, useEffect, useRef } = React;
  const { fmt, fmtInt, fmtAbbr } = window.DeltaData;
  const DeltaMap = window.DeltaMap;

  // ============= shared bits =============
  function PanelHead({ title, meta, right }) {
    return (
      <div className="panel-head">
        <span>◆ {title}</span>
        <span style={{ flex: 1 }} />
        {meta && <span className="meta">{meta}</span>}
        {right}
      </div>
    );
  }

  function useSort(rows, initial) {
    const [sort, setSort] = useState(initial || { key: null, dir: 'desc' });
    const sorted = useMemo(() => {
      if (!sort.key) return rows;
      const r = [...rows];
      r.sort((a, b) => {
        const x = a[sort.key], y = b[sort.key];
        if (x == null) return 1; if (y == null) return -1;
        if (typeof x === 'number' && typeof y === 'number') return sort.dir === 'asc' ? x - y : y - x;
        return sort.dir === 'asc' ? String(x).localeCompare(String(y)) : String(y).localeCompare(String(x));
      });
      return r;
    }, [rows, sort.key, sort.dir]);
    const toggle = (k) => setSort(s => s.key === k ? { key: k, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: 'desc' });
    return [sorted, sort, toggle];
  }

  function Th({ k, children, sort, toggle, align }) {
    const active = sort && sort.key === k;
    return (
      <th onClick={() => toggle(k)} style={{ textAlign: align || 'left' }}>
        {children}{active ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
      </th>
    );
  }

  function Filter({ value, onChange, placeholder }) {
    return (
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder || 'filter… (/)'}
        style={{
          background: 'var(--bg)', border: '1px solid var(--border-2)',
          color: 'var(--text)', font: 'inherit', fontFamily: 'var(--mono)',
          padding: '2px 6px', width: 180, fontSize: 11, outline: 'none',
        }} />
    );
  }

  // ============= MARKETS =============
  function QuotesTable({ rows, columns, onRowClick, selectedTicker }) {
    const [sorted, sort, toggle] = useSort(rows, { key: 'change_pct', dir: 'desc' });
    return (
      <table className="dense">
        <thead><tr>
          {columns.map(c => <Th key={c.key} k={c.key} sort={sort} toggle={toggle} align={c.align}>{c.label}</Th>)}
        </tr></thead>
        <tbody>
          {sorted.map(r => {
            const tk = r.ticker || r.symbol;
            return (
              <tr key={tk}
                className={r._dir === 'up' ? 'flash-up' : r._dir === 'down' ? 'flash-down' : ''}
                style={{ cursor: onRowClick ? 'pointer' : undefined, background: selectedTicker === tk ? 'rgba(56,189,248,.07)' : undefined }}
                onClick={onRowClick ? () => onRowClick(r) : undefined}>
                {columns.map(c => (
                  <td key={c.key} className={c.num ? 'num' : ''} style={{ color: c.color ? (r.color === 'up' || r.color === 'green') ? 'var(--mint)' : 'var(--rose)' : undefined }}>
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

  function TickerNewsDrawer({ ticker, onClose }) {
    const [articles, setArticles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState(null);

    useEffect(() => {
      if (!ticker) return;
      setLoading(true); setErr(null); setArticles([]);
      fetch(`http://localhost:8000/api/ticker-news?symbol=${encodeURIComponent(ticker)}&days=7`)
        .then(r => r.json())
        .then(d => { setArticles(d.articles || []); setLoading(false); })
        .catch(e => { setErr(String(e)); setLoading(false); });
    }, [ticker]);

    const fmtAgo = ts => {
      const s = Math.floor(Date.now()/1000 - ts);
      if (s < 3600) return Math.floor(s/60) + 'm ago';
      if (s < 86400) return Math.floor(s/3600) + 'h ago';
      return Math.floor(s/86400) + 'd ago';
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
        <div style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: 14 }}>{ticker}</span>
          <span style={{ color: 'var(--muted)', fontSize: 10 }}>NEWS · 7 DAYS</span>
          <div style={{ flex: 1 }} />
          <button className="btn" onClick={onClose} style={{ padding: '1px 8px', fontSize: 10 }}>✕ CLOSE</button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '4px 0', minHeight: 0 }}>
          {loading && <div style={{ padding: 16, color: 'var(--muted)', fontSize: 11 }}>Loading news…</div>}
          {err && <div style={{ padding: 16, color: 'var(--rose)', fontSize: 11 }}>{err}</div>}
          {!loading && articles.length === 0 && <div style={{ padding: 16, color: 'var(--muted)', fontSize: 11 }}>No recent articles</div>}
          {articles.map((a, i) => (
            <div key={i} style={{ padding: '7px 10px', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
              onClick={() => a.url && window.open(a.url, '_blank')}>
              <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.35, marginBottom: 3 }}>{a.headline}</div>
              <div style={{ display: 'flex', gap: 8, fontSize: 9, color: 'var(--muted)' }}>
                <span className="lbl">{a.source}</span>
                <span>{fmtAgo(a.datetime)}</span>
              </div>
              {a.summary && (
                <div style={{ fontSize: 10, color: 'var(--text-2)', marginTop: 3, lineHeight: 1.4 }}>
                  {a.summary.slice(0, 200)}{a.summary.length > 200 ? '…' : ''}
                </div>
              )}
            </div>
          ))}
        </div>
        <div style={{ borderTop: '1px solid var(--border)', padding: '3px 8px', fontSize: 9, color: 'var(--muted)' }}>
          Source: Finnhub Company News · Click headline to open article
        </div>
      </div>
    );
  }

  function MarketsPanel({ snap }) {
    const [newsTicker, setNewsTicker] = useState(null);

    const colsEq = [
      { key: 'ticker', label: 'SYM', render: r => <span className="lbl">{r.ticker}</span> },
      { key: 'name', label: 'NAME', render: r => <span className="mut">{r.name}</span> },
      { key: 'price', label: 'PRICE', align: 'right', num: true, render: r => fmt(r.price) },
      { key: 'change', label: 'Δ', align: 'right', num: true, color: true,
        render: r => <span>{r.arrow} {fmt(r.change)}</span> },
      { key: 'change_pct', label: '%', align: 'right', num: true, color: true,
        render: r => <span>{r.change_pct >= 0 ? '+' : ''}{r.change_pct.toFixed(2)}%</span> },
      { key: 'day_high', label: 'HI', align: 'right', num: true, render: r => fmt(r.day_high) },
      { key: 'day_low', label: 'LO', align: 'right', num: true, render: r => fmt(r.day_low) },
      { key: 'volume', label: 'VOL', align: 'right', num: true, render: r => <span className="mut">{fmtAbbr(r.volume)}</span> },
    ];
    const colsCrypto = [
      { key: 'symbol', label: 'PAIR', render: r => <span className="lbl">{r.symbol.replace('USDT','/USDT')}</span> },
      { key: 'name', label: 'NAME', render: r => <span className="mut">{r.name}</span> },
      { key: 'price', label: 'PRICE $', align: 'right', num: true, render: r => fmt(r.price, r.price < 1 ? 4 : 2) },
      { key: 'change_pct_24h', label: '24h %', align: 'right', num: true, color: true,
        render: r => <span>{r.arrow} {Math.abs(r.change_pct_24h).toFixed(2)}%</span> },
      { key: 'high_24h', label: 'HI', align: 'right', num: true, render: r => fmt(r.high_24h) },
      { key: 'low_24h', label: 'LO', align: 'right', num: true, render: r => fmt(r.low_24h) },
      { key: 'volume_24h', label: 'VOL', align: 'right', num: true, render: r => <span className="mut">${fmtAbbr(r.volume_24h)}</span> },
    ];

    const sparkPoints = (seed, up) => {
      let x = 0;
      const pts = [];
      let s = seed;
      for (let i = 0; i < 20; i++) {
        s = (s * 9301 + 49297) % 233280;
        x += (s / 233280 - 0.45);
        pts.push(x);
      }
      const min = Math.min(...pts), max = Math.max(...pts);
      const range = max - min || 1;
      return pts.map((p, i) => `${i * (60 / 19)},${20 - ((p - min) / range) * 18}`).join(' ');
    };

    const handleRowClick = (r) => {
      const tk = r.ticker || r.symbol;
      // Only open news for stocks/ETFs that have a news-friendly ticker (skip indices like ^GSPC)
      if (!tk || tk.startsWith('^')) return;
      setNewsTicker(prev => prev === tk ? null : tk);
    };

    const tables = (
      <div style={{ display: 'grid', gridTemplateRows: 'auto 1fr 1fr', gap: 6, height: '100%' }}>
        {/* Sparkline strip */}
        <div className="panel" style={{ padding: '6px 8px' }}>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', overflowX: 'auto' }}>
            {snap.indices.slice(0, 8).map((q, i) => (
              <div key={q.ticker} style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                <div>
                  <div style={{ color: 'var(--cyan)', fontSize: 10, letterSpacing: '.08em' }}>{q.ticker.replace('^','')}</div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{fmt(q.price)}</div>
                  <div className={q.color} style={{ fontSize: 10 }}>{q.arrow} {q.change_pct.toFixed(2)}%</div>
                </div>
                <svg width={60} height={20}>
                  <polyline points={sparkPoints(i + 1, q.color === 'up')}
                    fill="none" stroke={q.color === 'up' ? 'var(--mint)' : 'var(--rose)'} strokeWidth="1" opacity="0.9" />
                </svg>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, minHeight: 0 }}>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PanelHead title="INDICES · ETFs · GLOBAL" meta="DELAYED 15M · NYSE/NASDAQ/LSE/TSE" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuotesTable rows={snap.indices} columns={colsEq} onRowClick={handleRowClick} selectedTicker={newsTicker} />
            </div>
          </div>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PanelHead title="CRYPTOCURRENCIES" meta="REAL-TIME · BINANCE STREAM" right={<span className="pill pill-mint blink">● LIVE</span>} />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuotesTable rows={snap.crypto} columns={colsCrypto} />
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, minHeight: 0 }}>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PanelHead title="TECH EQUITIES" meta="US LARGE CAP · CLICK ROW FOR NEWS" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuotesTable rows={snap.tech} columns={colsEq} onRowClick={handleRowClick} selectedTicker={newsTicker} />
            </div>
          </div>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PanelHead title="MACRO · FX · COMMODITIES" meta="CME · ICE · FOREX · CLICK ROW FOR NEWS" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuotesTable rows={snap.macro} columns={colsEq} onRowClick={handleRowClick} selectedTicker={newsTicker} />
            </div>
          </div>
        </div>
      </div>
    );

    if (!newsTicker) {
      return <div style={{ padding: 6, height: '100%' }}>{tables}</div>;
    }

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 6, height: '100%', padding: 6 }}>
        {tables}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <TickerNewsDrawer ticker={newsTicker} onClose={() => setNewsTicker(null)} />
        </div>
      </div>
    );
  }

  // ============= WORLD (combined: aircraft + ships) =============
  function WorldPanel({ snap, sel, setSel }) {
    // sel: {kind, id} | null
    const [show, setShow] = useState({ aircraft: true, ships: true });
    const planes = snap.aircraft;
    const ships = snap.ships;
    const airborne = planes.filter(p => !p.on_ground).length;
    const underway = ships.filter(s => s.nav_status === 0 || s.nav_status === 8).length;

    const layers = useMemo(() => {
      const l = [];
      if (show.aircraft) l.push({ kind: 'aircraft', items: planes });
      if (show.ships)    l.push({ kind: 'ships',    items: ships });
      return l;
    }, [show, planes, ships]);

    const selObj = useMemo(() => {
      if (!sel) return null;
      if (sel.kind === 'aircraft') return planes.find(p => p.icao24 === sel.id);
      if (sel.kind === 'ships')    return ships.find(s => s.mmsi === sel.id);
      return null;
    }, [sel, planes, ships]);

    return (
      <div style={{ height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
          <PanelHead title="COMBINED WORLD TRACKER · ALL VEHICLES"
            meta={`AIRCRAFT ${planes.length} (${airborne} airborne) · VESSELS ${ships.length} (${underway} under way)`}
            right={
              <div style={{ display: 'flex', gap: 4 }}>
                <button className={`btn ${show.aircraft ? 'on' : ''}`} onClick={() => setShow(s => ({ ...s, aircraft: !s.aircraft }))}>✈ AIRCRAFT</button>
                <button className={`btn ${show.ships ? 'on' : ''}`} onClick={() => setShow(s => ({ ...s, ships: !s.ships }))}>⚓ SHIPS</button>
                <span className="pill pill-mint blink" style={{ marginLeft: 6 }}>● LIVE</span>
              </div>
            } />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap layers={layers}
              selected={sel}
              onSelect={(id, kind) => setSel(sel && sel.id === id ? null : { kind, id })}
              center={[25, 20]} zoom={2.5} />

            {/* Stats card (top-left) */}
            <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 500,
              background: 'var(--surface)', border: '1px solid var(--border-2)', padding: '8px 12px',
              fontSize: 11, minWidth: 200, boxShadow: '0 4px 12px rgba(0,0,0,.5)' }}>
              <div style={{ color: 'var(--cyan)', fontSize: 10, letterSpacing: '.12em', marginBottom: 6 }}>GLOBAL FLEET · LIVE</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', rowGap: 3, columnGap: 14 }}>
                <span><span className="mut">✈</span> AIRCRAFT</span> <span className="num lbl">{fmtInt(planes.length)}</span>
                <span className="mut" style={{ paddingLeft: 16 }}>airborne</span> <span className="num up">{fmtInt(airborne)}</span>
                <span className="mut" style={{ paddingLeft: 16 }}>on ground</span> <span className="num dim">{fmtInt(planes.length - airborne)}</span>
                <span><span className="mut">⚓</span> VESSELS</span> <span className="num lbl">{fmtInt(ships.length)}</span>
                <span className="mut" style={{ paddingLeft: 16 }}>under way</span> <span className="num up">{fmtInt(underway)}</span>
                <span className="mut" style={{ paddingLeft: 16 }}>anchored</span> <span className="num dim">{fmtInt(ships.length - underway)}</span>
              </div>
            </div>

            {/* Legend (bottom-left) */}
            <div style={{ position: 'absolute', left: 10, bottom: 10, zIndex: 500,
              background: 'var(--surface)', border: '1px solid var(--border-2)', padding: '6px 10px', fontSize: 10 }}>
              <div style={{ color: 'var(--cyan)', letterSpacing: '.08em', marginBottom: 4 }}>LEGEND</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'auto auto', gap: '2px 12px' }}>
                <span><span style={{ color: 'var(--mint)' }}>▲</span> aircraft (airborne)</span>
                <span><span style={{ color: 'var(--muted)' }}>▲</span> aircraft (ground)</span>
                <span><span style={{ color: 'var(--cyan)' }}>▬</span> cargo</span>
                <span><span style={{ color: 'var(--amber)' }}>▬</span> tanker</span>
                <span><span style={{ color: 'var(--violet)' }}>▬</span> passenger</span>
                <span><span style={{ color: 'var(--mint)' }}>▬</span> fishing</span>
              </div>
            </div>

            {/* Selected info card (bottom-right) */}
            {selObj && (
              <div style={{ position: 'absolute', right: 10, bottom: 10, zIndex: 500,
                background: 'var(--surface)', border: '1px solid var(--cyan)', padding: '10px 14px',
                fontSize: 11, minWidth: 260, boxShadow: '0 8px 24px rgba(0,0,0,.7)' }}>
                {sel.kind === 'aircraft' ? (
                  <>
                    <div style={{ color: 'var(--cyan)', fontSize: 13, marginBottom: 4 }}>✈ {selObj.callsign} <span className="mut">· {selObj.type}</span></div>
                    <div>ICAO <span className="lbl">{selObj.icao24}</span> · {selObj.country}</div>
                    <div>POS {selObj.lat.toFixed(3)}°  {selObj.lon.toFixed(3)}°</div>
                    <div>ALT <span className="up">{fmtInt(selObj.altitude_ft)} ft</span>  SPD <span className="up">{selObj.speed_kts} kts</span></div>
                    <div>HDG {selObj.heading_arrow} {selObj.heading}°  VS {selObj.vertical_rate >= 0 ? '+' : ''}{selObj.vertical_rate} fpm</div>
                    <div className="mut" style={{ marginTop: 4, fontSize: 10 }}>{selObj.fl}</div>
                  </>
                ) : (
                  <>
                    <div style={{ color: 'var(--cyan)', fontSize: 13, marginBottom: 4 }}>⚓ {selObj.name}</div>
                    <div>MMSI <span className="lbl">{selObj.mmsi}</span> · {selObj.flag}</div>
                    <div>TYPE <span className="mut">{selObj.type_name}</span>  DWT <span className="mut">{fmtInt(selObj.dwt)}t</span></div>
                    <div>POS {selObj.lat.toFixed(3)}°  {selObj.lon.toFixed(3)}°</div>
                    <div>SPD <span className="up">{selObj.speed_kts} kts</span>  COG {selObj.heading_arrow} {selObj.course}°</div>
                    <div className="mut" style={{ marginTop: 4 }}>→ <span className="lbl">{selObj.destination}</span></div>
                  </>
                )}
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)', fontSize: 10, color: 'var(--muted)' }}>
                  click marker again to deselect
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ============= AIRCRAFT =============
  function AircraftPanel({ snap, sel, setSel }) {
    const [filter, setFilter] = useState('');
    const planes = snap.aircraft;
    const filtered = useMemo(() => {
      if (!filter) return planes;
      const f = filter.toLowerCase();
      return planes.filter(p =>
        p.callsign.toLowerCase().includes(f) ||
        p.country.toLowerCase().includes(f) ||
        p.icao24.includes(f) ||
        p.type.toLowerCase().includes(f));
    }, [planes, filter]);
    const airborne = planes.filter(p => !p.on_ground).length;
    const [sorted, sort, toggle] = useSort(filtered, { key: 'altitude_ft', dir: 'desc' });
    const selObj = planes.find(p => p.icao24 === sel);

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 460px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative' }}>
          <PanelHead title="GLOBAL AIRCRAFT POSITIONS" meta={`OPENSKY NETWORK · ${planes.length} CONTACTS · ${airborne} AIRBORNE`}
            right={<span className="pill pill-mint blink">● LIVE 15s</span>} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap kind="aircraft" items={planes} selectedId={sel} onSelect={setSel} center={[30, 0]} zoom={2.5} />
            {/* Legend */}
            <div style={{ position: 'absolute', left: 10, bottom: 10, zIndex: 500, background: 'rgba(11,20,34,.9)',
              border: '1px solid var(--border-2)', padding: '6px 10px', fontSize: 10 }}>
              <div style={{ color: 'var(--cyan)', letterSpacing: '.08em', marginBottom: 4 }}>LEGEND</div>
              <div style={{ display: 'flex', gap: 14 }}>
                <span><span style={{ color: 'var(--mint)' }}>▲</span> AIRBORNE</span>
                <span><span style={{ color: 'var(--muted)' }}>▲</span> ON GROUND</span>
                <span><span style={{ color: 'var(--cyan)' }}>▲</span> SELECTED</span>
              </div>
            </div>
            {selObj && (
              <div style={{ position: 'absolute', right: 10, bottom: 10, zIndex: 500, background: 'rgba(11,20,34,.94)',
                border: '1px solid var(--cyan)', padding: '8px 12px', fontSize: 11, minWidth: 240,
                boxShadow: '0 8px 24px rgba(0,0,0,.7)' }}>
                <div style={{ color: 'var(--cyan)', fontSize: 13, marginBottom: 4 }}>{selObj.callsign} <span className="mut">· {selObj.type}</span></div>
                <div>ICAO <span className="lbl">{selObj.icao24}</span> · {selObj.country}</div>
                <div>LAT {selObj.lat.toFixed(3)}°  LON {selObj.lon.toFixed(3)}°</div>
                <div>ALT <span className="up">{fmtInt(selObj.altitude_ft)} ft</span>  SPD <span className="up">{selObj.speed_kts} kts</span></div>
                <div>HDG {selObj.heading_arrow} {selObj.heading}°  VS {selObj.vertical_rate >= 0 ? '+' : ''}{selObj.vertical_rate} fpm</div>
                <div className="mut" style={{ marginTop: 4, fontSize: 10 }}>{selObj.fl}</div>
              </div>
            )}
          </div>
        </div>

        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="TRAFFIC LIST" meta={`${filtered.length} OF ${planes.length}`} right={<Filter value={filter} onChange={setFilter} placeholder="filter callsign…" />} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <Th k="callsign" sort={sort} toggle={toggle}>CALLSIGN</Th>
                <Th k="type" sort={sort} toggle={toggle}>TYPE</Th>
                <Th k="country" sort={sort} toggle={toggle}>COUNTRY</Th>
                <Th k="altitude_ft" sort={sort} toggle={toggle} align="right">ALT</Th>
                <Th k="speed_kts" sort={sort} toggle={toggle} align="right">SPD</Th>
                <Th k="heading" sort={sort} toggle={toggle} align="right">HDG</Th>
              </tr></thead>
              <tbody>
                {sorted.slice(0, 200).map(p => (
                  <tr key={p.icao24} className={p.icao24 === sel ? 'selected' : ''}
                      style={{ opacity: p.on_ground ? 0.55 : 1 }}
                      onClick={() => setSel(p.icao24)}>
                    <td><span className="up">{p.callsign}</span></td>
                    <td><span className="mut">{p.type}</span></td>
                    <td><span className="mut">{p.country.slice(0, 14)}</span></td>
                    <td className="num">{p.on_ground ? <span className="dim">GND</span> : fmtInt(p.altitude_ft)}</td>
                    <td className="num">{p.speed_kts}</td>
                    <td className="num"><span className="lbl">{p.heading_arrow}</span> {p.heading}°</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ============= SHIPS =============
  function ShipsPanel({ snap, sel, setSel }) {
    const [filter, setFilter] = useState('');
    const ships = snap.ships;
    const filtered = useMemo(() => {
      if (!filter) return ships;
      const f = filter.toLowerCase();
      return ships.filter(s =>
        s.name.toLowerCase().includes(f) ||
        s.type_name.toLowerCase().includes(f) ||
        s.flag.toLowerCase().includes(f) ||
        s.destination.toLowerCase().includes(f));
    }, [ships, filter]);
    const underway = ships.filter(s => s.nav_status === 0 || s.nav_status === 8).length;
    const [sorted, sort, toggle] = useSort(filtered, { key: 'speed_kts', dir: 'desc' });
    const selObj = ships.find(s => s.mmsi === sel);

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 480px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative' }}>
          <PanelHead title="AIS VESSEL TRAFFIC · GLOBAL" meta={`${ships.length} CONTACTS · ${underway} UNDER WAY · AISHUB / KYSTVERKET`}
            right={<span className="pill pill-amber blink">● AIS 30s</span>} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap kind="ships" items={ships} selectedId={sel} onSelect={setSel} center={[25, 50]} zoom={2.5} />
            <div style={{ position: 'absolute', left: 10, bottom: 10, zIndex: 500, background: 'rgba(11,20,34,.9)',
              border: '1px solid var(--border-2)', padding: '6px 10px', fontSize: 10 }}>
              <div style={{ color: 'var(--cyan)', letterSpacing: '.08em', marginBottom: 4 }}>VESSEL TYPE</div>
              <div style={{ display: 'flex', gap: 14 }}>
                <span><span style={{ color: 'var(--cyan)' }}>■</span> CARGO</span>
                <span><span style={{ color: 'var(--amber)' }}>■</span> TANKER</span>
                <span><span style={{ color: 'var(--violet)' }}>■</span> PASSENGER</span>
                <span><span style={{ color: 'var(--mint)' }}>■</span> FISHING</span>
                <span><span style={{ color: 'var(--text-2)' }}>■</span> OTHER</span>
              </div>
            </div>
            {selObj && (
              <div style={{ position: 'absolute', right: 10, bottom: 10, zIndex: 500, background: 'rgba(11,20,34,.94)',
                border: '1px solid var(--cyan)', padding: '8px 12px', fontSize: 11, minWidth: 270 }}>
                <div style={{ color: 'var(--cyan)', fontSize: 13, marginBottom: 4 }}>{selObj.name}</div>
                <div>MMSI <span className="lbl">{selObj.mmsi}</span> · {selObj.callsign} · {selObj.flag}</div>
                <div>TYPE <span className="mut">{selObj.type_name}</span>  DWT <span className="mut">{fmtInt(selObj.dwt)}t</span></div>
                <div>LAT {selObj.lat.toFixed(3)}°  LON {selObj.lon.toFixed(3)}°</div>
                <div>SPD <span className="up">{selObj.speed_kts} kts</span>  COG {selObj.heading_arrow} {selObj.course}°</div>
                <div>STATUS <span className="mut">{selObj.status_name}</span></div>
                <div className="mut" style={{ marginTop: 4 }}>→ DESTINATION <span className="lbl">{selObj.destination}</span></div>
              </div>
            )}
          </div>
        </div>

        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="VESSEL REGISTRY" meta={`${filtered.length} OF ${ships.length}`} right={<Filter value={filter} onChange={setFilter} placeholder="filter name / type…" />} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <Th k="name" sort={sort} toggle={toggle}>VESSEL</Th>
                <Th k="type_name" sort={sort} toggle={toggle}>TYPE</Th>
                <Th k="flag" sort={sort} toggle={toggle}>FLAG</Th>
                <Th k="speed_kts" sort={sort} toggle={toggle} align="right">SPD</Th>
                <Th k="course" sort={sort} toggle={toggle} align="right">COG</Th>
                <Th k="destination" sort={sort} toggle={toggle}>DEST</Th>
              </tr></thead>
              <tbody>
                {sorted.slice(0, 180).map(s => (
                  <tr key={s.mmsi} className={s.mmsi === sel ? 'selected' : ''}
                      style={{ opacity: s.speed_kts < 0.5 ? 0.55 : 1 }}
                      onClick={() => setSel(s.mmsi)}>
                    <td><span className="up">{s.name.slice(0, 22)}</span></td>
                    <td><span className="mut">{s.type_name}</span></td>
                    <td><span className="violet">{s.flag}</span></td>
                    <td className="num">{s.speed_kts}</td>
                    <td className="num"><span className="lbl">{s.heading_arrow}</span> {s.course}°</td>
                    <td><span className="mut">{s.destination}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ============= SPACE =============
  function SpacePanel({ snap }) {
    const { stations, sats, starlink_count, active_count } = snap.space;
    const orbitColor = { LEO: 'pill-cyan', MEO: 'pill-mint', GEO: 'pill-violet', HEO: 'pill-amber' };
    return (
      <div style={{ display: 'grid', gridTemplateRows: '1fr auto', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative' }}>
          <PanelHead title="LOW-EARTH ORBIT · CREWED STATIONS" meta={`ACTIVE ${fmtInt(active_count)} · STARLINK ${fmtInt(starlink_count)}`}
            right={<span className="pill pill-violet blink">● TELEMETRY 60s</span>} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap kind="space" items={stations} center={[20, 0]} zoom={2} />
            <div style={{ position: 'absolute', left: 10, top: 10, zIndex: 500, display: 'flex', gap: 6 }}>
              {stations.map(s => (
                <div key={s.norad_id} style={{ background: 'rgba(11,20,34,.94)', border: '1px solid var(--border-2)',
                  padding: '8px 12px', fontSize: 11, minWidth: 230 }}>
                  <div style={{ color: 'var(--violet)', fontSize: 13, marginBottom: 4 }}>◈ {s.name}</div>
                  <div>NORAD <span className="lbl">{s.norad_id}</span></div>
                  <div>POS <span className="up">{s.ground_track}</span></div>
                  <div>ALT <span className="up">{s.altitude_km} km</span> <span className="mut">({s.altitude_mi} mi)</span></div>
                  <div>VEL <span className="up">{s.velocity_kms} km/s</span> <span className="mut">({fmtInt(s.velocity_mph)} mph)</span></div>
                  <div>VIS <span className={s.visibility === 'daylight' ? 'warn' : 'mut'}>{s.visibility.toUpperCase()}</span></div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="panel" style={{ display: 'flex', flexDirection: 'column', maxHeight: 240 }}>
          <PanelHead title="TRACKED ORBITAL OBJECTS · CelesTrak TLE" meta={`${sats.length} VISIBLE FROM CATALOG`} />
          <div style={{ overflow: 'auto' }}>
            <table className="dense">
              <thead><tr>
                <th>NAME</th><th>NORAD</th><th>ORBIT</th>
                <th style={{ textAlign:'right' }}>INC°</th>
                <th style={{ textAlign:'right' }}>APO km</th>
                <th style={{ textAlign:'right' }}>PERI km</th>
                <th style={{ textAlign:'right' }}>PERIOD min</th>
                <th style={{ textAlign:'right' }}>ECC</th>
              </tr></thead>
              <tbody>
                {sats.map(s => (
                  <tr key={s.norad_id}>
                    <td><span className="up">{s.name}</span></td>
                    <td><span className="lbl">{s.norad_id}</span></td>
                    <td><span className={`pill ${orbitColor[s.orbit_type] || ''}`}>{s.orbit_type}</span></td>
                    <td className="num">{s.inclination}</td>
                    <td className="num">{fmtInt(s.apogee_km)}</td>
                    <td className="num">{fmtInt(s.perigee_km)}</td>
                    <td className="num">{s.period_min}</td>
                    <td className="num mut">{s.eccentricity.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ============= WEATHER =============
  function WeatherPanel({ snap, sel, setSel }) {
    const wx = snap.weather;
    const [sorted, sort, toggle] = useSort(wx, { key: 'temp_c', dir: 'desc' });
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 520px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="GLOBAL WEATHER · OBSERVATIONS" meta={`${wx.length} STATIONS · OPEN-METEO · UPDATED 14:32 UTC`} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap kind="weather" items={wx} selectedId={sel} onSelect={setSel} center={[25, 0]} zoom={2} />
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="STATION READINGS" />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <Th k="city" sort={sort} toggle={toggle}>CITY</Th>
                <th>COND</th>
                <Th k="temp_c" sort={sort} toggle={toggle} align="right">°C</Th>
                <Th k="temp_f" sort={sort} toggle={toggle} align="right">°F</Th>
                <Th k="humidity" sort={sort} toggle={toggle} align="right">RH%</Th>
                <Th k="wind_speed_kph" sort={sort} toggle={toggle} align="right">WIND</Th>
                <th>DIR</th>
                <Th k="precipitation_mm" sort={sort} toggle={toggle} align="right">PRCP</Th>
              </tr></thead>
              <tbody>
                {sorted.map(w => (
                  <tr key={w.city} className={w.city === sel ? 'selected' : ''} onClick={() => setSel(w.city)}>
                    <td><span className="up">{w.city}</span></td>
                    <td>{w.icon} <span className="mut">{w.condition}</span></td>
                    <td className="num" style={{ color: w.temp_c > 30 ? 'var(--rose)' : w.temp_c < 0 ? 'var(--cyan)' : undefined }}>{w.temp_c.toFixed(1)}</td>
                    <td className="num mut">{w.temp_f.toFixed(1)}</td>
                    <td className="num" style={{ color: w.humidity > 80 ? 'var(--cyan)' : undefined }}>{w.humidity}</td>
                    <td className="num" style={{ color: w.wind_speed_kph > 50 ? 'var(--amber)' : undefined }}>{w.wind_speed_kph}</td>
                    <td><span className="lbl">{w.wind_direction_str}</span></td>
                    <td className="num" style={{ color: w.precipitation_mm > 0 ? 'var(--cyan)' : 'var(--dim)' }}>{w.precipitation_mm.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ============= EARTHQUAKES =============
  function QuakesPanel({ snap, sel, setSel }) {
    const q = snap.quakes;
    const all = useMemo(() => [...q.significant, ...q.recent], [q]);
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 540px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="GLOBAL SEISMIC ACTIVITY · 30 DAYS"
            meta={`LAST HR ${q.hourly_count} · TODAY ${q.daily_count}${q.largest_today ? ` · LARGEST ${q.largest_today.magnitude_str} ${q.largest_today.place.slice(0,28)}` : ''}`}
            right={<span className="pill pill-rose blink">● USGS LIVE</span>} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap kind="earthquakes" items={all} selectedId={sel} onSelect={setSel} center={[15, 130]} zoom={2.2} />
            <div style={{ position: 'absolute', left: 10, bottom: 10, zIndex: 500, background: 'rgba(11,20,34,.9)',
              border: '1px solid var(--border-2)', padding: '6px 10px', fontSize: 10 }}>
              <div style={{ color: 'var(--cyan)', marginBottom: 4 }}>MAGNITUDE</div>
              <div style={{ display: 'flex', gap: 12 }}>
                <span><span style={{ color: 'var(--rose)' }}>●</span> ≥7.0</span>
                <span><span style={{ color: 'var(--amber)' }}>●</span> ≥6.0</span>
                <span><span style={{ color: 'var(--amber)' }}>●</span> ≥5.0</span>
                <span><span style={{ color: 'var(--cyan)' }}>●</span> ≥4.0</span>
                <span><span style={{ color: 'var(--muted)' }}>●</span> &lt;4.0</span>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minHeight: 0 }}>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
            <PanelHead title="SIGNIFICANT EVENTS · M≥4.8 (30 days)" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuakesTable rows={q.significant} sel={sel} setSel={setSel} />
            </div>
          </div>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
            <PanelHead title="LAST HOUR" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuakesTable rows={q.recent} sel={sel} setSel={setSel} />
            </div>
          </div>
        </div>
      </div>
    );
  }
  function QuakesTable({ rows, sel, setSel }) {
    return (
      <table className="dense">
        <thead><tr>
          <th style={{ textAlign:'right' }}>MAG</th><th>LOCATION</th>
          <th style={{ textAlign:'right' }}>DEPTH</th>
          <th>WHEN</th><th>TSU</th><th>ALERT</th>
          <th style={{ textAlign:'right' }}>FELT</th>
        </tr></thead>
        <tbody>
          {rows.map(r => {
            const magCol = r.magnitude >= 7 ? 'var(--rose)' :
                           r.magnitude >= 6 ? 'var(--amber)' :
                           r.magnitude >= 5 ? 'var(--amber)' :
                           r.magnitude >= 4 ? 'var(--cyan)' : 'var(--muted)';
            return (
              <tr key={r.event_id} className={r.event_id === sel ? 'selected' : ''} onClick={() => setSel(r.event_id)}>
                <td className="num" style={{ color: magCol, fontWeight: 600 }}>{r.magnitude_str}</td>
                <td>{r.place}</td>
                <td className="num mut">{r.depth_km.toFixed(0)}km</td>
                <td><span className="mut">{r.time_ago}</span></td>
                <td>{r.tsunami ? <span className="pill pill-rose">YES</span> : <span className="dim">—</span>}</td>
                <td>{r.alert ? <span className={`pill pill-${r.alert === 'orange' || r.alert === 'red' ? 'rose' : r.alert === 'yellow' ? 'amber' : 'mint'}`}>{r.alert.toUpperCase()}</span> : <span className="dim">—</span>}</td>
                <td className="num mut">{r.felt ? fmtInt(r.felt) : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }

  // ============= NEWS =============
  function NewsPanel({ snap }) {
    const n = snap.news;
    const categories = ['Top','Markets','Business','Tech','Space','Aviation','Shipping'];
    const [active, setActive] = useState('ALL');
    return (
      <div style={{ height: '100%', padding: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: 'var(--cyan)' }}>NEWS WIRE</span>
          <span className="mut">SOURCES OK <span className="up">{n.sources_ok}</span></span>
          <span className="mut">FAILED <span className="down">{n.sources_failed}</span></span>
          <span className="mut">ARTICLES <span className="lbl">{n.articles.length}</span></span>
          <span style={{ flex: 1 }} />
          <div style={{ display: 'flex', gap: 4 }}>
            <button className={`btn ${active === 'ALL' ? 'on' : ''}`} onClick={() => setActive('ALL')}>ALL</button>
            {categories.map(c => (
              <button key={c} className={`btn ${active === c ? 'on' : ''}`} onClick={() => setActive(c)}>{c.toUpperCase()}</button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflow: 'auto', display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6 }}>
          {categories
            .filter(c => active === 'ALL' || active === c)
            .map(cat => {
              const arts = n.by_category[cat] || [];
              if (arts.length === 0) return null;
              return (
                <div key={cat} className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
                  <PanelHead title={`── ${cat.toUpperCase()} ──`} meta={`${arts.length} items`} />
                  <div style={{ padding: '4px 0' }}>
                    {arts.map(a => (
                      <div key={a.id} style={{ padding: '6px 10px', borderBottom: '1px solid rgba(28,45,77,.4)', cursor: 'pointer' }}
                        onClick={() => window.open(a.link, '_blank')}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                          <span className="pill pill-cyan" style={{ minWidth: 36, textAlign: 'center' }}>{a.time_ago}</span>
                          <span style={{ color: 'var(--violet)', fontSize: 10, minWidth: 100 }}>{a.source}</span>
                          <span style={{ fontWeight: 600 }}>{a.title}</span>
                        </div>
                        <div className="mut" style={{ marginLeft: 152, marginTop: 2, fontSize: 10.5 }}>{a.summary.slice(0, 130)}…</div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    );
  }

  // ============= PARKING =============
  function ParkingPanel({ snap, sel, setSel }) {
    const CITIES = [
      { name: 'London',        center: [51.51, -0.12],   zoom: 12 },
      { name: 'San Francisco', center: [37.77, -122.42], zoom: 13 },
      { name: 'Chicago',       center: [41.88, -87.64],  zoom: 12 },
      { name: 'Leeds',         center: [53.80, -1.55],   zoom: 14 },
      { name: 'Birmingham',    center: [52.48, -1.90],   zoom: 13 },
      { name: 'Cologne',       center: [50.94,  6.96],   zoom: 13 },
      { name: 'Newcastle',     center: [54.97, -1.62],   zoom: 14 },
    ];
    const lots = snap.parking.lots || snap.parking.zones || [];
    const availCities = useMemo(() => {
      const s = new Set(lots.map(z => z.city));
      return CITIES.filter(c => s.has(c.name));
    }, [lots]);
    const [city, setCity] = useState(availCities[0]?.name || 'London');
    const cityObj = CITIES.find(c => c.name === city) || CITIES[0];
    const cityLots = lots.filter(z => z.city === city);
    const total = lots.reduce((s, z) => s + (z.total || 0), 0);

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 520px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="MUNICIPAL PARKING · LIVE OCCUPANCY"
            meta={`${lots.length} LOTS · ${fmtInt(total)} SPACES · ${availCities.length} CITIES`}
            right={
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {availCities.map(c => (
                  <button key={c.name} className={`btn ${city === c.name ? 'on' : ''}`}
                    onClick={() => setCity(c.name)}>{c.name.split(' ')[0].toUpperCase()}</button>
                ))}
              </div>
            } />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <DeltaMap kind="parking" items={cityLots} selectedId={sel} onSelect={setSel}
              center={cityObj.center} zoom={cityObj.zoom} key={city} />
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title={`${city.toUpperCase()} · CAR PARKS`} meta={`${cityLots.length} LOTS`} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <th>NAME</th><th>TYPE</th>
                <th style={{ textAlign: 'right' }}>TOTAL</th>
                <th style={{ textAlign: 'right' }}>FREE</th>
                <th style={{ textAlign: 'right' }}>OCC%</th>
                <th>STATUS</th>
              </tr></thead>
              <tbody>
                {cityLots.map(z => {
                  const sCol = z.status === 'Available' ? 'pill-mint'
                             : z.status === 'Moderate'  ? 'pill-cyan'
                             : z.status === 'Busy'      ? 'pill-amber' : 'pill-rose';
                  return (
                    <tr key={z.id} className={z.id === sel ? 'selected' : ''} onClick={() => setSel(z.id)}>
                      <td><span className="up">{z.name}</span></td>
                      <td><span className="mut">{z.type || '—'}</span></td>
                      <td className="num">{fmtInt(z.total)}</td>
                      <td className="num">
                        <span className={z.occ_pct != null && z.occ_pct < 50 ? 'up' : z.occ_pct > 90 ? 'down' : ''}>
                          {z.free != null ? fmtInt(z.free) : '—'}
                        </span>
                      </td>
                      <td className="num">{z.occ_pct != null ? z.occ_pct + '%' : '—'}</td>
                      <td><span className={`pill ${sCol}`}>{z.status}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ============= COMMAND / HELP =============
  function CommandPanel({ snap, onJump }) {
    const [tab, setTab] = useState('dir');
    const [ping, setPing] = useState(null);
    const { CATEGORIES, TAB_NAMES } = window.DeltaCats;

    useEffect(() => {
      const t0 = performance.now();
      fetch('http://localhost:8000/api/markets')
        .then(() => setPing(Math.round(performance.now() - t0)))
        .catch(() => setPing(null));
    }, []);

    const FEEDS = [
      { name: 'Yahoo Finance',      api: 'yfinance · equity, macro, FX',      tabs: 'MKT CRT ERN EQT BND FRX COM',  ok: () => (snap.indices||[]).length > 0 },
      { name: 'CoinMarketCap',      api: 'CMC free tier · 100 coins',          tabs: 'CRY',                           ok: () => (snap.cmcCoins||[]).length > 0 },
      { name: 'FRED',               api: 'St. Louis Fed · macro series',       tabs: 'FRD MCR MFG LBR',               ok: () => Object.keys(snap.fred?.series||{}).length > 0 },
      { name: 'Options Chain',      api: 'CBOE via Yahoo Finance',             tabs: 'OFL DRK',                       ok: () => (snap.optionsFlow?.unusual||[]).length > 0 },
      { name: 'FINRA RegSho',       api: 'FINRA ATS daily short volume',       tabs: 'DRK',                           ok: () => (snap.darkpool?.ats_vol||[]).length > 0 },
      { name: 'OpenSky Network',    api: 'ADS-B transponder · live',           tabs: 'ACR',                           ok: () => (snap.aircraft||[]).length > 0 },
      { name: 'AIS / Kystverket',   api: 'Marine AIS · 60s polling',           tabs: 'VES SHP PRT',                   ok: () => (snap.ships||[]).length > 0 },
      { name: 'Open-Meteo',         api: 'NWP weather · free tier',            tabs: 'WEA CLM',                       ok: () => (snap.weather||[]).length > 0 },
      { name: 'USGS',               api: 'Earthquake catalog · 15-min',        tabs: 'EAR',                           ok: () => (snap.quakes?.recent||[]).length > 0 },
      { name: 'NASA FIRMS',         api: 'Active fire / thermal anomalies',    tabs: 'FIR',                           ok: () => true },
      { name: 'RSS Aggregator',     api: '30+ news sources · 2-min poll',      tabs: 'NEWS',                          ok: () => (snap.news?.articles||[]).length > 0 },
      { name: 'GDELT 2.0',          api: 'Global events · 15-min CSV',         tabs: 'POL TER DIP INT',               ok: () => (snap.gdelt?.pol||[]).length > 0 },
      { name: 'OFAC SDN',           api: 'US Treasury sanctions list',         tabs: 'SAN',                           ok: () => (snap.sanctions?.count||0) > 0 },
      { name: 'CISA KEV',           api: 'Known Exploited Vulns + advisories', tabs: 'CVE THR DAR HAC',               ok: () => (snap.cve?.kev||[]).length > 0 },
      { name: 'HaveIBeenPwned',     api: 'Data breach directory',              tabs: 'LEK DAR',                       ok: () => (snap.leaks?.breaches||[]).length > 0 },
      { name: 'Cloudflare Radar',   api: 'BGP routing intelligence',           tabs: 'NET CLD',                       ok: () => (snap.cloudflare?.bgp_stats?.total_prefixes||0) > 0 },
      { name: 'Hacker News',        api: 'Firebase API · 10-min poll',         tabs: 'SOC',                           ok: () => (snap.hackernews?.stories||[]).length > 0 },
      { name: 'Launch Library 2',   api: 'The Space Devs · free tier',         tabs: 'RKT',                           ok: () => (snap.launches?.upcoming||[]).length > 0 },
      { name: 'NASA CNEOS',         api: 'Near-Earth close approaches',        tabs: 'NEO',                           ok: () => (snap.neo?.objects||[]).length > 0 },
      { name: 'NOAA SWPC',          api: 'Space weather · Kp / G-scale',       tabs: 'SOL',                           ok: () => snap.spaceWeather?.kp_index != null },
      { name: 'CelesTrak',          api: 'TLE orbital elements · daily',       tabs: 'SAT ISS',                       ok: () => (snap.space?.sats||[]).length > 0 },
      { name: 'EIA',                api: 'Energy Information Administration',  tabs: 'OIL GAS NUC REN ELG',           ok: () => Object.keys(snap.energy?.oil||{}).length > 0 },
      { name: 'ACLED',              api: 'Armed conflict events database',     tabs: 'WAR',                           ok: () => (snap.conflicts?.events||[]).length > 0 },
      { name: 'WHO GHO',            api: 'Global Health Observatory · daily',  tabs: 'HLT',                           ok: () => Object.keys(snap.who?.by_country||{}).length > 0 },
      { name: 'ClinicalTrials.gov', api: 'NIH trial registry · hourly',        tabs: 'HLT',                           ok: () => (snap.clinicalTrials?.studies||[]).length > 0 },
      { name: 'World Bank',         api: 'Development data API',               tabs: 'POP URB TRD EDU',               ok: () => (snap.population?.countries||[]).length > 0 },
      { name: 'UNHCR',              api: 'Refugee data portal',                tabs: 'MIG REF',                       ok: () => (snap.unhcr?.by_origin||[]).length > 0 },
      { name: 'ArXiv',              api: 'Open-access preprints · 4h poll',    tabs: 'AI SEM ROB QNT BIO',            ok: () => (snap.arxiv?.ai||[]).length > 0 },
      { name: 'SEC EDGAR',          api: 'Insider trades · Form 4',            tabs: 'INS',                           ok: () => (snap.edgar?.insider_trades||[]).length > 0 },
      { name: 'NASA NSIDC',         api: 'Sea ice extent · daily',             tabs: 'OCN',                           ok: () => snap.ocean?.arctic?.extent != null },
      { name: 'Parking APIs',       api: 'NYC / SF / CHI open data',           tabs: 'PKG',                           ok: () => (snap.parking?.lots||[]).length > 0 },
      { name: 'Claude API',         api: 'Anthropic · AI recommendations',     tabs: 'REC',                           ok: () => (snap.recommendations?.stocks||[]).length > 0 },
      { name: 'MIT Elections',      api: 'Election lab · historical data',     tabs: 'ELE',                           ok: () => (snap.elections?.elections||[]).length > 0 },
    ];

    const activeFeeds = FEEDS.filter(f => f.ok()).length;
    const totalTabs   = CATEGORIES.reduce((n, c) => n + c.tabs.length, 0);
    const lastRefresh = snap.ts ? Math.round((Date.now() - snap.ts) / 1000) : null;

    const tabBtn = (key, label) => (
      <button key={key} onClick={() => setTab(key)}
        style={{ padding: '2px 10px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
          border: '1px solid', letterSpacing: '.06em', fontWeight: tab === key ? 700 : 400,
          borderColor: tab === key ? 'var(--cyan)' : 'var(--border-2)',
          background: tab === key ? 'rgba(56,189,248,.12)' : 'transparent',
          color: tab === key ? 'var(--cyan)' : 'var(--text-2)' }}>
        {label}
      </button>
    );

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Header */}
        <div className="panel" style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 }}>
          <span style={{ fontSize: 24, color: 'var(--cyan)', lineHeight: 1 }}>◆</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, letterSpacing: '.16em', fontWeight: 700 }}>DELTA TERMINAL</div>
            <div className="mut" style={{ fontSize: 9, marginTop: 1, letterSpacing: '.06em' }}>
              {totalTabs} TABS · {FEEDS.length} FEEDS · {activeFeeds} LIVE
              {lastRefresh != null && <span> · REFRESHED {lastRefresh}s AGO</span>}
              {ping != null && <span> · {ping}ms LATENCY</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {[['dir','DIRECTORY'],['feeds','FEEDS'],['keys','KEYBOARD']].map(([k,l]) => tabBtn(k,l))}
          </div>
        </div>

        {/* DIRECTORY — all tabs by category */}
        {tab === 'dir' && (
          <div className="panel" style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
            {CATEGORIES.filter(c => c.code !== 'sys').map(cat => (
              <div key={cat.code} style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 9, color: 'var(--cyan)', letterSpacing: '.12em', fontWeight: 700, marginBottom: 6 }}>
                  {cat.label}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 6px' }}>
                  {cat.tabs.map(t => (
                    <div key={t} onClick={() => onJump && onJump(t)}
                      style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
                        padding: '3px 8px', background: 'var(--surface-2)',
                        border: '1px solid var(--border)', borderRadius: 2, fontSize: 10 }}>
                      <span style={{ fontWeight: 700, color: 'var(--cyan)', fontFamily: 'var(--mono)', fontSize: 9, minWidth: 24 }}>{t}</span>
                      <span className="mut">{TAB_NAMES[t] || t}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div className="mut" style={{ fontSize: 9, marginTop: 8 }}>
              Click any tab to navigate · or type the code in the command bar and press GO
            </div>
          </div>
        )}

        {/* FEEDS — live status */}
        {tab === 'feeds' && (
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 12, fontSize: 10 }}>
              <span style={{ color: 'var(--mint)', fontWeight: 600 }}>{activeFeeds} LIVE</span>
              <span className="mut">·</span>
              <span style={{ color: 'var(--rose)', fontWeight: 600 }}>{FEEDS.length - activeFeeds} LOADING</span>
              <span className="mut">· {FEEDS.length} TOTAL FEEDS</span>
            </div>
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              <table className="dense">
                <thead><tr>
                  <th>FEED</th><th>SOURCE / INTERVAL</th><th>TABS</th><th>STATUS</th>
                </tr></thead>
                <tbody>
                  {FEEDS.map(f => {
                    const live = f.ok();
                    return (
                      <tr key={f.name}>
                        <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>{f.name}</td>
                        <td className="mut" style={{ fontSize: 10 }}>{f.api}</td>
                        <td className="mut" style={{ fontSize: 9, fontFamily: 'var(--mono)', whiteSpace: 'nowrap' }}>{f.tabs}</td>
                        <td><span className={'pill ' + (live ? 'pill-mint' : 'pill-amber')}>{live ? 'LIVE' : 'LOADING'}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* KEYBOARD — shortcuts + session */}
        {tab === 'keys' && (
          <div className="panel" style={{ flex: 1, padding: '16px 20px', overflow: 'auto' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
              <div>
                <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 10, fontWeight: 700, marginBottom: 12 }}>KEYBOARD SHORTCUTS</div>
                <table className="dense" style={{ fontSize: 11 }}>
                  <tbody>
                    <tr><td style={{ width: 80 }}><span className="kbd">1</span>–<span className="kbd">9</span></td><td className="mut">jump to tab by position</td></tr>
                    <tr><td><span className="kbd">Tab</span></td><td className="mut">next tab in category</td></tr>
                    <tr><td><span className="kbd">/</span></td><td className="mut">focus command bar</td></tr>
                    <tr><td><span className="kbd">R</span></td><td className="mut">force data refresh</td></tr>
                    <tr><td><span className="kbd">Esc</span></td><td className="mut">clear selection / filter</td></tr>
                    <tr><td><span className="kbd">?</span></td><td className="mut">jump to CMD (this screen)</td></tr>
                    <tr><td><span className="kbd">Enter</span></td><td className="mut">execute command bar input</td></tr>
                  </tbody>
                </table>

                <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 10, fontWeight: 700, marginTop: 20, marginBottom: 12 }}>COMMAND BAR</div>
                <table className="dense" style={{ fontSize: 11 }}>
                  <tbody>
                    <tr><td style={{ width: 80 }}><span className="lbl">MKT</span></td><td className="mut">jump to Markets</td></tr>
                    <tr><td><span className="lbl">[CODE]</span></td><td className="mut">any tab code (e.g. WAR, CVE, AI)</td></tr>
                    <tr><td><span className="lbl">HELP / ?</span></td><td className="mut">this screen</td></tr>
                    <tr><td><span className="lbl">1–9</span></td><td className="mut">jump to tab by number</td></tr>
                  </tbody>
                </table>
              </div>

              <div>
                <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 10, fontWeight: 700, marginBottom: 12 }}>SESSION</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 14, rowGap: 6, fontSize: 11 }}>
                  <span className="mut">BACKEND</span>
                  <span style={{ color: 'var(--mint)', fontWeight: 600 }}>localhost:8000 · CONNECTED</span>
                  <span className="mut">LATENCY</span>
                  <span className={ping != null ? 'up' : 'mut'}>
                    {ping != null ? `${ping}ms` : 'measuring…'}
                  </span>
                  <span className="mut">LAST REFRESH</span>
                  <span>{lastRefresh != null ? `${lastRefresh}s ago` : '—'}</span>
                  <span className="mut">FEEDS LIVE</span>
                  <span style={{ color: 'var(--mint)', fontWeight: 600 }}>{activeFeeds} / {FEEDS.length}</span>
                  <span className="mut">TABS</span>
                  <span>{totalTabs}</span>
                  <span className="mut">SESSION ID</span>
                  <span className="lbl">{snap.ts ? snap.ts.toString(36).toUpperCase() : '—'}</span>
                </div>

                <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 10, fontWeight: 700, marginTop: 20, marginBottom: 10 }}>ABOUT</div>
                <div className="mut" style={{ fontSize: 10, lineHeight: 1.8 }}>
                  DELTA is an open-source market &amp; world data terminal.<br/>
                  All feeds are free public APIs. No account required.<br/>
                  Data is for informational purposes only.<br/>
                  NOT FINANCIAL ADVICE.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // CryptoPanel lives in delta-panels3.jsx (CMC, 100 coins) — removed from here

  function _CryptoPanel_unused({ snap }) {
    const coins = snap.crypto;
    const [filter, setFilter] = useState('');
    const filtered = useMemo(() => {
      if (!filter) return coins;
      const f = filter.toLowerCase();
      return coins.filter(c => c.name.toLowerCase().includes(f) || c.symbol.toLowerCase().includes(f));
    }, [coins, filter]);
    const [sorted, sort, toggle] = useSort(filtered, { key: 'change_pct_24h', dir: 'desc' });
    const gainers = coins.filter(c => c.change_pct_24h > 0).length;
    const losers  = coins.filter(c => c.change_pct_24h < 0).length;

    return (
      <div style={{ height: '100%', padding: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: 'var(--cyan)', letterSpacing: '.12em' }}>CRYPTO · SPOT</span>
          <span className="mut">PAIRS <span className="lbl">{coins.length}</span></span>
          <span className="mut">GAINERS <span className="up">{gainers}</span></span>
          <span className="mut">LOSERS <span className="down">{losers}</span></span>
          <span style={{ flex: 1 }} />
          <Filter value={filter} onChange={setFilter} placeholder="search coin…" />
          <span className="pill pill-mint blink">● LIVE</span>
        </div>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="CRYPTOCURRENCY PRICES · BINANCE SPOT" meta={`${filtered.length} PAIRS`} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <Th k="symbol"        sort={sort} toggle={toggle}>PAIR</Th>
                <Th k="name"          sort={sort} toggle={toggle}>NAME</Th>
                <Th k="price"         sort={sort} toggle={toggle} align="right">PRICE $</Th>
                <Th k="change_pct_24h" sort={sort} toggle={toggle} align="right">24H %</Th>
                <Th k="change_24h"    sort={sort} toggle={toggle} align="right">24H Δ</Th>
                <Th k="high_24h"      sort={sort} toggle={toggle} align="right">24H HI</Th>
                <Th k="low_24h"       sort={sort} toggle={toggle} align="right">24H LO</Th>
                <Th k="volume_24h"    sort={sort} toggle={toggle} align="right">VOLUME</Th>
              </tr></thead>
              <tbody>
                {sorted.map(c => (
                  <tr key={c.symbol}>
                    <td><span className="lbl">{c.symbol.replace('USDT', '/USDT')}</span></td>
                    <td><span className="mut">{c.name}</span></td>
                    <td className="num">{fmt(c.price, c.price < 1 ? 4 : 2)}</td>
                    <td className="num" style={{ color: c.change_pct_24h >= 0 ? 'var(--mint)' : 'var(--rose)', fontWeight: 600 }}>
                      {c.arrow} {c.change_pct_24h >= 0 ? '+' : ''}{c.change_pct_24h.toFixed(2)}%
                    </td>
                    <td className="num" style={{ color: c.change_24h >= 0 ? 'var(--mint)' : 'var(--rose)' }}>
                      {c.change_24h >= 0 ? '+' : ''}{fmt(c.change_24h, 2)}
                    </td>
                    <td className="num mut">{fmt(c.high_24h, c.high_24h < 1 ? 4 : 2)}</td>
                    <td className="num mut">{fmt(c.low_24h,  c.low_24h  < 1 ? 4 : 2)}</td>
                    <td className="num mut">${fmtAbbr(c.volume_24h)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ============= WILDFIRES (FIR) =============
  function WildfiresPanel() {
    const [data, setData] = useState({ hotspots: [], count: 0, error: null });
    const [loading, setLoading] = useState(true);
    const [selId, setSelId] = useState(null);
    const [minFrp, setMinFrp] = useState(0);

    useEffect(() => {
      if (!window.DeltaLive || !window.DeltaLive.fetchWildfires) { setLoading(false); return; }
      const load = () => {
        try {
          window.DeltaLive.fetchWildfires()
            .then(d => { setData(d); setLoading(false); })
            .catch(() => setLoading(false));
        } catch(e) { setLoading(false); }
      };
      load();
      const id = setInterval(load, 3600_000);
      return () => clearInterval(id);
    }, []);

    const hotspots = useMemo(() =>
      data.hotspots.filter(h => (h.frp || 0) >= minFrp),
      [data.hotspots, minFrp]);

    const mapItems = useMemo(() =>
      hotspots.map((h, i) => ({ ...h, id: i, lat: h.lat, lon: h.lon })),
      [hotspots]);

    const selHot = selId != null ? mapItems[selId] : null;
    const avgFrp = hotspots.length ? (hotspots.reduce((s, h) => s + (h.frp || 0), 0) / hotspots.length).toFixed(1) : '—';
    const maxFrp = hotspots.length ? Math.max(...hotspots.map(h => h.frp || 0)).toFixed(0) : '—';

    if (loading) return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
        LOADING FIRMS DATA…
      </div>
    );

    if (data.error && hotspots.length === 0) return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: 12, color: 'var(--muted)', padding: 32 }}>
        <div style={{ fontSize: 28, color: 'var(--amber)' }}>⚠</div>
        <div style={{ color: 'var(--amber)' }}>FIRMS FEED ERROR</div>
        <div style={{ fontSize: 11, maxWidth: 400, textAlign: 'center' }}>{data.error}</div>
      </div>
    );

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, position: 'relative' }}>
          <PanelHead title="WILDFIRE HOTSPOTS · NASA FIRMS VIIRS/MODIS"
            meta={`${hotspots.length.toLocaleString()} HOTSPOTS · AVG FRP ${avgFrp} MW · MAX ${maxFrp} MW · NRT`}
            right={<span className="pill pill-rose blink">● NASA FIRMS</span>} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <WildfireMap items={mapItems} selId={selId} onSelect={setSelId} />
            <div style={{ position: 'absolute', left: 10, bottom: 10, zIndex: 500,
              background: 'var(--surface)', border: '1px solid var(--border-2)', padding: '6px 10px', fontSize: 10 }}>
              <div style={{ color: 'var(--cyan)', marginBottom: 4 }}>FRP (MW) INTENSITY</div>
              <div style={{ display: 'flex', gap: 12 }}>
                <span><span style={{ color: 'var(--rose)' }}>●</span> &gt;1000</span>
                <span><span style={{ color: 'var(--amber)' }}>●</span> &gt;100</span>
                <span><span style={{ color: '#f5c518' }}>●</span> &gt;10</span>
                <span><span style={{ color: 'var(--text-2)' }}>●</span> low</span>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minHeight: 0 }}>
          {selHot && (
            <div className="panel" style={{ padding: '10px 14px', fontSize: 11 }}>
              <div style={{ color: 'var(--rose)', fontSize: 13, marginBottom: 6 }}>🔥 HOTSPOT DETAIL</div>
              <div>POS <span className="lbl">{selHot.lat.toFixed(3)}°  {selHot.lon.toFixed(3)}°</span></div>
              <div>FRP <span className="up">{selHot.frp} MW</span>  BRIGHTNESS <span className="lbl">{selHot.brightness} K</span></div>
              <div>CONFIDENCE <span className="lbl">{selHot.confidence}</span>  SAT <span className="mut">{selHot.satellite}</span></div>
              <div className="mut" style={{ marginTop: 4 }}>DATE {selHot.date}</div>
            </div>
          )}
          <div className="panel" style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="mut" style={{ fontSize: 10 }}>MIN FRP</span>
            {[0, 10, 100, 500].map(v => (
              <button key={v} className={'btn' + (minFrp === v ? ' on' : '')} onClick={() => setMinFrp(v)}>
                {v === 0 ? 'ALL' : v + '+'}
              </button>
            ))}
          </div>
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PanelHead title="TOP HOTSPOTS BY FRP" meta={`${hotspots.length} TOTAL`} />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <table className="dense">
                <thead><tr>
                  <th style={{ textAlign:'right' }}>FRP MW</th>
                  <th style={{ textAlign:'right' }}>BRIGHT K</th>
                  <th>CONF</th>
                  <th>SAT</th>
                  <th>DATE</th>
                </tr></thead>
                <tbody>
                  {hotspots.slice().sort((a,b) => (b.frp||0)-(a.frp||0)).slice(0, 200).map((h, i) => (
                    <tr key={i} className={selId === i ? 'selected' : ''} onClick={() => setSelId(selId === i ? null : i)}
                      style={{ cursor: 'pointer' }}>
                      <td className="num" style={{ color: h.frp > 1000 ? 'var(--rose)' : h.frp > 100 ? 'var(--amber)' : undefined, fontWeight: h.frp > 100 ? 600 : undefined }}>
                        {h.frp.toFixed(0)}
                      </td>
                      <td className="num mut">{h.brightness.toFixed(0)}</td>
                      <td><span className={'pill ' + (h.confidence === 'h' ? 'pill-mint' : h.confidence === 'n' ? 'pill-cyan' : 'pill-amber')}>{h.confidence}</span></td>
                      <td className="mut">{h.satellite}</td>
                      <td className="mut">{h.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    );
  }

  function WildfireMap({ items, selId, onSelect }) {
    const containerRef = React.useRef(null);
    const mapRef = React.useRef(null);
    const layerRef = React.useRef(null);
    const markersRef = React.useRef([]);

    useEffect(() => {
      if (mapRef.current) return;
      const map = L.map(containerRef.current, {
        center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 10,
        preferCanvas: true, renderer: L.canvas({ padding: 0.5 }),
        zoomControl: true, attributionControl: true,
      });
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png', {
        maxZoom: 19, attribution: '&copy; OpenStreetMap &copy; CARTO', subdomains: 'abcd',
      }).addTo(map);
      const isLight = document.documentElement.getAttribute('data-theme') === 'paper';
      L.tileLayer(isLight
        ? 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png'
        : 'https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png',
        { maxZoom: 19, subdomains: 'abcd', opacity: 0.5 }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      const ro = new ResizeObserver(() => map.invalidateSize());
      ro.observe(containerRef.current);
      return () => { ro.disconnect(); map.remove(); mapRef.current = null; };
    }, []);

    useEffect(() => {
      const layer = layerRef.current;
      if (!layer) return;
      layer.clearLayers();
      markersRef.current = [];
      items.forEach((h, i) => {
        const frp = h.frp || 0;
        const r = Math.max(3, Math.min(14, 3 + Math.log10(frp + 1) * 3.5));
        const col = frp > 1000 ? '#ef4444' : frp > 100 ? '#f97316' : frp > 10 ? '#f5c518' : '#9ca3af';
        const m = L.circleMarker([h.lat, h.lon], {
          radius: r, color: col, fillColor: col, fillOpacity: 0.7,
          weight: selId === i ? 2 : 0.5, opacity: 0.9,
        });
        m.bindTooltip(`FRP ${frp.toFixed(0)} MW · ${h.confidence} · ${h.satellite}`, { className: 'delta-tip' });
        m.on('click', () => onSelect(selId === i ? null : i));
        m.addTo(layer);
        markersRef.current.push(m);
      });
    }, [items, selId]);

    return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
  }

  // ============= SATELLITES (SAT) =============
  function SatellitesPanel({ snap }) {
    const { sats, starlink_count, active_count } = snap.space;
    const orbitColor = { LEO: 'pill-cyan', MEO: 'pill-mint', GEO: 'pill-violet', HEO: 'pill-amber' };
    const [sorted, sort, toggle] = useSort(sats, { key: 'perigee_km', dir: 'asc' });
    const [orb, setOrb] = useState('ALL');
    const ORBITS = ['ALL', 'LEO', 'MEO', 'GEO', 'HEO'];
    const rows = orb === 'ALL' ? sorted : sorted.filter(s => s.orbit_type === orb);

    return (
      <div style={{ height: '100%', padding: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: 'var(--cyan)', letterSpacing: '.12em' }}>ORBITAL CATALOG · CelesTrak</span>
          <span className="mut">ACTIVE SATS <span className="lbl">{fmtInt(active_count)}</span></span>
          <span className="mut">STARLINK <span className="lbl">{fmtInt(starlink_count)}</span></span>
          <span className="mut">CATALOG SAMPLE <span className="lbl">{sats.length}</span></span>
          <span style={{ flex: 1 }} />
          {ORBITS.map(o => (
            <button key={o} className={`btn ${orb === o ? 'on' : ''}`} onClick={() => setOrb(o)}>{o}</button>
          ))}
          <span className="pill pill-violet blink">● LIVE</span>
        </div>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="TRACKED OBJECTS · VISUAL MAGNITUDE CATALOG"
            meta={`${rows.length} OBJECTS · SORTED BY ORBIT`} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <Th k="name"       sort={sort} toggle={toggle}>OBJECT</Th>
                <Th k="norad_id"   sort={sort} toggle={toggle}>NORAD</Th>
                <Th k="orbit_type" sort={sort} toggle={toggle}>ORBIT</Th>
                <Th k="inclination" sort={sort} toggle={toggle} align="right">INC°</Th>
                <Th k="apogee_km"  sort={sort} toggle={toggle} align="right">APOGEE km</Th>
                <Th k="perigee_km" sort={sort} toggle={toggle} align="right">PERIGEE km</Th>
                <Th k="period_min" sort={sort} toggle={toggle} align="right">PERIOD min</Th>
                <Th k="eccentricity" sort={sort} toggle={toggle} align="right">ECC</Th>
              </tr></thead>
              <tbody>
                {rows.map(s => (
                  <tr key={s.norad_id}>
                    <td><span className="up">{s.name}</span></td>
                    <td><span className="lbl">{s.norad_id}</span></td>
                    <td><span className={`pill ${orbitColor[s.orbit_type] || ''}`}>{s.orbit_type}</span></td>
                    <td className="num">{s.inclination != null ? s.inclination.toFixed(1) : '—'}</td>
                    <td className="num">{fmtInt(s.apogee_km)}</td>
                    <td className="num">{fmtInt(s.perigee_km)}</td>
                    <td className="num">{s.period_min != null ? s.period_min.toFixed(2) : '—'}</td>
                    <td className="num mut">{s.eccentricity != null ? s.eccentricity.toFixed(5) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  const CAM_REFRESH_MS = 30_000; // refresh camera images every 30s

  function camSrc(cam, tick) {
    const base = cam.proxy
      ? `http://localhost:8000/api/camera-proxy?url=${encodeURIComponent(cam.url)}`
      : cam.url;
    // Append tick as cache-buster — forces browser to re-fetch the image
    const sep = base.includes('?') ? '&' : '?';
    return `${base}${sep}_t=${tick}`;
  }

  function useCamTick() {
    const [tick, setTick] = useState(() => Math.floor(Date.now() / CAM_REFRESH_MS));
    useEffect(() => {
      const id = setInterval(() => setTick(Math.floor(Date.now() / CAM_REFRESH_MS)), CAM_REFRESH_MS);
      return () => clearInterval(id);
    }, []);
    return tick;
  }

  function CamCard({ cam, onClick, tick }) {
    const [err, setErr] = useState(false);
    const [loaded, setLoaded] = useState(false);

    // Reset on tick change so image re-fetches cleanly
    useEffect(() => {
      setErr(false);
      setLoaded(false);
    }, [tick]);

    const src = camSrc(cam, tick);
    return (
      <div style={{ cursor: 'pointer', border: '1px solid var(--border-2)', background: 'var(--bg-2)', overflow: 'hidden' }}
        onClick={onClick}>
        <div style={{ position: 'relative', height: 130, background: 'var(--surface-2)', overflow: 'hidden',
          display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {err ? (
            <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: 10 }}>
              <div style={{ fontSize: 20, marginBottom: 4 }}>○</div>
              <div>OFFLINE</div>
              <div style={{ marginTop: 2, fontSize: 9 }}>{cam.city}</div>
            </div>
          ) : (
            <>
              {!loaded && (
                <div style={{ position: 'absolute', color: 'var(--muted)', fontSize: 9, letterSpacing: '.06em' }}>LOADING…</div>
              )}
              <img src={src} alt={cam.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: loaded ? 1 : 0, transition: 'opacity .3s' }}
                onLoad={() => setLoaded(true)}
                onError={() => setErr(true)} />
            </>
          )}
          <div style={{ position: 'absolute', top: 4, right: 4 }}>
            <span className={'pill ' + (err ? 'pill-rose' : cam.reachable ? 'pill-mint' : 'pill-amber')}
              style={{ fontSize: 9 }}>
              {err ? '○ ERR' : cam.reachable ? '● LIVE' : '○ OFF'}
            </span>
          </div>
        </div>
        <div style={{ padding: '5px 7px' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis' }}>{cam.name}</div>
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>{cam.city}</div>
        </div>
      </div>
    );
  }

  // ============= CAMERAS / TRAFFIC (TRF) =============
  function CamerasPanel() {
    const [cams, setCams] = useState([]);
    const [loading, setLoading] = useState(true);
    const [cat, setCat] = useState('ALL');
    const [sel, setSel] = useState(null);
    const tick = useCamTick();

    useEffect(() => {
      if (!window.DeltaLive || !window.DeltaLive.fetchCameras) {
        setLoading(false);
        return;
      }
      const load = () => {
        try {
          window.DeltaLive.fetchCameras()
            .then(c => { setCams(c); setLoading(false); })
            .catch(() => setLoading(false));
        } catch(e) { setLoading(false); }
      };
      load();
      const id = setInterval(load, 120_000);
      return () => clearInterval(id);
    }, []);

    const cats = useMemo(() => ['ALL', ...new Set(cams.map(c => c.category))], [cams]);
    const filtered = cat === 'ALL' ? cams : cams.filter(c => c.category === cat);
    const live = filtered.filter(c => c.reachable !== false);
    const selCam = cams.find(c => c.id === sel);

    if (loading) return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
        LOADING CAMERAS…
      </div>
    );

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 540px', gap: 6, height: '100%', padding: 6 }}>
        {/* Camera grid */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="LIVE CAMERA FEEDS · PUBLIC SOURCES"
            meta={`${live.length} LIVE · ${cams.length} TOTAL · NOAA NDBC OCEAN BUOYS · 24/7 · AUTO-REFRESH 30s`}
            right={
              <div style={{ display: 'flex', gap: 4 }}>
                {cats.map(c => (
                  <button key={c} className={`btn ${cat === c ? 'on' : ''}`}
                    onClick={() => setCat(c)}>{c.toUpperCase()}</button>
                ))}
              </div>
            } />
          {selCam ? (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 0, minHeight: 0 }}>
              <div style={{ padding: '6px 10px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 10 }}>
                <button className="btn" onClick={() => setSel(null)}>← BACK</button>
                <span style={{ color: 'var(--cyan)' }}>{selCam.name}</span>
                <span className="mut">{selCam.city}</span>
                <span className={`pill ${selCam.reachable ? 'pill-mint' : 'pill-rose'}`}>
                  {selCam.reachable ? '● LIVE' : '○ OFFLINE'}
                </span>
              </div>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: '#000', position: 'relative' }}>
                <img src={camSrc(selCam, tick)} alt={selCam.name}
                  style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  onError={e => { e.target.style.opacity = 0.3; }}
                  key={selCam.id + tick} />
                <div style={{ position: 'absolute', bottom: 8, right: 8, fontSize: 10, color: 'var(--muted)',
                  background: 'rgba(0,0,0,.7)', padding: '2px 6px' }}>
                  AUTO-REFRESH 30s · CLICK BACK TO BROWSE
                </div>
              </div>
            </div>
          ) : (
            <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {filtered.map(c => <CamCard key={c.id} cam={c} onClick={() => setSel(c.id)} tick={tick} />)}
              </div>
            </div>
          )}
        </div>

        {/* Camera list / detail */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="CAMERA INDEX" meta={`${filtered.length} FEEDS`} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <th>NAME</th><th>CITY</th><th>TYPE</th><th>STATUS</th>
              </tr></thead>
              <tbody>
                {filtered.map(c => (
                  <tr key={c.id} className={c.id === sel ? 'selected' : ''}
                    style={{ cursor: 'pointer' }} onClick={() => setSel(c.id === sel ? null : c.id)}>
                    <td><span className="up">{c.name.slice(0, 32)}</span></td>
                    <td><span className="mut">{c.city}</span></td>
                    <td><span className="lbl">{c.category}</span></td>
                    <td>
                      <span className={`pill ${c.reachable ? 'pill-mint' : 'pill-rose'}`}>
                        {c.reachable ? 'LIVE' : 'OFFLINE'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  window.DeltaPanels = { MarketsPanel, WorldPanel, AircraftPanel, ShipsPanel, SpacePanel, WeatherPanel, QuakesPanel, NewsPanel, ParkingPanel, CommandPanel, SatellitesPanel, CamerasPanel, WildfiresPanel };
})();
