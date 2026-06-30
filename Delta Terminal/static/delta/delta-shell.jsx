// delta-shell.jsx — top-level app, header, tabs, ticker, function-bar, status bar
(function () {
  const { useEffect, useMemo, useRef, useState, useCallback } = React;
  const { fmt, fmtInt } = window.DeltaData;

  const EMPTY_SNAP = {
    indices: [], tech: [], macro: [], crypto: [],
    aircraft: [], ships: [],
    space: { stations: [], sats: [], starlink_count: 0, active_count: 0, iss: null, tiangong: null, crew: [] },
    weather: [],
    quakes: { recent: [], significant: [], largest_today: null, hourly_count: 0, daily_count: 0 },
    news: { articles: [], by_category: {}, sources_ok: 0, sources_failed: 0 },
    parking: { lots: [], by_city: {}, zones: [] },
    bonds:        { maturities: [], spread_10y2y: 0 },
    forex:        { rates: {} },
    fred:         { series: {} },
    cve:          { recent: [], kev: [], ransomware: [] },
    launches:     { upcoming: [], recent: [] },
    conflicts:    { events: [] },
    sanctions:    { entries: [], count: 0, programs: [] },
    neo:          { objects: [], count: 0 },
    spaceWeather: { kp_index: 0, kp_24h: [], solar_wind: {}, x_ray_flux: 0, alerts: [], storm_level: '' },
    outages:      { alerts: [], countries: [], bgp: [] },
    population:   { countries: [], indicators: {} },
    equityFund:   { fundamentals: {} },
    energy:       { oil: {}, gas: {}, electricity: {}, nuclear: {}, renewables: {} },
    arxiv:        { ai: [], bio: [], quant: [], rob: [], sem: [] },
    who:          { by_country: {}, indicators: [] },
    unhcr:        { totals: {}, by_origin: [], by_host: [] },
    optionsFlow:  { unusual: [], summary: [] },
    recommendations: { stocks: [], macro: {} },
    edgar:    { insider_trades: [], filings_8k: [], filings_10q: [] },
    earnings: { upcoming: [], recent: [] },
    charts:   { intraday: {}, daily: {} },
    darkpool: { prints: [], ats_vol: [] },
    econCalendar: { events: [] },
    climate: { stations: [] },
    polygonData: { bars: {}, fundamentals: {} },
    cmcCoins: [],
    threats:   { advisories: [] },
    ocean:      { arctic: { extent: null, date: '', anomaly: null, trend: [] }, antarctic: { extent: null, date: '', anomaly: null, trend: [] } },
    trade:      { countries: [] },
    elections:  { elections: [] },
    leaks:      { breaches: [], total_pwned: 0, by_class: {} },
    cloudflare: { bgp_leaks: [], bgp_stats: {} },
    gdelt:      { pol: [], ter: [], dip: [] },
    hackernews:     { stories: [] },
    clinicalTrials: { studies: [], by_condition: {}, total: 0 },
    ts: 0, _live: false, _loaded: false,
  };
  const P = window.DeltaPanels;

  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "theme": "paper",
    "density": "regular",
    "animations": true,
    "mapLabels": true
  }/*EDITMODE-END*/;

  const { CATEGORIES, TAB_NAMES, TAB_TO_CAT } = window.DeltaCats;
  const Pl = window.DeltaPlaceholders;

  // Map a tab code to a "real" panel (existing rich panels reused under new codes)
  function renderTab(code, ctx) {
    const { snap, sel, setSelFor, setSel, setTab } = ctx;
    switch (code) {
      // Reused rich panels
      case 'MKT':  return <P.MarketsPanel snap={snap} />;
      case 'CRY':  return P.CryptoPanel    ? <P.CryptoPanel snap={snap} />    : <NotImplemented code="CRY" name="Crypto" />;
      case 'FIR':  return P.WildfiresPanel ? <P.WildfiresPanel />             : <NotImplemented code="FIR" name="Wildfires" />;
      case 'WLD':  return <P.WorldPanel snap={snap} sel={sel.world} setSel={(v) => setSel(s => ({ ...s, world: v }))} />;
      case 'ACR':  return <P.AircraftPanel snap={snap} sel={sel.aircraft} setSel={setSelFor('aircraft')} />;
      case 'VES':  return <P.ShipsPanel snap={snap} sel={sel.ships} setSel={setSelFor('ships')} />;
      case 'SAT':  return P.SatellitesPanel ? <P.SatellitesPanel snap={snap} /> : <NotImplemented code="SAT" name="Satellites" />;
      case 'ISS':  return P.ISSPanel ? <P.ISSPanel snap={snap} /> : <P.SpacePanel snap={snap} />;
      case 'TRF':  return P.CamerasPanel ? <P.CamerasPanel /> : <NotImplemented code="TRF" name="Traffic Cams" />;
      case 'WEA':  return <P.WeatherPanel snap={snap} sel={sel.weather} setSel={setSelFor('weather')} />;
      case 'CLM':  return <P.WeatherPanel snap={snap} sel={sel.weather} setSel={setSelFor('weather')} />;
      case 'EAR':  return <P.QuakesPanel snap={snap} sel={sel.quake} setSel={setSelFor('quake')} />;
      case 'NEWS': return <P.NewsPanel snap={snap} />;
      case 'PKG':  return <P.ParkingPanel snap={snap} sel={sel.parking} setSel={setSelFor('parking')} />;
      case 'CMD':  return <P.CommandPanel snap={snap} onJump={(c) => setTab(c)} />;
      // Finance
      case 'EQT':  return P.EquityPanel       ? <P.EquityPanel snap={snap} />       : <NotImplemented code="EQT" name="Equity" />;
      case 'BND':  return P.BondsPanel        ? <P.BondsPanel snap={snap} />        : <NotImplemented code="BND" name="Bonds" />;
      case 'FRX':  return P.ForexPanel        ? <P.ForexPanel snap={snap} />        : <NotImplemented code="FRX" name="Forex" />;
      case 'FRD':  return P.FredPanel         ? <P.FredPanel snap={snap} />         : <NotImplemented code="FRD" name="FRED Macro" />;
      case 'MCR':  return P.FredPanel         ? <P.FredPanel snap={snap} />         : <NotImplemented code="MCR" name="Macro" />;
      case 'COM':  return P.CommoditiesPanel  ? <P.CommoditiesPanel snap={snap} />  : <NotImplemented code="COM" name="Commodities" />;
      case 'OFL':  return P.OptionsFlowPanel  ? <P.OptionsFlowPanel snap={snap} />  : <NotImplemented code="OFL" name="Options Flow" />;
      case 'OPT':  return P.OptionsMispricingPanel ? <P.OptionsMispricingPanel /> : <NotImplemented code="OPT" name="Options Mispricing" />;
      case 'OF3':  return P.OrderFlow3DPanel  ? <P.OrderFlow3DPanel snap={snap} />  : <NotImplemented code="OF3" name="Order Flow 3D" />;
      case 'REC':  return P.RecPanel          ? <P.RecPanel snap={snap} />          : <NotImplemented code="REC" name="AI Picks" />;
      case 'INS':  return P.EdgarPanel        ? <P.EdgarPanel snap={snap} />        : <NotImplemented code="INS" name="INS - Insider" />;
      case 'CRT':  return P.ChartsPanel       ? <P.ChartsPanel snap={snap} />       : <NotImplemented code="CRT" name="Charts" />;
      case 'ERN':  return P.EarningsPanel     ? <P.EarningsPanel snap={snap} />     : <NotImplemented code="ERN" name="Earnings" />;
      case 'PFL':  return P.PortfolioPanel    ? <P.PortfolioPanel snap={snap} />    : <NotImplemented code="PFL" name="Portfolio" />;
      case 'ALT':  return P.AlertsPanel       ? <P.AlertsPanel snap={snap} />       : <NotImplemented code="ALT" name="Alerts" />;
      case 'DRK':  return P.DarkpoolPanel     ? <P.DarkpoolPanel snap={snap} />     : <NotImplemented code="DRK" name="Dark Pool" />;
      // Cyber
      case 'CVE':  return P.CvePanel        ? <P.CvePanel snap={snap} />        : <NotImplemented code="CVE" name="Vulnerabilities" />;
      case 'NET':  return P.OutagesPanel    ? <P.OutagesPanel snap={snap} />    : <NotImplemented code="NET" name="Net Outages" />;
      case 'THR':  return P.ThreatPanel     ? <P.ThreatPanel snap={snap} />     : <NotImplemented code="THR" name="Threat Intel" />;
      case 'DAR':  return P.DarPanel        ? <P.DarPanel snap={snap} />        : <NotImplemented code="DAR" name="Dark Web" />;
      // Science
      case 'SOL':  return P.SolarPanel      ? <P.SolarPanel snap={snap} />      : <NotImplemented code="SOL" name="Space Weather" />;
      case 'RKT':  return P.LaunchesPanel   ? <P.LaunchesPanel snap={snap} />   : <NotImplemented code="RKT" name="Launches" />;
      case 'NEO':  return P.NeoPanel        ? <P.NeoPanel snap={snap} />        : <NotImplemented code="NEO" name="Near Earth" />;
      // Geopolitics
      case 'WAR':  return P.ConflictsPanel  ? <P.ConflictsPanel snap={snap} />  : <NotImplemented code="WAR" name="Conflicts" />;
      case 'POL':  return P.PolPanel        ? <P.PolPanel snap={snap} />        : <NotImplemented code="POL" name="Politics" />;
      case 'TER':  return P.TerPanel        ? <P.TerPanel snap={snap} />        : <NotImplemented code="TER" name="Incidents" />;
      case 'DIP':  return P.DipPanel        ? <P.DipPanel snap={snap} />        : <NotImplemented code="DIP" name="Diplomacy" />;
      case 'INT':  return P.IntPanel        ? <P.IntPanel snap={snap} />        : <NotImplemented code="INT" name="Intel" />;
      case 'SAN':  return P.SanctionsPanel  ? <P.SanctionsPanel snap={snap} />  : <NotImplemented code="SAN" name="Sanctions" />;
      // Demographics
      case 'POP':  return P.PopulationPanel  ? <P.PopulationPanel snap={snap} />  : <NotImplemented code="POP" name="Population" />;
      case 'MIG':  return P.MigrationPanel   ? <P.MigrationPanel snap={snap} />   : <NotImplemented code="MIG" name="Migration" />;
      case 'REF':  return P.MigrationPanel   ? <P.MigrationPanel snap={snap} />   : <NotImplemented code="REF" name="Displacement" />;
      case 'URB':  return P.UrbanPanel       ? <P.UrbanPanel snap={snap} />       : <NotImplemented code="URB" name="Urbanization" />;
      case 'LBR':  return P.LaborPanel       ? <P.LaborPanel snap={snap} />       : <NotImplemented code="LBR" name="Labor" />;
      case 'EDU':  return P.EducationPanel   ? <P.EducationPanel snap={snap} />   : <NotImplemented code="EDU" name="Education" />;
      // Tech / Science
      case 'AI':   return P.ArxivPanel       ? <P.ArxivPanel key="ai"    snap={snap} />                    : <NotImplemented code="AI" name="AI Research" />;
      case 'BIO':  return P.ArxivPanel       ? <P.ArxivPanel key="bio"   snap={snap} />                    : <NotImplemented code="BIO" name="Biology" />;
      case 'QNT':  return P.ArxivPanel       ? <P.ArxivPanel key="quant" snap={snap} defaultTab="quant" /> : <NotImplemented code="QNT" name="Quantum" />;
      case 'ROB':  return P.ArxivPanel       ? <P.ArxivPanel key="rob"   snap={snap} defaultTab="rob" />   : <NotImplemented code="ROB" name="Robotics" />;
      case 'SEM':  return P.ArxivPanel       ? <P.ArxivPanel key="sem"   snap={snap} defaultTab="sem" />   : <NotImplemented code="SEM" name="Semis" />;
      // Health
      case 'HLT':  return P.HealthPanel      ? <P.HealthPanel snap={snap} />      : <NotImplemented code="HLT" name="Health" />;
      // Manufacturing
      case 'MFG':  return P.ManufacturingPanel ? <P.ManufacturingPanel snap={snap} /> : <NotImplemented code="MFG" name="Manufacturing" />;
      // Climate alias
      case 'CLI':  return P.ClimatePanel ? <P.ClimatePanel snap={snap} /> : <P.WeatherPanel snap={snap} sel={sel.weather} setSel={setSelFor('weather')} />;
      // Energy
      case 'OIL':  return P.OilPanel        ? <P.OilPanel snap={snap} />        : <NotImplemented code="OIL" name="Oil Markets" />;
      case 'GAS':  return P.GasPanel        ? <P.GasPanel snap={snap} />        : <NotImplemented code="GAS" name="Natural Gas" />;
      case 'NUC':  return P.NuclearPanel    ? <P.NuclearPanel snap={snap} />    : <NotImplemented code="NUC" name="Nuclear" />;
      case 'REN':  return P.RenewablesPanel ? <P.RenewablesPanel snap={snap} /> : <NotImplemented code="REN" name="Renewables" />;
      case 'ELG':  return P.GridPanel       ? <P.GridPanel snap={snap} />       : <NotImplemented code="ELG" name="Power Grid" />;
      // Supply chain aliases
      case 'SHP':  return <P.ShipsPanel snap={snap} sel={sel.ships} setSel={setSelFor('ships')} />;
      case 'AIR':  return <P.AircraftPanel snap={snap} sel={sel.aircraft} setSel={setSelFor('aircraft')} />;
      case 'INV':  return P.InventoryPanel   ? <P.InventoryPanel snap={snap} />   : <NotImplemented code="INV" name="Inventory" />;
      case 'PRT':  return P.PortsPanel       ? <P.PortsPanel snap={snap} />       : <NotImplemented code="PRT" name="Ports" />;
      // Social
      case 'SOC':  return P.SocPanel         ? <P.SocPanel snap={snap} />         : <NotImplemented code="SOC" name="Social" />;
      // Ocean / Sea Ice
      case 'OCN':  return P.OceanPanel      ? <P.OceanPanel snap={snap} />      : <NotImplemented code="OCN" name="Sea Ice" />;
      // Global Trade
      case 'TRD':  return P.TradePanel      ? <P.TradePanel snap={snap} />      : <NotImplemented code="TRD" name="Trade" />;
      // Elections
      case 'ELE':  return P.ElectionsPanel  ? <P.ElectionsPanel snap={snap} />  : <NotImplemented code="ELE" name="Elections" />;
      // Data Breaches
      case 'LEK':  return P.LeaksPanel      ? <P.LeaksPanel snap={snap} />      : <NotImplemented code="LEK" name="Leaks" />;
      // Cloudflare Radar
      case 'CLD':  return P.CloudflarePanel ? <P.CloudflarePanel snap={snap} /> : <NotImplemented code="CLD" name="Cloud" />;
      // CISA Incident Response
      case 'HAC':  return P.HacPanel        ? <P.HacPanel snap={snap} />        : <NotImplemented code="HAC" name="Incident Resp" />;
      default:
        return <NotImplemented code={code} name={TAB_NAMES[code] || code} />;
    }
  }

  function NotImplemented({ code, name }) {
    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head"><span>◆ {code} · {name.toUpperCase()}</span></div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column', gap: 12 }}>
            <div style={{ fontSize: 24, color: 'var(--border-3)', letterSpacing: '.05em' }}>◌</div>
            <div style={{ fontSize: 11, letterSpacing: '.12em', color: 'var(--text-2)' }}>NO LIVE FEED</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', letterSpacing: '.04em' }}>
              {name} data source not yet connected
            </div>
          </div>
        </div>
      </div>
    );
  }

  function App() {
    const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
    const [prevTheme, setPrevTheme] = useState(t.theme === 'noir' ? 'paper' : t.theme);
    const toggleNoir = () => {
      if (t.theme === 'noir') {
        setTweak('theme', prevTheme || 'paper');
      } else {
        setPrevTheme(t.theme);
        setTweak('theme', 'noir');
      }
    };
    // Workspaces = terminal/browser-style tabs. Each holds its own pane layout
    // and can be popped out into a new window.
    function initialWorkspaces() {
      try {
        const p = new URLSearchParams(location.search);
        const t0 = p.get('tab') || (p.get('panes') || '').split(',').filter(Boolean)[0];
        if (t0 && TAB_NAMES[t0]) return [{ id: 1, tab: t0 }];
      } catch (e) {}
      return [{ id: 1, tab: 'MKT' }];
    }
    const [workspaces, setWorkspaces] = useState(initialWorkspaces);
    const [activeWs, setActiveWs] = useState(0);
    const ws = workspaces[Math.min(activeWs, workspaces.length - 1)] || workspaces[0];
    const tab = ws.tab || 'MKT';

    const setTab = useCallback((code) => {
      setWorkspaces(list => list.map((w, i) => i === activeWs ? { ...w, tab: code } : w));
    }, [activeWs]);
    function addWorkspace() {
      setWorkspaces(list => [...list, { id: Date.now(), tab: 'MKT' }]);
      setActiveWs(workspaces.length);
    }
    function closeWorkspace(i) {
      setWorkspaces(list => list.length <= 1 ? list : list.filter((_, j) => j !== i));
      setActiveWs(a => (i < a ? a - 1 : (i === a ? Math.max(0, a - 1) : a)));
    }
    function popOut(i) {
      const w = workspaces[i];
      const abs = location.origin + location.pathname + '?tab=' + encodeURIComponent(w.tab);
      // Desktop app: native window via the pywebview js_api bridge in desktop.py.
      try {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.open_window) {
          window.pywebview.api.open_window(abs);
          return;
        }
      } catch (e) { /* fall through */ }
      // Browser: open a new TAB (no size = not treated as a blockable popup),
      // then fall back to a sized window.
      let win = window.open(abs, '_blank');
      if (!win) win = window.open(abs, '_blank', 'width=1280,height=820');
      if (win) { try { win.focus(); } catch (e) {} return; }
      console.warn('pop-out blocked for', abs);
      alert('Browser blocked the new window/tab.\n\n' +
            '• Click the ⧉ icon on a tab (a click is allowed; a drag often is not), or\n' +
            '• Allow pop-ups for this site, or\n' +
            '• Run the desktop app for real OS windows:  python3.13 desktop.py\n\n' +
            'URL: ' + abs);
    }
    const cat = TAB_TO_CAT[tab] || 'fin';
    const setCat = (newCat) => {
      const c = CATEGORIES.find(x => x.code === newCat);
      if (c) setTab(c.tabs[0]);
    };
    const [snap, setSnap] = useState(EMPTY_SNAP);
    const [sel, setSel] = useState({});
    const [zen, setZen] = useState(false);   // fullscreen the active tab
    const [cmd, setCmd] = useState('');
    const [now, setNow] = useState(new Date());
    const [wsState, setWsState] = useState('connecting');
    const cmdRef = useRef(null);
    const prevPricesRef = useRef({});  // ticker → last known price

    // Apply theme + density to <html>
    useEffect(() => {
      document.documentElement.setAttribute('data-theme', t.theme);
      document.documentElement.style.setProperty('--row-pad-y', t.density === 'compact' ? '1px' : t.density === 'comfy' ? '6px' : '3px');
      document.documentElement.style.setProperty('--base-font', t.density === 'compact' ? '11px' : t.density === 'comfy' ? '13px' : '12px');
    }, [t.theme, t.density]);

    // Clock
    useEffect(() => {
      const id = setInterval(() => setNow(new Date()), 1000);
      return () => clearInterval(id);
    }, []);

    // Live backend hydration — only real data, no mock fallback
    useEffect(() => {
      if (!window.DeltaLive) return;
      const load = () => window.DeltaLive.fetchAll()
        .then(live => {
          // Seed price baseline so first diff works correctly
          const prev = prevPricesRef.current;
          [...(live.indices||[]), ...(live.tech||[]), ...(live.macro||[])].forEach(r => { if (r.ticker) prev[r.ticker] = r.price; });
          (live.crypto||[]).forEach(r => { if (r.symbol) prev[r.symbol] = r.price; });
          setSnap(live);
          setWsState('connected');
        })
        .catch(() => setWsState('down'));
      load();
      const id = setInterval(load, 60_000);
      return () => clearInterval(id);
    }, []);

    useEffect(() => {
      if (!window.DeltaLive) return;

      function tagDir(rows, keyField) {
        const prev = prevPricesRef.current;
        return rows.map(r => {
          const k = r[keyField];
          const p = prev[k];
          const dir = p == null ? null : r.price > p ? 'up' : r.price < p ? 'down' : null;
          prev[k] = r.price;
          return dir ? { ...r, _dir: dir } : r;
        });
      }

      const loadPrices = () => window.DeltaLive.fetchPrices().then(p => {
        const hasMkt = p.mkt && p.mkt.indices && p.mkt.indices.length > 0;
        const hasCry = p.crypto && p.crypto.length > 0;
        setSnap(s => ({
          ...s,
          ...(hasMkt ? {
            indices: tagDir(p.mkt.indices, 'ticker'),
            tech:    tagDir(p.mkt.tech,    'ticker'),
            macro:   tagDir(p.mkt.macro,   'ticker'),
          } : {}),
          ...(hasCry ? { crypto: tagDir(p.crypto, 'symbol') } : {}),
        }));
        // Clear _dir flags after animation completes (900ms > 800ms animation)
        setTimeout(() => setSnap(s => ({
          ...s,
          indices: s.indices.map(r => r._dir ? { ...r, _dir: null } : r),
          tech:    s.tech.map(r    => r._dir ? { ...r, _dir: null } : r),
          macro:   s.macro.map(r   => r._dir ? { ...r, _dir: null } : r),
          crypto:  s.crypto.map(r  => r._dir ? { ...r, _dir: null } : r),
        })), 900);
      }).catch(() => {});
      const id = setInterval(loadPrices, 2_000);
      return () => clearInterval(id);
    }, []);

    // Real-time tick stream — flash individual rows the moment a trade arrives
    useEffect(() => {
      const es = new EventSource('http://localhost:8000/api/markets/stream');
      es.onmessage = (e) => {
        if (!e.data || e.data.startsWith(':')) return;
        let tick;
        try { tick = JSON.parse(e.data); } catch { return; }
        const { s: ticker, p: price } = tick;
        if (!ticker || !price) return;

        setSnap(snap => {
          const prev = prevPricesRef.current;
          const oldPrice = prev[ticker];
          if (oldPrice === price) return snap;
          const dir = price > oldPrice ? 'up' : 'down';
          prev[ticker] = price;

          function patchRows(rows) {
            const i = rows.findIndex(r => r.ticker === ticker);
            if (i === -1) return rows;
            const r = rows[i];
            const pc = r.prev_close || r.price;
            const updated = [...rows];
            updated[i] = { ...r, price, _dir: dir,
              change: price - pc,
              change_pct: pc ? ((price - pc) / pc * 100) : r.change_pct,
            };
            return updated;
          }

          return { ...snap,
            indices: patchRows(snap.indices),
            tech:    patchRows(snap.tech),
            macro:   patchRows(snap.macro),
          };
        });

        setTimeout(() => setSnap(snap => {
          function clearRow(rows) {
            const i = rows.findIndex(r => r.ticker === ticker && r._dir);
            if (i === -1) return rows;
            const updated = [...rows];
            updated[i] = { ...updated[i], _dir: null };
            return updated;
          }
          return { ...snap, indices: clearRow(snap.indices), tech: clearRow(snap.tech), macro: clearRow(snap.macro) };
        }), 900);
      };
      es.onerror = () => {};
      return () => es.close();
    }, []);

    useEffect(() => {
      if (!window.DeltaLive) return;
      const loadPos = () => window.DeltaLive.fetchPositions().then(p => {
        setSnap(s => ({
          ...s,
          ...(p.aircraft && p.aircraft.length > 0 ? { aircraft: p.aircraft } : {}),
          ...(p.ships    && p.ships.length    > 0 ? { ships:    p.ships    } : {}),
        }));
      }).catch(() => {});
      const id = setInterval(loadPos, 15_000);
      return () => clearInterval(id);
    }, []);


    // Keyboard
    useEffect(() => {
      const onKey = (e) => {
        // Reload the UI (pywebview has no F5). Works even from inputs.
        if (((e.metaKey || e.ctrlKey) && (e.key === 'r' || e.key === 'R')) || e.key === 'F5') {
          e.preventDefault(); location.reload(); return;
        }
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
          if (e.key === 'Escape') e.target.blur();
          return;
        }
        if (e.key >= '0' && e.key <= '9') {
          const i = e.key === '0' ? 9 : parseInt(e.key, 10) - 1;
          if (CATEGORIES[i]) setCat(CATEGORIES[i].code);
        } else if (e.key === 'Tab') {
          e.preventDefault();
          const tabs = (CATEGORIES.find(c => c.code === cat) || CATEGORIES[0]).tabs;
          const i = tabs.indexOf(tab);
          setTab(tabs[(i + (e.shiftKey ? tabs.length - 1 : 1)) % tabs.length]);
        } else if (e.key === '/') {
          e.preventDefault();
          cmdRef.current && cmdRef.current.focus();
        } else if (e.key === '?') {
          setTab('CMD');
        } else if (e.key === 'f' || e.key === 'F') {
          setZen(z => !z);
        } else if (e.key === 'Escape') {
          if (zen) setZen(false);
          else setSel({});
        }
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }, [tab, cat, zen, activeWs]);

    // Toggling fullscreen resizes the panel container; nudge resize-aware
    // widgets (Plotly 3D order-flow, charts, maps) to refit the new size.
    useEffect(() => {
      const id = setTimeout(() => window.dispatchEvent(new Event('resize')), 60);
      return () => clearTimeout(id);
    }, [zen, activeWs]);

    const runCmd = () => {
      const c = cmd.trim().toUpperCase();
      if (!c) return;
      if (/^[1-9]$/.test(c)) {
        const cIdx = parseInt(c, 10) - 1;
        if (CATEGORIES[cIdx]) { setCat(CATEGORIES[cIdx].code); setCmd(''); return; }
      }
      // Direct tab code (MKT, EQT, CVE, etc)
      if (TAB_NAMES[c]) { setTab(c); setCmd(''); return; }
      // Category code (fin, geo, etc)
      const catMatch = CATEGORIES.find(x => x.code.toUpperCase() === c || x.label === c);
      if (catMatch) { setCat(catMatch.code); setCmd(''); return; }
      if (c === 'HELP' || c === '?') { setTab('CMD'); setCmd(''); return; }
      setCmd('');
    };

    const setSelFor = useCallback((kind) => (id) =>
      setSel(s => ({ ...s, [kind]: s[kind] === id ? null : id })), []);

    // Ticker content
    const ticker = useMemo(() => {
      const tickItems = [
        ...snap.indices.slice(0, 8).map(q => ({ sym: q.ticker.replace('^',''), px: q.price, pct: q.change_pct, color: q.color })),
        ...snap.crypto.slice(0, 6).map(c => ({ sym: c.name.toUpperCase(), px: c.price, pct: c.change_pct_24h, color: c.color })),
        ...snap.macro.slice(0, 6).map(q => ({ sym: q.ticker.replace('=F','').replace('=X',''), px: q.price, pct: q.change_pct, color: q.color })),
      ];
      return tickItems;
    }, [snap]);

    const utc = now.toISOString().slice(11, 19);
    const date = now.toISOString().slice(0, 10);

    return (
      <>
        {/* DRAG STRIP — window move handle (pywebview drag-region / electron app-region) */}
        <div className="pywebview-drag-region" style={{ height: 10, flexShrink: 0,
          background: 'var(--surface-2)', borderBottom: '1px solid var(--border)',
          WebkitAppRegion: 'drag', cursor: 'grab' }} />

        {/* WORKSPACE TABS — terminal-style tabs; ⧉ pops out to a new window */}
        <div className="nosel" style={{ display: 'flex', alignItems: 'stretch', height: 26,
          flexShrink: 0, background: 'var(--bg-2)', borderBottom: '1px solid var(--border)',
          overflowX: 'auto', overflowY: 'hidden' }}>
          {workspaces.map((w, i) => {
            const active = i === activeWs;
            const label = TAB_NAMES[w.tab] || w.tab || ('WS ' + (i + 1));
            return (
              <div key={w.id} draggable
                onMouseDown={() => setActiveWs(i)}
                title={label + '  ·  drag out of the window → new window'}
                onDragStart={(e) => {
                  e.dataTransfer.effectAllowed = 'move';
                  try { e.dataTransfer.setData('text/plain', label); } catch (er) {}
                }}
                onDragEnd={(e) => {
                  // Tear off if released outside the window OR dragged off the tab
                  // strip into the panel area (a reliable inside-window signal that
                  // works even when screen-coords are unavailable in the webview).
                  const w0 = window.screenX || 0, h0 = window.screenY || 0;
                  const ww = window.outerWidth || 0, wh = window.outerHeight || 0;
                  const outside = (ww && (e.screenX < w0 || e.screenX > w0 + ww))
                               || (wh && (e.screenY < h0 || e.screenY > h0 + wh));
                  const draggedOffBar = e.clientY > 70 || e.clientY <= 0 || e.clientX <= 0
                               || e.clientX >= (window.innerWidth || 99999);
                  if (outside || draggedOffBar) popOut(i);
                }}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 8px',
                  cursor: 'pointer', fontSize: 10, letterSpacing: '.05em', whiteSpace: 'nowrap',
                  maxWidth: 200, background: active ? 'var(--surface)' : 'transparent',
                  color: active ? 'var(--cyan)' : 'var(--text-2)',
                  borderRight: '1px solid var(--border)',
                  borderTop: '2px solid ' + (active ? 'var(--cyan)' : 'transparent') }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>
                <span title="Pop out to new window"
                  onClick={(e) => { e.stopPropagation(); popOut(i); }}
                  style={{ color: 'var(--muted)', padding: '0 2px', fontSize: 11 }}>⧉</span>
                {workspaces.length > 1 && (
                  <span title="Close tab"
                    onClick={(e) => { e.stopPropagation(); closeWorkspace(i); }}
                    style={{ color: 'var(--muted)', padding: '0 3px' }}>×</span>
                )}
              </div>
            );
          })}
          <button onClick={addWorkspace} title="New tab"
            style={{ border: 'none', background: 'transparent', color: 'var(--cyan)',
              padding: '0 12px', fontSize: 15, cursor: 'pointer', fontFamily: 'var(--mono)' }}>+</button>
          <button onClick={() => location.reload()} title="Reload UI (Cmd/Ctrl+R · F5)"
            style={{ border: 'none', background: 'transparent', color: 'var(--muted)',
              padding: '0 12px', fontSize: 13, cursor: 'pointer', fontFamily: 'var(--mono)',
              marginLeft: 'auto' }}>↻</button>
        </div>
        {/* TICKER */}
        <div style={{ height: 26, background: 'var(--surface)', borderBottom: '1px solid var(--border)',
          overflow: 'hidden', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap' }}>
          <div style={{ padding: '0 10px', color: 'var(--cyan)', fontSize: 10, letterSpacing: '.14em',
            borderRight: '1px solid var(--border)', background: 'var(--surface-2)', height: '100%', display: 'flex', alignItems: 'center' }}>TAPE</div>
          <div className="marquee-track" style={{ paddingLeft: 24, lineHeight: '26px', fontSize: 11 }}>
            {[...ticker, ...ticker].map((t, i) => (
              <span key={i} style={{ marginRight: 28 }}>
                <span className="lbl">{t.sym}</span>{' '}
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>{fmt(t.px)}</span>{' '}
                <span className={t.color}>{t.color === 'up' ? '▲' : '▼'} {Math.abs(t.pct).toFixed(2)}%</span>
                <span className="dim" style={{ margin: '0 12px' }}>·</span>
              </span>
            ))}
          </div>
        </div>

        {/* HEADER */}
        <div className="nosel" style={{ height: 42, background: 'var(--bg-2)', borderBottom: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', padding: '0 12px', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 18, color: 'var(--cyan)' }}>◆</span>
            <span style={{ fontSize: 14, letterSpacing: '.18em', fontWeight: 600 }}>DELTA TERMINAL</span>
            <span className="mut" style={{ fontSize: 10, marginLeft: 4 }}>v0.4.1</span>
          </div>
          <span style={{ flex: 1 }} />

          {/* Function bar */}
          <div style={{ display: 'flex', alignItems: 'center', border: '1px solid var(--border-2)',
            background: 'var(--bg)', height: 26, padding: '0 8px', gap: 8 }}>
            <span className="lbl" style={{ fontSize: 10, letterSpacing: '.1em' }}>CMD ›</span>
            <input ref={cmdRef} value={cmd} onChange={e => setCmd(e.target.value.toUpperCase())}
              onKeyDown={e => { if (e.key === 'Enter') runCmd(); }}
              placeholder="type a function (HELP, MKT, AIR…)"
              style={{ background: 'transparent', border: 'none', color: 'var(--text)',
                fontFamily: 'var(--mono)', fontSize: 11, outline: 'none', width: 280, letterSpacing: '.05em' }} />
            <button className="btn" style={{ padding: '1px 8px', fontSize: 10 }} onClick={runCmd}>GO</button>
          </div>

          {/* Noir toggle */}
          <button onClick={toggleNoir}
            title={t.theme === 'noir' ? 'Exit dark mono mode' : 'Boring dark mode'}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: 'transparent', border: '1px solid var(--border-2)',
              color: 'var(--text-2)', fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '.06em',
              padding: '2px 6px 2px 4px', cursor: 'pointer', height: 22,
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-3)'; e.currentTarget.style.color = 'var(--text)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-2)'; e.currentTarget.style.color = 'var(--text-2)'; }}
          >
            <span style={{ fontSize: 11 }}>{t.theme === 'noir' ? '◐' : '◑'}</span>
            <span style={{
              position: 'relative', width: 24, height: 12,
              background: t.theme === 'noir' ? '#1a1a1a' : 'var(--surface-3)',
              border: '1px solid var(--border-2)', borderRadius: 7,
            }}>
              <span style={{
                position: 'absolute', top: 0, left: t.theme === 'noir' ? 12 : 0,
                width: 10, height: 10, borderRadius: '50%',
                background: t.theme === 'noir' ? '#ffffff' : 'var(--cyan)',
                transition: 'left .15s ease',
              }} />
            </span>
            <span>{t.theme === 'noir' ? 'NOIR' : 'DARK'}</span>
          </button>

          {/* Clock + status */}
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', fontSize: 11 }}>
            <span className="mut">{date}</span>
            <span style={{ fontWeight: 600, letterSpacing: '.06em' }}>{utc} <span className="mut">UTC</span></span>
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              <span className="mut">WS</span>
              <span style={{ width: 8, height: 8, borderRadius: '50%',
                background: wsState === 'connected' ? 'var(--mint)' : wsState === 'connecting' ? 'var(--amber)' : 'var(--rose)',
                boxShadow: wsState === 'connected' ? '0 0 6px var(--mint)' : 'none' }} />
            </span>
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              <span className="mut">FEED</span>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--mint)', boxShadow: '0 0 6px var(--mint)' }} />
            </span>
          </div>
        </div>

        {/* CATEGORY BAR */}
        <div className="nosel" style={{ height: 30, display: 'flex', background: 'var(--bg-2)',
          borderBottom: '1px solid var(--border)', padding: '0 6px', gap: 4, alignItems: 'center', overflowX: 'auto' }}>
          {CATEGORIES.map((c, i) => {
            const active = c.code === cat;
            return (
              <button key={c.code} onClick={() => setCat(c.code)}
                style={{
                  background: active ? 'var(--cyan)' : 'transparent',
                  color: active ? 'var(--bg)' : 'var(--text-2)',
                  border: '1px solid ' + (active ? 'var(--cyan)' : 'var(--border-2)'),
                  borderRadius: 0,
                  padding: '2px 10px', height: 22,
                  cursor: 'pointer',
                  fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '.12em',
                  fontWeight: active ? 700 : 500,
                  display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}>
                <span style={{ opacity: 0.65, fontWeight: 400 }}>{i === 9 ? '0' : i + 1}</span>
                {c.label}
                <span style={{ opacity: 0.55, fontSize: 9 }}>·{c.tabs.length}</span>
              </button>
            );
          })}
        </div>

        {/* TABS */}
        <div className="tabbar nosel" style={{ height: 34, position: 'relative', background: 'var(--surface)',
          borderBottom: '1px solid var(--border)' }}>
          <div
            ref={(el) => {
              if (!el || el._wheelBound) return;
              el._wheelBound = true;
              el.addEventListener('wheel', (ev) => {
                if (Math.abs(ev.deltaY) > Math.abs(ev.deltaX)) {
                  el.scrollLeft += ev.deltaY;
                  ev.preventDefault();
                }
              }, { passive: false });
            }}
            style={{
              height: '100%', display: 'flex', overflowX: 'auto', overflowY: 'hidden',
              scrollbarWidth: 'thin',
            }}>
          {(CATEGORIES.find(c => c.code === cat) || CATEGORIES[0]).tabs.map(code => {
            const active = code === tab;
            const name = TAB_NAMES[code] || code;
            return (
              <button key={code} onClick={() => setTab(code)}
                style={{
                  background: active ? 'var(--bg)' : 'transparent',
                  border: 'none',
                  borderRight: '1px solid var(--border)',
                  borderTop: active ? '2px solid var(--cyan)' : '2px solid transparent',
                  borderBottom: active ? '1px solid var(--bg)' : '1px solid var(--border)',
                  marginBottom: -1,
                  padding: '0 14px',
                  color: active ? 'var(--cyan)' : 'var(--text-2)',
                  cursor: 'pointer',
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                  letterSpacing: '.08em',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontWeight: active ? 600 : 400,
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'var(--surface-2)'; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <span>{code}</span>
                <span style={{ color: 'var(--muted)', fontWeight: 400, fontSize: 10 }}>{name}</span>
              </button>
            );
          })}
          <div style={{ flex: 1, minWidth: 60, borderBottom: '1px solid var(--border)', marginBottom: -1 }} />
          </div>
          <button className="btn" onClick={() => setZen(true)} title="Fullscreen this tab (F)"
            style={{ position: 'absolute', right: 6, top: 5, height: 24, padding: '0 8px',
                     fontSize: 11, zIndex: 3, background: 'var(--surface-2)' }}>⤢ FULL</button>
        </div>

        {/* PANEL */}
        {zen ? (
          <div style={{ position: 'fixed', inset: 0, zIndex: 5000, background: 'var(--bg)' }}>
            <button className="btn" onClick={() => setZen(false)} title="Exit fullscreen (Esc / F)"
              style={{ position: 'fixed', top: 8, right: 10, zIndex: 6000, padding: '3px 10px',
                       opacity: 0.92, letterSpacing: '.08em' }}>
              ⤡ EXIT · {TAB_NAMES[tab] || tab}
            </button>
            {renderTab(tab, { snap, sel, setSelFor, setSel, setTab })}
          </div>
        ) : (
          <div style={{ flex: 1, minHeight: 0, background: 'var(--bg)', position: 'relative' }}>
            {renderTab(tab, { snap, sel, setSelFor, setSel, setTab })}
          </div>
        )}

        {/* STATUS BAR */}
        <div className="nosel" style={{ height: 24, background: 'var(--surface-2)', borderTop: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', padding: '0 10px', gap: 14, fontSize: 10, letterSpacing: '.05em' }}>
          <span><span className="kbd">F1</span> <span className="mut">HELP</span></span>
          <span><span className="kbd">/</span>  <span className="mut">SEARCH</span></span>
          <span><span className="kbd">R</span>  <span className="mut">REFRESH</span></span>
          <span><span className="kbd">Tab</span> <span className="mut">NEXT</span></span>
          <span><span className="kbd">Esc</span> <span className="mut">CLEAR</span></span>
          <span><span className="kbd">F</span>   <span className="mut">FULLSCREEN</span></span>
          <span style={{ flex: 1 }} />
          <span className="mut">ws://localhost:8000/ws</span>
          <span className="up">● LIVE</span>
          <span className="mut">·</span>
          <span><span><span className="mut">CAT</span> <span className="lbl">{(CATEGORIES.find(c => c.code === cat) || {}).label}</span></span></span>
          <span><span className="mut">VESSELS</span> <span className="lbl">{snap.ships.length}</span></span>
          <span><span className="mut">AIRCRAFT</span> <span className="lbl">{snap.aircraft.length}</span></span>
          <span><span className="mut">TICKERS</span> <span className="lbl">{snap.indices.length + snap.tech.length + snap.macro.length + snap.crypto.length}</span></span>
          <span><span className="mut">QUAKES</span> <span className="lbl">{snap.quakes.recent.length + snap.quakes.significant.length}</span></span>
          <span style={{ color: 'var(--muted)', minWidth: 64, textAlign: 'right' }}>guest@delta</span>
        </div>
        {/* Tweaks panel */}
        <TweaksPanel title="Theme & display">
          <TweakSection label="Palette" />
          <TweakSelect label="Theme" value={t.theme}
            options={['paper','noir']}
            onChange={(v) => setTweak('theme', v)} />
          <div style={{ display: 'flex', gap: 6, marginTop: -4 }}>
            {[
              { name: 'paper', bg: '#f5f1e6', fg: '#8a3a0c', tx: '#1a1208' },
              { name: 'noir',  bg: '#000000', fg: '#d4d4d4', tx: '#d8d8d8' },
            ].map(p => (
              <button key={p.name} type="button" onClick={() => setTweak('theme', p.name)}
                title={p.name}
                style={{
                  flex: 1, height: 38, padding: 0, cursor: 'pointer',
                  background: p.bg, color: p.tx,
                  border: t.theme === p.name ? '2px solid #29261b' : '1px solid rgba(0,0,0,.15)',
                  borderRadius: 6,
                  display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
                  fontFamily: 'JetBrains Mono, monospace', fontSize: 9, letterSpacing: '.08em',
                }}>
                <span style={{ color: p.fg, fontSize: 12, lineHeight: 1, marginBottom: 1 }}>◆</span>
                <span>{p.name.toUpperCase().slice(0,3)}</span>
              </button>
            ))}
          </div>
          <TweakRadio label="Density" value={t.density}
            options={['compact','regular','comfy']}
            onChange={(v) => setTweak('density', v)} />
          <TweakSection label="Behavior" />
          <TweakToggle label="Live ticks" value={t.animations}
            onChange={(v) => setTweak('animations', v)} />
        </TweaksPanel>
      </>
    );
  }

  ReactDOM.createRoot(document.getElementById('root')).render(<App />);
})();
