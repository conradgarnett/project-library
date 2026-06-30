// delta-live.jsx — real backend data for DELTA Terminal
// Exposes window.DeltaLive

(function () {
  const API = 'http://localhost:8000/api';

  async function get(path) {
    const r = await fetch(API + path, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  // ── Markets ──────────────────────────────────────────────────────────────────
  const IDX_SET = new Set([
    '^GSPC','^DJI','^IXIC','^RUT','^VIX','^FTSE','^N225','^HSI',
    'SPY','QQQ','IWM','DIA','GLD','TLT','HYG','EEM','XLE','XLK',
  ]);
  const MAC_SET = new Set([
    'GC=F','CL=F','BZ=F','SI=F','HG=F','NG=F','ZN=F',
    'DX-Y.NYB','EURUSD=X','JPY=X','GBPUSD=X','AUDUSD=X','USDCAD=X','BTC=F',
  ]);

  async function fetchMarkets() {
    const d = await get('/markets');
    const all = Object.values(d.quotes || {});
    return {
      indices: all.filter(q => IDX_SET.has(q.ticker)),
      macro:   all.filter(q => MAC_SET.has(q.ticker)),
      tech:    all.filter(q => !IDX_SET.has(q.ticker) && !MAC_SET.has(q.ticker)),
    };
  }

  // ── Crypto ───────────────────────────────────────────────────────────────────
  async function fetchCrypto() {
    const d = await get('/crypto');
    return Object.values(d.ticks || {});
  }

  // ── Aircraft ─────────────────────────────────────────────────────────────────
  const HDG_ARROWS = ['↑','↗','→','↘','↓','↙','←','↖'];
  function hArrow(h) { return HDG_ARROWS[Math.round(((h || 0) + 360) / 45) % 8]; }

  async function fetchAircraft() {
    const d = await get('/aircraft');
    return (d.planes || [])
      .filter(p => p.lat != null && p.lon != null)
      .map(p => ({
        ...p,
        heading_arrow: p.heading_arrow || hArrow(p.heading),
        fl:  p.fl  || (p.on_ground ? 'GND' : 'FL' + String(Math.round((p.altitude_ft||0)/100)).padStart(3,'0')),
        type: p.type || p.aircraft_type || '—',
        callsign: p.callsign || '—',
        country:  p.country  || '—',
      }));
  }

  // ── Ships ────────────────────────────────────────────────────────────────────
  async function fetchShips() {
    const d = await get('/ships');
    return (d.vessels || [])
      .filter(v => v.lat != null && v.lon != null)
      .map(v => ({
        ...v,
        heading_arrow: v.heading_arrow || hArrow(v.heading),
        dwt: v.dwt || 0,
        name:        v.name        || '—',
        type_name:   v.type_name   || '—',
        flag:        v.flag        || '—',
        destination: v.destination || '—',
      }));
  }

  // ── Space ────────────────────────────────────────────────────────────────────
  async function fetchSpace() {
    const d = await get('/space');
    const stations = [d.iss, d.tiangong].filter(Boolean);
    const sats = (d.notable || []).map(s => ({ ...s, orbit_type: s.orbit_type || 'LEO' }));
    return { stations, sats, starlink_count: d.starlink_count || 0, active_count: d.active_count || 0, iss: d.iss || null, tiangong: d.tiangong || null, crew: d.crew || [] };
  }

  // ── Weather ──────────────────────────────────────────────────────────────────
  async function fetchWeather() {
    const d = await get('/weather');
    return Object.values(d.cities || {});
  }

  // ── Earthquakes ──────────────────────────────────────────────────────────────
  async function fetchQuakes() {
    const d = await get('/earthquakes');
    return {
      recent:        d.recent        || [],
      significant:   d.significant   || [],
      largest_today: d.largest_today || null,
      hourly_count:  d.hourly_count  || 0,
      daily_count:   d.daily_count   || 0,
    };
  }

  // ── News ─────────────────────────────────────────────────────────────────────
  async function fetchNews() {
    const d = await get('/news');
    return {
      articles:       d.articles      || [],
      by_category:    d.by_category   || {},
      sources_ok:     d.sources_ok    || 0,
      sources_failed: d.sources_fail  || 0,
    };
  }

  // ── Wildfires ────────────────────────────────────────────────────────────────
  async function fetchWildfires() {
    const d = await get('/wildfires');
    return { hotspots: d.hotspots || [], count: d.count || 0, error: d.error || null };
  }

  // ── Cameras ──────────────────────────────────────────────────────────────────
  async function fetchCameras() {
    const d = await get('/cameras');
    return d.cameras || [];
  }

  // ── Parking ──────────────────────────────────────────────────────────────────
  async function fetchParking() {
    const d = await get('/parking');
    return { lots: d.lots || [], by_city: d.by_city || {}, zones: d.lots || [] };
  }

  // ── Bonds ────────────────────────────────────────────────────────────────────
  async function fetchBonds() {
    const d = await get('/bonds');
    return { maturities: d.maturities || [], spread_10y2y: d.spread_10y2y || 0 };
  }

  // ── Forex ─────────────────────────────────────────────────────────────────────
  async function fetchForex() {
    const d = await get('/forex');
    return { rates: d.rates || {} };
  }

  // ── FRED Macro ────────────────────────────────────────────────────────────────
  async function fetchFred() {
    const d = await get('/fred');
    return { series: d.series || {} };
  }

  // ── CVE / Cyber ───────────────────────────────────────────────────────────────
  async function fetchCve() {
    const d = await get('/cve');
    return { recent: d.recent || [], kev: d.kev || [], ransomware: d.ransomware || [] };
  }

  async function fetchThreats() {
    const d = await get('/threats');
    return { advisories: d.advisories || [] };
  }

  // ── Rocket Launches ───────────────────────────────────────────────────────────
  async function fetchLaunches() {
    const d = await get('/launches');
    return { upcoming: d.upcoming || [], recent: d.recent || [] };
  }

  // ── Conflicts ─────────────────────────────────────────────────────────────────
  async function fetchConflicts() {
    const d = await get('/conflicts');
    return { events: d.events || [] };
  }

  // ── Sanctions ─────────────────────────────────────────────────────────────────
  async function fetchSanctions() {
    const d = await get('/sanctions');
    return { entries: d.entries || [], count: d.count || 0, programs: d.programs || [] };
  }

  // ── Near Earth Objects ────────────────────────────────────────────────────────
  async function fetchNeo() {
    const d = await get('/neo');
    return { objects: d.objects || [], count: d.count || 0 };
  }

  // ── Space Weather ─────────────────────────────────────────────────────────────
  async function fetchSpaceWeather() {
    const d = await get('/space-weather');
    return {
      kp_index:    d.kp_index    || 0,
      kp_24h:      d.kp_24h      || [],
      solar_wind:  d.solar_wind  || {},
      x_ray_flux:  d.x_ray_flux  || 0,
      alerts:      d.alerts      || [],
      storm_level: d.storm_level || '',
    };
  }

  // ── Network Outages ───────────────────────────────────────────────────────────
  async function fetchOutages() {
    const d = await get('/outages');
    return { alerts: d.alerts || [], countries: d.countries || [], bgp: d.bgp || [] };
  }

  // ── Population ────────────────────────────────────────────────────────────────
  async function fetchPopulation() {
    const d = await get('/population');
    return { countries: d.countries || [], indicators: d.indicators || {} };
  }

  // ── Equity Fundamentals (Alpha Vantage) ───────────────────────────────────────
  async function fetchEquityFundamentals() {
    const d = await get('/equity-fundamentals');
    return { fundamentals: d.fundamentals || {} };
  }

  // ── Options Mispricing (on-demand, per ticker) ────────────────────────────────
  async function fetchOptionsMispricing(ticker) {
    // The scan hits yfinance for history + several option chains → allow ~25s.
    try {
      const r = await fetch(API + '/options-mispricing/' + encodeURIComponent(ticker),
                            { signal: AbortSignal.timeout(25000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    } catch (e) {
      return { ticker, error: String(e.message || e), rows: [], flagged: [], parity: [] };
    }
  }

  async function fetchOptionsMC(ticker, horizon = 30, volSource = 'iv') {
    try {
      const url = API + '/options-mc/' + encodeURIComponent(ticker)
                + '?horizon=' + horizon + '&vol_source=' + volSource;
      const r = await fetch(url, { signal: AbortSignal.timeout(25000) });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    } catch (e) {
      return { ticker, error: String(e.message || e) };
    }
  }

  // ── arXiv ─────────────────────────────────────────────────────────────────────
  async function fetchArxiv() {
    const d = await get('/arxiv');
    return { ai: d.ai || [], bio: d.bio || [], quant: d.quant || [], rob: d.rob || [], sem: d.sem || [] };
  }

  // ── GDELT Events ──────────────────────────────────────────────────────────────
  async function fetchGdelt() {
    const d = await get('/gdelt');
    return { pol: d.pol || [], ter: d.ter || [], dip: d.dip || [] };
  }

  // ── WHO GHO ───────────────────────────────────────────────────────────────────
  async function fetchWho() {
    const d = await get('/who');
    return { by_country: d.by_country || {}, indicators: d.indicators || [] };
  }

  // ── UNHCR ─────────────────────────────────────────────────────────────────────
  async function fetchUnhcr() {
    const d = await get('/unhcr');
    return { totals: d.totals || {}, by_origin: d.by_origin || [], by_host: d.by_host || [] };
  }

  // ── SEC EDGAR ─────────────────────────────────────────────────────────────────
  async function fetchEdgar() {
    const d = await get('/edgar');
    return {
      insider_trades: d.insider_trades || [],
      filings_8k:     d.filings_8k     || [],
      filings_10q:    d.filings_10q    || [],
    };
  }

  // ── AI Recommendations ───────────────────────────────────────────────────────
  async function fetchRecommendations() {
    const d = await get('/recommendations');
    return { stocks: d.stocks || [], macro: d.macro || {}, updated: d.updated || 0 };
  }

  async function fetchTickerAnalysis(symbol) {
    const d = await get('/recommendations/analyze/' + encodeURIComponent(symbol.toUpperCase()));
    return d;
  }

  // ── Energy (EIA) ──────────────────────────────────────────────────────────────
  async function fetchEnergy() {
    const d = await get('/energy');
    return {
      oil:         d.oil         || {},
      gas:         d.gas         || {},
      electricity: d.electricity || {},
      nuclear:     d.nuclear     || {},
      renewables:  d.renewables  || {},
    };
  }

  // ── Earnings Calendar ─────────────────────────────────────────────────────────
  async function fetchEarnings() {
    const d = await get('/earnings');
    return { upcoming: d.upcoming || [], recent: d.recent || [] };
  }

  // ── Price Charts ──────────────────────────────────────────────────────────────
  async function fetchCharts() {
    const d = await get('/charts');
    return { intraday: d.intraday || {}, daily: d.daily || {} };
  }

  // ── Dark Pool ─────────────────────────────────────────────────────────────────
  async function fetchDarkpool() {
    const d = await get('/darkpool');
    return { prints: d.prints || [], ats_vol: d.ats_vol || [] };
  }

  // ── Economic Calendar ─────────────────────────────────────────────────────────
  async function fetchEconCalendar() {
    const d = await get('/econ-calendar');
    return { events: d.events || [] };
  }

  // ── Climate (NOAA CDO) ─────────────────────────────────────────────────────────
  async function fetchClimate() {
    const d = await get('/climate');
    return { stations: d.stations || [] };
  }

  // ── Polygon / massive.com ─────────────────────────────────────────────────────
  async function fetchPolygon() {
    const d = await get('/polygon-data');
    return { bars: d.bars || {}, fundamentals: d.fundamentals || {} };
  }

  // ── CoinMarketCap ─────────────────────────────────────────────────────────────
  async function fetchCmcCoins() {
    const d = await get('/cmc-coins');
    return d.coins || [];
  }

  // ── Ocean / Sea Ice ───────────────────────────────────────────────────────────
  async function fetchOcean() {
    const d = await get('/ocean');
    return {
      arctic:    d.arctic    || { extent: null, date: '', anomaly: null, trend: [] },
      antarctic: d.antarctic || { extent: null, date: '', anomaly: null, trend: [] },
    };
  }

  // ── Trade (World Bank) ────────────────────────────────────────────────────────
  async function fetchTrade() {
    const d = await get('/trade');
    return { countries: d.countries || [] };
  }

  // ── Elections (Wikidata) ──────────────────────────────────────────────────────
  async function fetchElections() {
    const d = await get('/elections');
    return { elections: d.elections || [] };
  }

  // ── Leaks / HIBP ─────────────────────────────────────────────────────────────
  async function fetchLeaks() {
    const d = await get('/leaks');
    return { breaches: d.breaches || [], total_pwned: d.total_pwned || 0, by_class: d.by_class || {} };
  }

  // ── Cloudflare Radar ──────────────────────────────────────────────────────────
  async function fetchCloudflare() {
    const d = await get('/cloudflare');
    return {
      bgp_leaks: d.bgp_leaks || [],
      bgp_stats: d.bgp_stats || {},
    };
  }

  // ── Options Flow ──────────────────────────────────────────────────────────────
  async function fetchOptionsFlow() {
    const d = await get('/options-flow');
    return { unusual: d.unusual || [], summary: d.summary || [] };
  }

  // ── HackerNews ────────────────────────────────────────────────────────────────
  async function fetchHackerNews() {
    const d = await get('/hackernews');
    return { stories: d.stories || [] };
  }

  // ── ClinicalTrials.gov ────────────────────────────────────────────────────────
  async function fetchClinicalTrials() {
    const d = await get('/clinical-trials');
    return { studies: d.studies || [], by_condition: d.by_condition || {}, total: d.total || 0 };
  }

  // ── Full snapshot ─────────────────────────────────────────────────────────────
  async function fetchAll() {
    const settled = await Promise.allSettled([
      fetchMarkets(),      // 0
      fetchCrypto(),       // 1
      fetchAircraft(),     // 2
      fetchShips(),        // 3
      fetchSpace(),        // 4
      fetchWeather(),      // 5
      fetchQuakes(),       // 6
      fetchNews(),         // 7
      fetchParking(),      // 8
      fetchBonds(),        // 9
      fetchForex(),        // 10
      fetchFred(),         // 11
      fetchCve(),          // 12
      fetchLaunches(),     // 13
      fetchConflicts(),    // 14
      fetchSanctions(),    // 15
      fetchNeo(),          // 16
      fetchSpaceWeather(), // 17
      fetchOutages(),      // 18
      fetchPopulation(),          // 19
      fetchEquityFundamentals(),  // 20
      fetchEnergy(),              // 21
      fetchArxiv(),               // 22
      fetchWho(),                 // 23
      fetchUnhcr(),               // 24
      fetchRecommendations(),     // 25
      fetchEdgar(),               // 26
      fetchEarnings(),            // 27
      fetchCharts(),              // 28
      fetchDarkpool(),            // 29
      fetchEconCalendar(),        // 30
      fetchClimate(),             // 31
      fetchPolygon(),             // 32
      fetchCmcCoins(),            // 33
      fetchThreats(),             // 34
      fetchOcean(),               // 35
      fetchTrade(),               // 36
      fetchElections(),           // 37
      fetchLeaks(),               // 38
      fetchCloudflare(),          // 39
      fetchOptionsFlow(),         // 40
      fetchGdelt(),               // 41
      fetchHackerNews(),          // 42
      fetchClinicalTrials(),      // 43
    ]);

    const ok = (i) => settled[i].status === 'fulfilled' && settled[i].value;
    const mkt = ok(0) ? settled[0].value : null;
    return {
      indices:  mkt ? mkt.indices : [],
      tech:     mkt ? mkt.tech    : [],
      macro:    mkt ? mkt.macro   : [],
      crypto:      ok(1)  ? settled[1].value  : [],
      aircraft:    ok(2)  ? settled[2].value  : [],
      ships:       ok(3)  ? settled[3].value  : [],
      space:       ok(4)  ? settled[4].value  : { stations: [], sats: [], starlink_count: 0, active_count: 0 },
      weather:     ok(5)  ? settled[5].value  : [],
      quakes:      ok(6)  ? settled[6].value  : { recent: [], significant: [], largest_today: null, hourly_count: 0, daily_count: 0 },
      news:        ok(7)  ? settled[7].value  : { articles: [], by_category: {}, sources_ok: 0, sources_failed: 0 },
      parking:     ok(8)  ? settled[8].value  : { lots: [], by_city: {}, zones: [] },
      bonds:       ok(9)  ? settled[9].value  : { maturities: [], spread_10y2y: 0 },
      forex:       ok(10) ? settled[10].value : { rates: {} },
      fred:        ok(11) ? settled[11].value : { series: {} },
      cve:         ok(12) ? settled[12].value : { recent: [], kev: [], ransomware: [] },
      launches:    ok(13) ? settled[13].value : { upcoming: [], recent: [] },
      conflicts:   ok(14) ? settled[14].value : { events: [] },
      sanctions:   ok(15) ? settled[15].value : { entries: [], count: 0, programs: [] },
      neo:         ok(16) ? settled[16].value : { objects: [], count: 0 },
      spaceWeather:ok(17) ? settled[17].value : { kp_index: 0, kp_24h: [], solar_wind: {}, x_ray_flux: 0, alerts: [], storm_level: '' },
      outages:     ok(18) ? settled[18].value : { alerts: [], countries: [], bgp: [] },
      population:  ok(19) ? settled[19].value : { countries: [], indicators: {} },
      equityFund:  ok(20) ? settled[20].value : { fundamentals: {} },
      energy:      ok(21) ? settled[21].value : { oil: {}, gas: {}, electricity: {}, nuclear: {}, renewables: {} },
      arxiv:       ok(22) ? settled[22].value : { ai: [], bio: [], quant: [], rob: [], sem: [] },
      who:         ok(23) ? settled[23].value : { by_country: {}, indicators: [] },
      unhcr:       ok(24) ? settled[24].value : { totals: {}, by_origin: [], by_host: [] },
      recommendations: ok(25) ? settled[25].value : { stocks: [], macro: {} },
      edgar:           ok(26) ? settled[26].value : { insider_trades: [], filings_8k: [], filings_10q: [] },
      earnings:        ok(27) ? settled[27].value : { upcoming: [], recent: [] },
      charts:          ok(28) ? settled[28].value : { intraday: {}, daily: {} },
      darkpool:        ok(29) ? settled[29].value : { prints: [], ats_vol: [] },
      econCalendar:    ok(30) ? settled[30].value : { events: [] },
      climate:         ok(31) ? settled[31].value : { stations: [] },
      polygonData:     ok(32) ? settled[32].value : { bars: {}, fundamentals: {} },
      cmcCoins:        ok(33) ? settled[33].value : [],
      threats:         ok(34) ? settled[34].value : { advisories: [] },
      ocean:           ok(35) ? settled[35].value : { arctic: { extent: null, date: '', anomaly: null, trend: [] }, antarctic: { extent: null, date: '', anomaly: null, trend: [] } },
      trade:           ok(36) ? settled[36].value : { countries: [] },
      elections:       ok(37) ? settled[37].value : { elections: [] },
      leaks:           ok(38) ? settled[38].value : { breaches: [], total_pwned: 0, by_class: {} },
      cloudflare:      ok(39) ? settled[39].value : { bgp_leaks: [], bgp_stats: {} },
      optionsFlow:     ok(40) ? settled[40].value : { unusual: [], summary: [] },
      gdelt:           ok(41) ? settled[41].value : { pol: [], ter: [], dip: [] },
      hackernews:      ok(42) ? settled[42].value : { stories: [] },
      clinicalTrials:  ok(43) ? settled[43].value : { studies: [], by_condition: {}, total: 0 },
      ts: Date.now(),
      _live: true,
      _loaded: true,
    };
  }

  // Partial updaters for high-frequency polling
  async function fetchPositions() {
    const [ac, sh] = await Promise.allSettled([fetchAircraft(), fetchShips()]);
    return {
      aircraft: ac.status === 'fulfilled' ? ac.value : null,
      ships:    sh.status === 'fulfilled' ? sh.value : null,
    };
  }

  async function fetchPrices() {
    const [mkt, cry] = await Promise.allSettled([fetchMarkets(), fetchCrypto()]);
    return {
      mkt:    mkt.status === 'fulfilled' ? mkt.value : null,
      crypto: cry.status === 'fulfilled' ? cry.value : null,
    };
  }

  window.DeltaLive = {
    fetchAll, fetchPositions, fetchPrices,
    fetchMarkets, fetchCrypto, fetchAircraft, fetchShips,
    fetchSpace, fetchWeather, fetchQuakes, fetchNews, fetchParking,
    fetchCameras, fetchWildfires,
    fetchBonds, fetchForex, fetchFred, fetchCve, fetchLaunches,
    fetchConflicts, fetchSanctions, fetchNeo, fetchSpaceWeather,
    fetchOutages, fetchPopulation, fetchEquityFundamentals, fetchEnergy,
    fetchArxiv, fetchWho, fetchUnhcr, fetchRecommendations, fetchTickerAnalysis,
    fetchEdgar, fetchEarnings, fetchCharts, fetchDarkpool, fetchEconCalendar, fetchClimate,
    fetchPolygon, fetchCmcCoins,
    fetchOcean, fetchTrade, fetchElections,
    fetchLeaks, fetchCloudflare, fetchOptionsFlow, fetchGdelt, fetchHackerNews, fetchClinicalTrials,
    fetchOptionsMispricing, fetchOptionsMC,
  };
})();
