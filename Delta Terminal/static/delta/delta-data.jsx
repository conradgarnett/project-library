// delta-data.jsx — procedural mock feeds for DELTA Terminal
// Exposes window.DeltaData

(function () {
  // Seeded RNG (mulberry32)
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const pick = (arr, r) => arr[Math.floor(r() * arr.length)];
  const between = (lo, hi, r) => lo + r() * (hi - lo);
  const round = (n, d = 2) => Math.round(n * Math.pow(10, d)) / Math.pow(10, d);
  const fmt = (n, d = 2) =>
    n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmtInt = (n) => (n == null ? '—' : Math.round(n).toLocaleString('en-US'));
  const fmtAbbr = (n) => {
    if (n == null) return '—';
    const a = Math.abs(n);
    if (a >= 1e12) return (n / 1e12).toFixed(2) + 'T';
    if (a >= 1e9)  return (n / 1e9).toFixed(2) + 'B';
    if (a >= 1e6)  return (n / 1e6).toFixed(2) + 'M';
    if (a >= 1e3)  return (n / 1e3).toFixed(2) + 'K';
    return n.toFixed(0);
  };

  // ============== MARKETS ==============
  const EQUITIES = [
    ['^GSPC','S&P 500',5837.12,0.34],['^DJI','Dow Jones',43421.55,0.12],
    ['^IXIC','Nasdaq Composite',18712.40,0.58],['^RUT','Russell 2000',2354.18,-0.42],
    ['^VIX','CBOE Volatility',12.84,-2.10],['^FTSE','FTSE 100',8267.10,0.18],
    ['^N225','Nikkei 225',38762.50,-0.71],['^HSI','Hang Seng',19245.80,1.42],
    ['SPY','SPY ETF',582.34,0.31],['QQQ','Invesco QQQ',498.21,0.62],
    ['IWM','iShares R2K',234.55,-0.41],['GLD','SPDR Gold',252.18,0.22],
    ['TLT','20Y Treasury',92.41,-0.18],['HYG','High Yield',79.84,0.05],
    ['EEM','MSCI EM',45.12,0.78],['XLE','Energy SPDR',88.41,-0.62],
  ];
  const TECH = [
    ['AAPL','Apple Inc',228.31,0.41],['MSFT','Microsoft',421.55,0.62],
    ['NVDA','NVIDIA',141.21,2.18],['GOOGL','Alphabet',171.43,0.31],
    ['META','Meta Platforms',584.12,1.04],['AMZN','Amazon.com',205.84,0.78],
    ['TSLA','Tesla',342.10,-1.41],['AMD','Adv Micro Dev',141.55,1.62],
    ['CRM','Salesforce',332.18,0.41],['ORCL','Oracle',184.55,-0.22],
    ['ADBE','Adobe',512.31,0.18],['NFLX','Netflix',858.42,0.95],
  ];
  const MACRO = [
    ['GC=F','Gold Futures',2682.40,0.18],['CL=F','WTI Crude',69.82,-1.21],
    ['SI=F','Silver',31.45,0.42],['DX-Y.NYB','US Dollar Idx',106.84,0.12],
    ['EURUSD=X','EUR/USD',1.0521,-0.08],['JPY=X','USD/JPY',154.21,0.31],
    ['GBPUSD=X','GBP/USD',1.2651,0.04],['BTC=F','BTC Futures',97842,2.42],
    ['ZN=F','10Y T-Note',109.71,-0.05],['HG=F','Copper',4.21,0.62],
  ];
  const CRYPTO = [
    ['BTCUSDT','Bitcoin',97842.10,2.42],['ETHUSDT','Ethereum',3421.55,1.81],
    ['SOLUSDT','Solana',241.82,3.12],['BNBUSDT','BNB',721.40,0.42],
    ['XRPUSDT','Ripple',2.34,5.21],['ADAUSDT','Cardano',1.04,2.18],
    ['DOGEUSDT','Dogecoin',0.412,4.41],['AVAXUSDT','Avalanche',42.18,1.04],
    ['LINKUSDT','Chainlink',24.55,2.62],['DOTUSDT','Polkadot',8.42,0.82],
    ['MATICUSDT','Polygon',0.521,1.81],['LTCUSDT','Litecoin',108.42,0.62],
  ];

  function buildQuotes(rows, rand) {
    return rows.map(([ticker, name, price, pctSeed]) => {
      const pct = pctSeed + between(-0.08, 0.08, rand);
      const ch = round((price * pct) / 100, 2);
      const px = round(price + between(-price * 0.002, price * 0.002, rand), price > 1000 ? 2 : 4);
      const hi = round(px * (1 + Math.abs(pct) / 100 + between(0, 0.005, rand)), 2);
      const lo = round(px * (1 - Math.abs(pct) / 100 - between(0, 0.005, rand)), 2);
      const vol = Math.floor(between(2e6, 8e7, rand));
      return {
        ticker, name, price: px, change: ch, change_pct: round(pct, 2),
        day_high: hi, day_low: lo, volume: vol,
        arrow: pct >= 0 ? '▲' : '▼', color: pct >= 0 ? 'up' : 'down',
      };
    });
  }

  function buildCrypto(rows, rand) {
    return rows.map(([symbol, name, price, pctSeed]) => {
      const pct = pctSeed + between(-0.2, 0.2, rand);
      const px = price * (1 + between(-0.003, 0.003, rand));
      return {
        symbol, name,
        price: round(px, px < 1 ? 4 : 2),
        change_24h: round((px * pct) / 100, 2),
        change_pct_24h: round(pct, 2),
        high_24h: round(px * (1 + Math.abs(pct) / 100 + 0.004), 2),
        low_24h:  round(px * (1 - Math.abs(pct) / 100 - 0.004), 2),
        volume_24h: Math.floor(between(1e8, 4e10, rand)),
        arrow: pct >= 0 ? '▲' : '▼', color: pct >= 0 ? 'up' : 'down',
      };
    });
  }

  // ============== AIRCRAFT ==============
  const AIRLINES = [
    ['UAL','United States'],['DAL','United States'],['AAL','United States'],
    ['SWA','United States'],['JBU','United States'],
    ['DLH','Germany'],['BAW','United Kingdom'],['AFR','France'],['KLM','Netherlands'],
    ['IBE','Spain'],['ALK','Norway'],['SAS','Sweden'],['THY','Turkey'],
    ['UAE','United Arab Emirates'],['QTR','Qatar'],['ETD','UAE'],['SIA','Singapore'],
    ['CPA','Hong Kong'],['ANA','Japan'],['JAL','Japan'],['QFA','Australia'],
    ['ACA','Canada'],['AMX','Mexico'],['LAN','Chile'],['GLO','Brazil'],
    ['ETH','Ethiopia'],['MSR','Egypt'],['SAA','South Africa'],['ROT','Romania'],
    ['SVR','Russia'],['CCA','China'],['CSN','China'],['CES','China'],['AIC','India'],
  ];
  const COUNTRIES = ['United States','Germany','United Kingdom','France','Japan','China',
    'Brazil','Canada','Australia','Russia','India','South Africa','Mexico','Singapore'];

  // Air traffic hot zones (lat, lon, radius_deg)
  const AIR_ZONES = [
    [40, -95, 25],   // North America
    [50, 10, 20],    // Europe
    [35, 130, 18],   // East Asia
    [25, 80, 16],    // South Asia
    [-25, 135, 18],  // Australia
    [-15, -55, 22],  // South America
    [0, 20, 22],     // Africa
    [25, 50, 14],    // Middle East
    [50, -160, 30],  // Pacific
    [60, -30, 25],   // North Atlantic
  ];

  function genAircraft(n, rand) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const zone = pick(AIR_ZONES, rand);
      const lat = zone[0] + (rand() - 0.5) * 2 * zone[2];
      const lon = zone[1] + (rand() - 0.5) * 2 * zone[2];
      const onGround = rand() < 0.04;
      const al = pick(AIRLINES, rand);
      const cs = al[0] + Math.floor(between(100, 9999, rand));
      const heading = between(0, 360, rand);
      const altFt = onGround ? 0 : Math.floor(between(18000, 42000, rand) / 1000) * 1000;
      const spd = onGround ? Math.floor(between(0, 25, rand)) : Math.floor(between(380, 540, rand));
      const arrows = ['↑','↗','→','↘','↓','↙','←','↖'];
      out.push({
        icao24: (Math.floor(rand() * 0xffffff)).toString(16).padStart(6, '0'),
        callsign: cs,
        country: al[1],
        lat: round(lat, 4),
        lon: round(((lon + 540) % 360) - 180, 4),
        altitude_ft: altFt,
        speed_kts: spd,
        heading: round(heading, 0),
        heading_arrow: arrows[Math.round(heading / 45) % 8],
        fl: onGround ? 'GND' : 'FL' + (altFt / 100).toString().padStart(3, '0'),
        on_ground: onGround,
        vertical_rate: onGround ? 0 : Math.floor(between(-2200, 2200, rand)),
        type: pick(['B738','A320','B77W','A359','A21N','B789','E190','CRJ9','B748','A388'], rand),
      });
    }
    return out;
  }

  // Advance aircraft positions one tick along heading
  function tickAircraft(planes, dt = 1) {
    return planes.map(p => {
      if (p.on_ground) return p;
      // Speed kts × time-step; map ~deg ≈ km/111; we want visible motion but not warp
      const km = (p.speed_kts * 1.852) * (dt / 3600) * 30; // scaled
      const rad = (p.heading - 90) * Math.PI / 180;
      const dLat = (km * Math.sin(-rad)) / 111;
      const dLon = (km * Math.cos(rad)) / (111 * Math.cos(p.lat * Math.PI / 180));
      let lat = p.lat + dLat;
      let lon = p.lon + dLon;
      if (lat > 85) { lat = 85; }
      if (lat < -85) { lat = -85; }
      if (lon > 180) lon -= 360;
      if (lon < -180) lon += 360;
      return { ...p, lat: round(lat, 4), lon: round(lon, 4) };
    });
  }

  // ============== SHIPS ==============
  const VESSEL_NAMES = [
    'EVER GIVEN','MAERSK SAVANNAH','MSC GULSUN','CMA CGM JACQUES','OOCL HONG KONG',
    'COSCO SHIPPING','NORDIC HUNTER','SEASPAN HAMBURG','HMM ALGECIRAS','POLAR ENDEAVOUR',
    'STENA IMPRESSION','AFRAMAX SPIRIT','LNG ENDURANCE','PACIFIC VOYAGER','ATLANTIC PIONEER',
    'NORTH STAR','SOUTHERN CROSS','BLUE HORIZON','SILVER WIND','GOLDEN OSPREY',
    'KOTA NEBULA','EVERGREEN ACE','MARAN GAS','EAGLE SAPPHIRE','SEAVISTA',
    'BALTIC EXPRESS','CAPE ENDEAVOR','OCEAN VICTORY','BERGE STAHL','VALE BRASIL',
  ];
  const FLAGS = ['LR','PA','MH','SG','HK','CN','GR','JP','DE','NO','GB','US','BS','IT','MT'];
  const SHIP_TYPES = [
    [70,'Cargo'],[80,'Tanker'],[60,'Passenger'],[30,'Fishing'],[37,'Pleasure'],
    [52,'Tug'],[50,'Pilot'],[51,'SAR'],[40,'HSC'],[36,'Sailing'],
  ];
  const SHIP_STATUS = [
    [0,'Under way (engine)'],[0,'Under way (engine)'],[0,'Under way (engine)'],
    [1,'At anchor'],[5,'Moored'],[8,'Under way (sailing)'],[7,'Fishing'],
  ];
  // Shipping lane hot spots
  const SEA_ZONES = [
    [30, -75, 14],    // US east coast
    [30, -130, 14],   // US west coast
    [50, 0, 8],       // English channel / north sea
    [36, 14, 10],     // Mediterranean
    [25, 55, 8],      // Persian gulf
    [3, 105, 10],     // Singapore / malacca
    [31, 122, 8],     // Shanghai / Yellow sea
    [35, 140, 8],     // Tokyo bay
    [-34, 18, 6],     // Cape of Good Hope
    [12, 45, 6],      // Bab-el-Mandeb
    [9, -79, 4],      // Panama
    [-23, -45, 8],    // Brazil coast
  ];

  function genShips(n, rand) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const zone = pick(SEA_ZONES, rand);
      const lat = zone[0] + (rand() - 0.5) * 2 * zone[2];
      const lon = zone[1] + (rand() - 0.5) * 2 * zone[2];
      const [code, statusName] = pick(SHIP_STATUS, rand);
      const underway = code === 0 || code === 8;
      const heading = between(0, 360, rand);
      const arrows = ['↑','↗','→','↘','↓','↙','←','↖'];
      const [tcode, tname] = pick(SHIP_TYPES, rand);
      out.push({
        mmsi: String(Math.floor(between(200000000, 799999999, rand))),
        name: pick(VESSEL_NAMES, rand) + ' ' + pick(['I','II','III','IV','V','VII','IX','X','XI'], rand),
        callsign: String.fromCharCode(65 + Math.floor(rand() * 26)) + Math.floor(between(1000, 9999, rand)),
        vessel_type: tcode, type_name: tname,
        lat: round(lat, 4),
        lon: round(((lon + 540) % 360) - 180, 4),
        speed_kts: underway ? round(between(8, 22, rand), 1) : round(between(0, 0.4, rand), 1),
        course: round(heading, 0),
        heading: round(heading, 0),
        heading_arrow: arrows[Math.round(heading / 45) % 8],
        nav_status: code, status_name: statusName,
        destination: pick(['SINGAPORE','ROTTERDAM','SHANGHAI','LOS ANGELES','HAMBURG','ANTWERP','BUSAN','DUBAI','HOUSTON','SANTOS','TOKYO','HONG KONG','NEW YORK'], rand),
        flag: pick(FLAGS, rand),
        dwt: Math.floor(between(8000, 320000, rand)),
      });
    }
    return out;
  }

  function tickShips(ships, dt = 1) {
    return ships.map(s => {
      if (s.speed_kts < 0.5) return s;
      const km = (s.speed_kts * 1.852) * (dt / 3600) * 50;
      const rad = (s.heading - 90) * Math.PI / 180;
      const dLat = (km * Math.sin(-rad)) / 111;
      const dLon = (km * Math.cos(rad)) / (111 * Math.cos(s.lat * Math.PI / 180));
      let lat = s.lat + dLat, lon = s.lon + dLon;
      if (lat > 85) lat = 85; if (lat < -85) lat = -85;
      if (lon > 180) lon -= 360; if (lon < -180) lon += 360;
      return { ...s, lat: round(lat, 4), lon: round(lon, 4) };
    });
  }

  // ============== SPACE ==============
  function genSpace(rand, t) {
    // ISS orbit ~ inclination 51.6°, period 92.6 min — sinusoidal ground track approximation
    const elapsed = t / 1000;
    const issLon = ((elapsed * 0.064) % 360) - 180;
    const issLat = 51.6 * Math.sin((elapsed / 5550) * 2 * Math.PI);
    const tianLon = ((elapsed * 0.062 + 120) % 360) - 180;
    const tianLat = 41.5 * Math.sin((elapsed / 5500) * 2 * Math.PI + 1.2);

    const stations = [
      { name: 'ISS (ZARYA)', norad_id: 25544, lat: round(issLat,2), lon: round(issLon,2),
        altitude_km: 408.3, altitude_mi: 253.6, velocity_kms: 7.66, velocity_mph: 17137,
        visibility: rand() > 0.5 ? 'daylight' : 'eclipsed',
        ground_track: `${Math.abs(issLat).toFixed(2)}°${issLat>=0?'N':'S'} ${Math.abs(issLon).toFixed(2)}°${issLon>=0?'E':'W'}` },
      { name: 'TIANGONG', norad_id: 48274, lat: round(tianLat,2), lon: round(tianLon,2),
        altitude_km: 384.0, altitude_mi: 238.6, velocity_kms: 7.68, velocity_mph: 17182,
        visibility: 'daylight',
        ground_track: `${Math.abs(tianLat).toFixed(2)}°${tianLat>=0?'N':'S'} ${Math.abs(tianLon).toFixed(2)}°${tianLon>=0?'E':'W'}` },
    ];

    const orbits = ['LEO','LEO','LEO','MEO','GEO','HEO'];
    const sats = [];
    const satNames = ['HUBBLE','LANDSAT 9','SENTINEL-2B','TERRA','AQUA','NOAA-20','GPS IIF-12',
      'GALILEO 25','GLONASS 760','GOES-18','METOP-C','SWOT','JWST','JASON-3','CRYOSAT-2',
      'SENTINEL-6','ICESAT-2','TESS','TROPICS-1','CAPSTONE','SPHEREX','DART REMNANT','LUCY'];
    for (const n of satNames) {
      const orbit = pick(orbits, rand);
      const apogee = orbit === 'LEO' ? between(400, 1500, rand) :
                     orbit === 'MEO' ? between(8000, 22000, rand) :
                     orbit === 'GEO' ? 35786 : between(20000, 60000, rand);
      const peri = apogee * (orbit === 'GEO' ? 1 : between(0.7, 0.98, rand));
      sats.push({
        name: n, norad_id: String(Math.floor(between(20000, 60000, rand))), orbit_type: orbit,
        inclination: round(between(0, 98, rand), 2),
        apogee_km: round(apogee, 0), perigee_km: round(peri, 0),
        period_min: round(between(90, 1440, rand), 1),
        eccentricity: round(between(0, 0.01, rand), 4),
      });
    }
    return { stations, sats, starlink_count: 5821, active_count: 8932 };
  }

  // ============== WEATHER ==============
  const CITIES = [
    ['New York', 40.71, -74.00], ['London', 51.50, -0.12],
    ['Tokyo', 35.68, 139.69], ['Singapore', 1.35, 103.82],
    ['Dubai', 25.20, 55.27], ['Sydney', -33.87, 151.21],
    ['Mumbai', 19.07, 72.87], ['São Paulo', -23.55, -46.63],
    ['Lagos', 6.52, 3.38], ['Mexico City', 19.43, -99.13],
    ['Cairo', 30.04, 31.24], ['Moscow', 55.75, 37.62],
    ['Toronto', 43.65, -79.38], ['Berlin', 52.52, 13.40],
    ['Hong Kong', 22.30, 114.18], ['Reykjavik', 64.15, -21.94],
    ['Cape Town', -33.92, 18.42], ['Seoul', 37.57, 126.98],
  ];
  const CONDITIONS = [
    ['Clear', '☀️', false], ['Partly cloudy', '⛅', false], ['Cloudy', '☁️', false],
    ['Light rain', '🌦', true], ['Rain', '🌧', true], ['Thunderstorms', '⛈', true],
    ['Snow', '❄️', false], ['Fog', '🌫', false],
  ];
  function genWeather(rand) {
    return CITIES.map(([city, lat, lon]) => {
      const [cond, icon] = pick(CONDITIONS, rand);
      const tropical = Math.abs(lat) < 23;
      const arctic = Math.abs(lat) > 60;
      const base = tropical ? between(24, 38, rand) : arctic ? between(-22, 4, rand) : between(2, 28, rand);
      const tempC = round(base, 1);
      return {
        city, lat, lon,
        temp_c: tempC, temp_f: round(tempC * 9/5 + 32, 1),
        feels_like_c: round(tempC + between(-2, 2, rand), 1),
        humidity: Math.floor(between(28, 92, rand)),
        wind_speed_kph: round(between(2, 65, rand), 1),
        wind_direction_str: pick(['N','NE','E','SE','S','SW','W','NW'], rand),
        precipitation_mm: cond.includes('rain') || cond.includes('Snow') || cond.includes('Thunder')
          ? round(between(0.4, 14, rand), 1) : 0,
        condition: cond, icon, is_day: rand() > 0.4,
      };
    });
  }

  // ============== EARTHQUAKES ==============
  const QUAKE_PLACES = [
    'Off the east coast of Honshu, Japan','35km SW of Bandar Abbas, Iran','Central Alaska',
    'Aleutian Islands','Off the coast of Northern California','Near Coast of Central Chile',
    'Volcano Region, Hawaii','Vanuatu','Tonga','Solomon Islands','Mindanao, Philippines',
    'Sumatra, Indonesia','Java Region, Indonesia','Crete, Greece','Iceland Region',
    'Reykjanes Peninsula','Puerto Rico Region','60km E of Anchorage, Alaska',
    'Banda Sea','Kermadec Islands','Off the coast of Kamchatka, Russia',
    'Loyalty Islands','Off the coast of Oaxaca, Mexico','Central Italy','Eastern Turkey',
  ];
  // Approximate epicenters tied to places above
  const QUAKE_COORDS = [
    [37.5, 142.5],[27.2, 56.3],[63.1, -148.5],[51.9, -177.5],[40.8, -124.3],[-30.5, -71.7],
    [19.4, -155.6],[-15.5, 167.2],[-19.8, -174.7],[-9.7, 160.1],[7.1, 124.5],[2.5, 96.2],
    [-7.5, 108.2],[35.3, 25.1],[64.2, -19.6],[63.8, -22.5],[18.2, -67.0],[61.3, -149.0],
    [-5.2, 130.0],[-30.0, -178.0],[55.6, 161.5],[-21.2, 168.5],[16.5, -97.2],[42.6, 13.3],
    [38.5, 39.3],
  ];

  function genQuakes(rand, t) {
    const recent = [];
    const significant = [];
    for (let i = 0; i < 28; i++) {
      const idx = i % QUAKE_PLACES.length;
      const mag = round(between(2.5, 4.8, rand), 1);
      const mins = Math.floor(between(1, 60, rand));
      recent.push(buildQuake(idx, mag, mins + 'm', false, rand));
    }
    for (let i = 0; i < 14; i++) {
      const idx = Math.floor(rand() * QUAKE_PLACES.length);
      const mag = round(between(4.8, 7.6, rand), 1);
      const days = Math.floor(between(0, 30, rand));
      const tsu = mag > 6.8 && rand() > 0.5;
      significant.push(buildQuake(idx, mag, days + 'd', tsu, rand));
    }
    significant.sort((a, b) => b.magnitude - a.magnitude);
    return {
      recent, significant,
      hourly_count: recent.length,
      daily_count: 312 + Math.floor(rand() * 40),
      largest_today: significant[0],
    };
  }
  function buildQuake(idx, mag, ago, tsu, rand) {
    const [lat, lon] = QUAKE_COORDS[idx];
    const place = QUAKE_PLACES[idx];
    return {
      event_id: 'us' + Math.floor(rand() * 9e6).toString(36),
      magnitude: mag, magnitude_str: 'M' + mag.toFixed(1), mag_type: 'mww',
      place, lat: lat + (rand() - .5) * 0.5, lon: lon + (rand() - .5) * 0.5,
      depth_km: round(between(2, 600, rand), 1),
      time_ago: ago, felt: Math.floor(between(0, 4200, rand)),
      alert: mag >= 6.5 ? (rand() > 0.5 ? 'orange' : 'yellow') : (mag >= 5.5 ? 'green' : null),
      tsunami: tsu, sig: Math.floor(mag * 100),
    };
  }

  // ============== NEWS ==============
  const NEWS = [
    ['Top','Reuters','Federal Reserve signals patience on rate cuts as inflation gauges hold above target'],
    ['Top','BBC World','Talks reopen as ceasefire framework reaches third draft in Geneva'],
    ['Top','Associated Press','Atlantic storm system gains strength, advisories issued for east coast'],
    ['Markets','Bloomberg-OS','Treasury yields ease after softer-than-expected core PCE print'],
    ['Markets','Financial Times','Big-tech earnings carry the index higher despite weakness in small-caps'],
    ['Markets','Reuters','Brent crude slips below $70 as supply concerns ease in the Middle East'],
    ['Markets','Wall St Journal','Dollar steadies near two-year high as traders eye payrolls Friday'],
    ['Business','Reuters','Major airline orders 110 narrow-body jets in long-haul fleet refresh'],
    ['Business','Financial Times','Container rates spike 18% week-on-week amid Red Sea reroute strain'],
    ['Business','Bloomberg-OS','EV maker cuts prices across Asia-Pacific to defend market share'],
    ['Tech','Ars Technica','New open-source model claims state-of-the-art on long-context retrieval'],
    ['Tech','The Verge','GPU shortages persist into Q1 as data-center buildout outpaces supply'],
    ['Tech','TechCrunch','Storage startup raises $180M Series C led by sovereign wealth fund'],
    ['Space','NASA Newsroom','ISS receives resupply mission; crew rotation scheduled for next window'],
    ['Space','SpaceNews','Heavy-lift launch slips to next month as range coordination continues'],
    ['Space','ESA','New radar satellite delivers first images of polar ice retreat'],
    ['Aviation','Flightradar Blog','Trans-Atlantic re-routing adds 18 minutes average eastbound today'],
    ['Aviation','Aviation Week','Hub closure triggers cascading delays across European network'],
    ['Shipping','Lloyds List','Suez transit volume recovers to pre-disruption levels for the quarter'],
    ['Shipping','TradeWinds','New panamax tanker delivered ahead of schedule from Korean yard'],
    ['Shipping','gCaptain','Major port operator announces $1.2B automation investment program'],
  ];
  function genNews(rand) {
    const ts = Date.now();
    const articles = NEWS.map((row, i) => {
      const mins = Math.floor(between(1, 240, rand));
      return {
        id: 'a' + i,
        category: row[0], source: row[1], title: row[2],
        summary: 'Reporting indicates ongoing developments with implications for global markets and connected sectors. Multiple sources corroborate the underlying data points referenced in this brief synopsis.',
        link: '#',
        published: new Date(ts - mins * 60000).toISOString(),
        time_ago: mins < 60 ? mins + 'm' : Math.floor(mins / 60) + 'h',
      };
    });
    const by_category = {};
    for (const a of articles) { (by_category[a.category] ||= []).push(a); }
    return { articles, by_category, sources_ok: 14, sources_failed: 1 };
  }

  // ============== PARKING ==============
  const PARK_LOTS = [
    // London — TfL
    ['LON','London','GB','Westfield Stratford',    51.5430, -0.0078, 2400, 'garage'],
    ['LON','London','GB','Westfield White City',   51.5074, -0.2210, 4500, 'garage'],
    ['LON','London','GB','Brent Cross Shopping',   51.5760, -0.2240, 6500, 'garage'],
    ['LON','London','GB','Q-Park Park Lane',       51.5076, -0.1521, 750,  'garage'],
    ['LON','London','GB','NCP Knightsbridge',      51.5012, -0.1638, 580,  'garage'],
    ['LON','London','GB','Oxford St West',         51.5152, -0.1530, 240,  'street'],
    ['LON','London','GB','Canary Wharf JubliePl',  51.5050, -0.0190, 2100, 'garage'],
    ['LON','London','GB','London City Airport',    51.5050,  0.0550, 1180, 'garage'],
    // San Francisco — SFMTA
    ['SF','San Francisco','US','Union Square Garage',    37.7880, -122.4076, 985, 'garage'],
    ['SF','San Francisco','US','5th & Mission Garage',   37.7833, -122.4054, 1820,'garage'],
    ['SF','San Francisco','US','Sutter-Stockton',        37.7894, -122.4071, 1865,'garage'],
    ['SF','San Francisco','US','Civic Center',           37.7800, -122.4156, 843, 'garage'],
    ['SF','San Francisco','US','Moscone Center',         37.7847, -122.4012, 730, 'garage'],
    ['SF','San Francisco','US','Performing Arts',        37.7782, -122.4196, 596, 'garage'],
    ['SF','San Francisco','US','Polk-Bush',              37.7920, -122.4203, 350, 'garage'],
    // Birmingham UK
    ['BHM','Birmingham','GB','Bullring Moor St',     52.4783, -1.8927, 1500, 'garage'],
    ['BHM','Birmingham','GB','Mailbox',              52.4767, -1.9012, 875,  'garage'],
    ['BHM','Birmingham','GB','NCP Snow Hill',        52.4847, -1.8951, 411,  'garage'],
    ['BHM','Birmingham','GB','Town Hall',            52.4791, -1.9032, 624,  'garage'],
    // Leeds UK
    ['LDS','Leeds','GB','Trinity',          53.7980, -1.5443, 1000, 'garage'],
    ['LDS','Leeds','GB','Victoria Gate',    53.7971, -1.5384, 800,  'garage'],
    ['LDS','Leeds','GB','Merrion Centre',   53.8014, -1.5436, 1000, 'garage'],
    ['LDS','Leeds','GB','The Light',        53.8004, -1.5454, 575,  'garage'],
    // Köln DE
    ['CGN','Köln','DE','Dom / Hauptbahnhof',     50.9417, 6.9580, 600, 'garage'],
    ['CGN','Köln','DE','Rheinauhafen',           50.9242, 6.9620, 950, 'garage'],
    ['CGN','Köln','DE','Mediapark',              50.9492, 6.9425, 720, 'garage'],
    ['CGN','Köln','DE','Neumarkt-Galerie',       50.9358, 6.9468, 480, 'garage'],
    // Newcastle UK
    ['NCL','Newcastle','GB','Eldon Square',     54.9738, -1.6135, 1240, 'garage'],
    ['NCL','Newcastle','GB','Grainger Town',    54.9700, -1.6150, 410,  'garage'],
    ['NCL','Newcastle','GB','Quayside',         54.9696, -1.6020, 320,  'garage'],
    // Bristol UK
    ['BRS','Bristol','GB','Cabot Circus',       51.4595, -2.5854, 2600, 'garage'],
    ['BRS','Bristol','GB','Trenchard St',       51.4575, -2.5970, 487,  'garage'],
    ['BRS','Bristol','GB','Prince St Bridge',   51.4480, -2.5965, 218,  'garage'],
  ];

  function genParking(rand) {
    const cityMeta = {
      LON: { name: 'London',        source: 'TfL'      },
      SF:  { name: 'San Francisco', source: 'SFMTA'    },
      BHM: { name: 'Birmingham',    source: 'BCC'      },
      LDS: { name: 'Leeds',         source: 'LCC'      },
      CGN: { name: 'Köln',          source: 'Stadtwerke' },
      NCL: { name: 'Newcastle',     source: 'NCC'      },
      BRS: { name: 'Bristol',       source: 'BCC'      },
    };
    const lots = PARK_LOTS.map(([cityCode, city, country, name, lat, lon, total, type]) => {
      const occPct = round(between(18, 99, rand), 1);
      const occupied = Math.floor(total * occPct / 100);
      const free = total - occupied;
      const status = occPct >= 95 ? 'Full' : occPct >= 80 ? 'Busy' : occPct >= 50 ? 'Moderate' : 'Available';
      return {
        id: cityCode + '-' + name.slice(0, 8).replace(/\W/g, '').toUpperCase(),
        name, city, country, city_code: cityCode,
        lat, lon, total, occupied, free, occ_pct: occPct,
        type, status, source: cityMeta[cityCode].source,
      };
    });
    // by_city summary
    const by_city = {};
    for (const l of lots) {
      const c = by_city[l.city_code] ||= { city: l.city, country: l.country, code: l.city_code,
        source: l.source, lots: 0, total: 0, occupied: 0, free: 0 };
      c.lots += 1; c.total += l.total; c.occupied += l.occupied; c.free += l.free;
    }
    Object.values(by_city).forEach(c => { c.occ_pct = round(c.occupied / c.total * 100, 1); });
    return { lots, by_city, zones: lots };  // "zones" kept as alias for back-compat
  }

  // ============== SNAPSHOT BUILDER ==============
  function snapshot(seed = 4242) {
    const rand = rng(seed);
    const t = Date.now();
    return {
      indices: buildQuotes(EQUITIES, rand),
      tech: buildQuotes(TECH, rand),
      macro: buildQuotes(MACRO, rand),
      crypto: buildCrypto(CRYPTO, rand),
      aircraft: genAircraft(420, rand),
      ships: genShips(360, rand),
      space: genSpace(rand, t),
      weather: genWeather(rand),
      quakes: genQuakes(rand, t),
      news: genNews(rand),
      parking: genParking(rand),
      ts: t,
    };
  }

  function nudgeQuotes(rows, rand, intensity = 0.0015) {
    return rows.map(q => {
      const drift = (rand() - 0.5) * 2 * intensity;
      const newPx = round(q.price * (1 + drift), q.price > 1000 ? 2 : 4);
      const ch = round(q.change + (newPx - q.price), 2);
      const pct = round((ch / (q.price - q.change)) * 100, 2);
      return { ...q, price: newPx, change: ch, change_pct: pct, _dir: drift > 0 ? 'up' : 'down' };
    });
  }
  function nudgeCrypto(rows, rand) {
    return rows.map(c => {
      const drift = (rand() - 0.5) * 0.004;
      const px = round(c.price * (1 + drift), c.price < 1 ? 4 : 2);
      const ch = round(px - (c.price - c.change_24h), 2);
      const pct = round((ch / (c.price - c.change_24h)) * 100, 2);
      return { ...c, price: px, change_24h: ch, change_pct_24h: pct, _dir: drift > 0 ? 'up' : 'down' };
    });
  }

  window.DeltaData = {
    snapshot, tickAircraft, tickShips, nudgeQuotes, nudgeCrypto, genSpace,
    fmt, fmtInt, fmtAbbr, round, rng, pick, between, CITIES,
  };
})();
