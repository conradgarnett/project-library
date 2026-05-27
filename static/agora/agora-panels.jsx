// agora-panels.jsx — tab panel components
// Exposes window.AgoraPanels

(function () {
  const { useState, useMemo, useEffect, useRef } = React;
  const { fmt, fmtInt, fmtAbbr } = window.AgoraData;
  const AgoraMap = window.AgoraMap;

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
  function QuotesTable({ rows, columns }) {
    const [sorted, sort, toggle] = useSort(rows, { key: 'change_pct', dir: 'desc' });
    return (
      <table className="dense">
        <thead><tr>
          {columns.map(c => <Th key={c.key} k={c.key} sort={sort} toggle={toggle} align={c.align}>{c.label}</Th>)}
        </tr></thead>
        <tbody>
          {sorted.map(r => (
            <tr key={r.ticker || r.symbol} className={r._dir === 'up' ? 'flash-up' : r._dir === 'down' ? 'flash-down' : ''}>
              {columns.map(c => (
                <td key={c.key} className={c.num ? 'num' : ''} style={{ color: c.color ? r.color === 'up' ? 'var(--mint)' : 'var(--rose)' : undefined }}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  function MarketsPanel({ snap }) {
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

    // Compact sparkline (visual flair, deterministic per ticker)
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

    return (
      <div style={{ display: 'grid', gridTemplateRows: 'auto 1fr 1fr', gap: 6, height: '100%', padding: 6 }}>
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
              <QuotesTable rows={snap.indices} columns={colsEq} />
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
            <PanelHead title="TECH EQUITIES" meta="US LARGE CAP" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuotesTable rows={snap.tech} columns={colsEq} />
            </div>
          </div>
          <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PanelHead title="MACRO · FX · COMMODITIES" meta="CME · ICE · FOREX" />
            <div style={{ overflow: 'auto', flex: 1 }}>
              <QuotesTable rows={snap.macro} columns={colsEq} />
            </div>
          </div>
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
            <AgoraMap layers={layers}
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
            <AgoraMap kind="aircraft" items={planes} selectedId={sel} onSelect={setSel} center={[30, 0]} zoom={2.5} />
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
            <AgoraMap kind="ships" items={ships} selectedId={sel} onSelect={setSel} center={[25, 50]} zoom={2.5} />
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
            <AgoraMap kind="space" items={stations} center={[20, 0]} zoom={2} />
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
            <AgoraMap kind="weather" items={wx} selectedId={sel} onSelect={setSel} center={[25, 0]} zoom={2} />
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
            meta={`LAST HR ${q.hourly_count} · TODAY ${q.daily_count} · LARGEST ${q.largest_today.magnitude_str} ${q.largest_today.place.slice(0,28)}`}
            right={<span className="pill pill-rose blink">● USGS LIVE</span>} />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <AgoraMap kind="earthquakes" items={all} selectedId={sel} onSelect={setSel} center={[15, 130]} zoom={2.2} />
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
    const cities = [
      { code: 'NYC', label: 'New York City', center: [40.74, -73.98], zoom: 11 },
      { code: 'SF',  label: 'San Francisco', center: [37.77, -122.42], zoom: 12 },
      { code: 'CHI', label: 'Chicago',       center: [41.88, -87.64], zoom: 11 },
    ];
    const [city, setCity] = useState('NYC');
    const cityObj = cities.find(c => c.code === city);
    const zones = snap.parking.zones;
    const cityZones = zones.filter(z => z.city_code === city);
    const total = zones.reduce((s, z) => s + z.total_spaces, 0);

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 520px', gap: 6, height: '100%', padding: 6 }}>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title="MUNICIPAL PARKING · LIVE OCCUPANCY"
            meta={`${zones.length} ZONES · ${fmtInt(total)} SPACES TOTAL · 3 CITIES`}
            right={
              <div style={{ display: 'flex', gap: 4 }}>
                {cities.map(c => (
                  <button key={c.code} className={`btn ${city === c.code ? 'on' : ''}`} onClick={() => setCity(c.code)}>{c.code}</button>
                ))}
              </div>
            } />
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            <AgoraMap kind="parking" items={cityZones} selectedId={sel} onSelect={setSel}
              center={cityObj.center} zoom={cityObj.zoom} key={city} />
          </div>
        </div>
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PanelHead title={`${cityObj.label.toUpperCase()} · ZONES`} meta={`${cityZones.length} ZONES`} />
          <div style={{ overflow: 'auto', flex: 1 }}>
            <table className="dense">
              <thead><tr>
                <th>LOCATION</th><th>TYPE</th>
                <th style={{ textAlign: 'right' }}>TOTAL</th>
                <th style={{ textAlign: 'right' }}>AVAIL</th>
                <th style={{ textAlign: 'right' }}>OCC%</th>
                <th>STATUS</th>
                <th style={{ textAlign: 'right' }}>$/HR</th>
              </tr></thead>
              <tbody>
                {cityZones.map(z => {
                  const sCol = z.status === 'Available' ? 'pill-mint'
                             : z.status === 'Moderate' ? 'pill-cyan'
                             : z.status === 'Busy' ? 'pill-amber' : 'pill-rose';
                  return (
                    <tr key={z.zone_id} className={z.zone_id === sel ? 'selected' : ''} onClick={() => setSel(z.zone_id)}>
                      <td><span className="up">{z.location}</span></td>
                      <td><span className="mut">{z.zone_type}</span></td>
                      <td className="num">{fmtInt(z.total_spaces)}</td>
                      <td className="num"><span className={z.occupancy_pct < 50 ? 'up' : z.occupancy_pct > 90 ? 'down' : ''}>{fmtInt(z.available_spaces)}</span></td>
                      <td className="num">{z.occupancy_pct}%</td>
                      <td><span className={`pill ${sCol}`}>{z.status}</span></td>
                      <td className="num">${z.rate_per_hour.toFixed(2)}</td>
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
    const COMMANDS = [
      ['MKT <GO>', 'Markets · indices, equities, crypto, macro'],
      ['AIR <GO>', 'Aircraft positions · OpenSky Network'],
      ['SEA <GO>', 'Ship positions · AIS public feeds'],
      ['ORB <GO>', 'Orbital tracking · ISS, Tiangong, CelesTrak'],
      ['WX  <GO>', 'World weather observations · Open-Meteo'],
      ['EQ  <GO>', 'Seismic activity · USGS 30-day window'],
      ['NWS <GO>', 'News wire · curated RSS aggregation'],
      ['PRK <GO>', 'Municipal parking occupancy · 3 cities'],
      ['HELP <GO>', 'This screen'],
      ['<NUM> <GO>', 'Jump to tab 1-9'],
    ];
    return (
      <div style={{ padding: 6, height: '100%', overflow: 'auto' }}>
        <div className="panel" style={{ padding: '20px 32px' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 18 }}>
            <span style={{ fontSize: 36, color: 'var(--cyan)' }}>◆</span>
            <div>
              <div style={{ fontSize: 22, letterSpacing: '.16em', fontWeight: 600 }}>AGORA TERMINAL</div>
              <div className="mut" style={{ fontSize: 11, marginTop: 2 }}>OPEN MARKET DATA · v0.4.1 · MIT LICENSE · github.com/agora-terminal</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 32, marginTop: 24 }}>
            <div>
              <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 11, marginBottom: 10 }}>FUNCTION COMMANDS</div>
              <table className="dense" style={{ fontSize: 12 }}>
                <tbody>
                  {COMMANDS.map(([cmd, desc]) => (
                    <tr key={cmd} onClick={() => onJump && onJump(cmd.split(' ')[0])}>
                      <td style={{ width: 140 }}><span className="lbl" style={{ fontWeight: 600 }}>{cmd}</span></td>
                      <td><span className="mut">{desc}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 11, marginTop: 22, marginBottom: 10 }}>KEYBOARD</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 18px', fontSize: 11 }}>
                <div><span className="kbd">1</span>—<span className="kbd">9</span> &nbsp; jump to tab</div>
                <div><span className="kbd">Tab</span> &nbsp; next tab</div>
                <div><span className="kbd">/</span> &nbsp; focus filter</div>
                <div><span className="kbd">R</span> &nbsp; force refresh</div>
                <div><span className="kbd">Esc</span> &nbsp; clear selection</div>
                <div><span className="kbd">?</span> &nbsp; this screen</div>
              </div>
            </div>

            <div>
              <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 11, marginBottom: 10 }}>DATA SOURCES</div>
              <table className="dense" style={{ fontSize: 11 }}>
                <tbody>
                  <tr><td style={{ width: 120 }}><span className="lbl">Markets</span></td><td>Yahoo Finance · 15-min delay</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">Crypto</span></td><td>Binance WebSocket · real-time</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">Aircraft</span></td><td>OpenSky Network · 15s polling</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">Ships</span></td><td>AISHub / Kystverket / DMA</td><td><span className="pill pill-amber">PARTIAL</span></td></tr>
                  <tr><td><span className="lbl">Space</span></td><td>Open-Notify · CelesTrak TLE</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">Weather</span></td><td>Open-Meteo · 5-min polling</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">Quakes</span></td><td>USGS Earthquake Feed</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">News</span></td><td>Multi-source RSS · 2-min poll</td><td><span className="pill pill-mint">OK</span></td></tr>
                  <tr><td><span className="lbl">Parking</span></td><td>NYC/SF/CHI open data portals</td><td><span className="pill pill-mint">OK</span></td></tr>
                </tbody>
              </table>

              <div style={{ color: 'var(--cyan)', letterSpacing: '.12em', fontSize: 11, marginTop: 22, marginBottom: 10 }}>SESSION</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 12, rowGap: 4, fontSize: 11 }}>
                <span className="mut">USER</span><span className="lbl">guest@agora</span>
                <span className="mut">SESSION</span><span className="lbl">{snap.ts.toString(36).toUpperCase()}</span>
                <span className="mut">BACKEND</span><span className="lbl">ws://localhost:8000 · CONNECTED</span>
                <span className="mut">LATENCY</span><span className="up">42ms p50 · 118ms p99</span>
                <span className="mut">VERSION</span><span>0.4.1 (build 2024.11)</span>
              </div>
            </div>
          </div>

          <div className="mut" style={{ marginTop: 30, fontSize: 10, lineHeight: 1.7 }}>
            AGORA TERMINAL is an open-source workstation for live market and world data.
            No API keys required. All data sources are public. Self-hosted. MIT licensed.
            Type a function code on the command line and press <span className="kbd">GO</span> (or Enter).
          </div>
        </div>
      </div>
    );
  }

  window.AgoraPanels = { MarketsPanel, WorldPanel, AircraftPanel, ShipsPanel, SpacePanel, WeatherPanel, QuakesPanel, NewsPanel, ParkingPanel, CommandPanel };
})();
