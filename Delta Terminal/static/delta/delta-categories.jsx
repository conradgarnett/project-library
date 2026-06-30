// delta-categories.jsx — Category + tab metadata, mirrors backend
(function () {
  // Order matches backend's CATEGORIES dict
  const CATEGORIES = [
    { code: 'fin', label: 'FINANCE',     tabs: ['MKT','CRT','ERN','PFL','ALT','EQT','BND','FRX','FRD','OFL','OPT','OF3','CRY','COM','MCR','NEWS','REC','INS'] },
    { code: 'geo', label: 'GEOPOLITICS', tabs: ['WAR','POL','SAN','REF','ELE','DIP','TER','INT'] },
    { code: 'eng', label: 'ENERGY',      tabs: ['OIL','NUC','REN','GAS','ELG','CLI'] },
    { code: 'sec', label: 'CYBER',       tabs: ['CVE','NET','DRK','THR','DAR','LEK','SOC','HAC'] },
    { code: 'sci', label: 'SCIENCE',     tabs: ['SOL','RKT','NEO','FIR','EAR','BIO','OCN','CLM'] },
    { code: 'dem', label: 'DEMOG',       tabs: ['POP','MIG','URB','LBR','HLT','EDU'] },
    { code: 'tec', label: 'TECH',        tabs: ['AI','CLD','SEM','ROB','QNT'] },
    { code: 'sup', label: 'SUPPLY',      tabs: ['SHP','AIR','PRT','TRD','MFG','INV'] },
    { code: 'liv', label: 'LIVE',        tabs: ['ACR','VES','ISS','SAT','WEA','PKG','WLD','TRF'] },
    { code: 'sys', label: 'SYSTEM',      tabs: ['CMD'] },
  ];

  // Display labels (matches backend TAB_NAMES + a couple of additions)
  const TAB_NAMES = {
    // Finance
    MKT:'Markets', CRT:'Charts', ERN:'Earnings', PFL:'Portfolio', ALT:'Alerts',
    EQT:'Equity', BND:'Bonds', FRX:'Forex', FRD:'FRED Macro', OPT:'Mispricing',
    CRY:'Crypto', COM:'Commodities', MCR:'Macro', NEWS:'News', OFL:'Options Flow', OF3:'Order Flow 3D', REC:'AI Picks', INS:'INS - Insider',
    // Geopolitics
    WAR:'Conflict', POL:'Politics', SAN:'Sanctions', REF:'Refugees', ELE:'Elections',
    DIP:'Diplomacy', TER:'Incidents', INT:'Intel',
    // Energy
    OIL:'Oil/Gas', NUC:'Nuclear', REN:'Renewables', GAS:'Nat Gas', ELG:'Power Grid', CLI:'Climate',
    // Cyber
    CVE:'Cyber CVE', NET:'Net Outages', DRK:'Dark Pool', THR:'Threats', DAR:'Dark Web', LEK:'Leaks', SOC:'Social', HAC:'Incident Resp',
    // Science
    SOL:'Space Wx', RKT:'Launches', NEO:'Asteroids', FIR:'Wildfires', EAR:'Earthquakes',
    BIO:'Biosurv', OCN:'Oceans', CLM:'Weather',
    // Demographics
    POP:'Population', MIG:'Migration', URB:'Urban', LBR:'Labor', HLT:'Health', EDU:'Education',
    // Tech
    AI:'AI Index', CLD:'Cloud', SEM:'Semis', ROB:'Robotics', QNT:'Quantum',
    // Supply
    SHP:'Vessels', AIR:'Aircraft', PRT:'Ports', TRD:'Trade', MFG:'Manuf', INV:'Inventory',
    // Live
    ACR:'Aircraft Map', VES:'Vessel Map', SAT:'Satellites', ISS:'ISS', TRF:'Cameras',
    CAM:'Cams', WEA:'Weather', PKG:'Parking', WLD:'World Map',
    // System
    CMD:'Command',
  };

  // Lookup: tab → category code (for highlighting)
  const TAB_TO_CAT = {};
  for (const c of CATEGORIES) for (const t of c.tabs) TAB_TO_CAT[t] = c.code;

  window.DeltaCats = { CATEGORIES, TAB_NAMES, TAB_TO_CAT };
})();
