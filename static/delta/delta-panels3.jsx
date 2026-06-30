// delta-panels3.jsx — OFL, COM, AI, BIO, HLT, MIG, LBR, MFG, URB panels
(function () {
  const { useState, useMemo, useCallback } = React;

  // ── shared primitives (duplicated from panels2 since each file is standalone)
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
  function Filter({ value, onChange, placeholder }) {
    return (
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder || 'filter…'}
        style={{ background: 'var(--bg)', border: '1px solid var(--border-2)', color: 'var(--text)',
          fontFamily: 'var(--mono)', fontSize: 10, padding: '2px 6px', outline: 'none', width: 180 }} />
    );
  }
  function Sortable({ col, active, dir, onClick, children }) {
    return <th onClick={() => onClick(col)} style={{ cursor: 'pointer' }}>{children}{active ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}</th>;
  }
  function useSort(items, defaultCol, defaultDir = 'desc') {
    const [col, setCol] = useState(defaultCol);
    const [dir, setDir] = useState(defaultDir);
    const toggle = useCallback((c) => {
      if (c === col) setDir(d => d === 'asc' ? 'desc' : 'asc');
      else { setCol(c); setDir('desc'); }
    }, [col]);
    const sorted = useMemo(() => {
      if (!items || !items.length) return [];
      return [...items].sort((a, b) => {
        const av = a[col], bv = b[col];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv;
        return dir === 'asc' ? cmp : -cmp;
      });
    }, [items, col, dir]);
    return { sorted, col, dir, toggle };
  }

  // ── OFL — Unusual Options Flow ───────────────────────────────────────────────
  function OptionsFlowPanel({ snap }) {
    const ofl = snap.optionsFlow || { unusual: [], summary: [] };
    const rows = ofl.unusual || [];
    const [filter, setFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('ALL');
    const { sorted, col, dir, toggle } = useSort(rows, 'premium_k', 'desc');

    const filtered = useMemo(() => {
      let r = sorted;
      if (typeFilter !== 'ALL') r = r.filter(x => x.type === typeFilter);
      if (filter) r = r.filter(x => x.ticker.includes(filter.toUpperCase()));
      return r;
    }, [sorted, filter, typeFilter]);

    const fmtK = (v) => v >= 1000 ? '$' + (v / 1000).toFixed(1) + 'M' : '$' + Math.round(v) + 'K';

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="UNUSUAL OPTIONS FLOW" meta={`${filtered.length} CONTRACTS`}
            right={
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {['ALL','C','P'].map(t => (
                  <button key={t} className={`btn${typeFilter===t?' on':''}`}
                    onClick={() => setTypeFilter(t)} style={{ padding: '1px 6px', fontSize: 10 }}>
                    {t === 'C' ? 'CALLS' : t === 'P' ? 'PUTS' : 'ALL'}
                  </button>
                ))}
                <Filter value={filter} onChange={setFilter} placeholder="ticker…" />
              </div>
            } />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <Sortable col="ticker" active={col==='ticker'} dir={dir} onClick={toggle}>TICKER</Sortable>
                  <th>TYPE</th>
                  <Sortable col="strike" active={col==='strike'} dir={dir} onClick={toggle}>STRIKE</Sortable>
                  <th>EXPIRY</th>
                  <Sortable col="volume" active={col==='volume'} dir={dir} onClick={toggle}>VOLUME</Sortable>
                  <Sortable col="open_int" active={col==='open_int'} dir={dir} onClick={toggle}>OI</Sortable>
                  <Sortable col="vol_oi" active={col==='vol_oi'} dir={dir} onClick={toggle}>VOL/OI</Sortable>
                  <Sortable col="iv_pct" active={col==='iv_pct'} dir={dir} onClick={toggle}>IV%</Sortable>
                  <Sortable col="premium_k" active={col==='premium_k'} dir={dir} onClick={toggle}>PREMIUM</Sortable>
                  <th>ITM</th>
                </tr></thead>
                <tbody>
                  {filtered.slice(0, 150).map((r, i) => (
                    <tr key={i}>
                      <td className="lbl" style={{ fontWeight: 700 }}>{r.ticker}</td>
                      <td style={{ color: r.type === 'C' ? 'var(--mint)' : 'var(--rose)', fontWeight: 700 }}>{r.type === 'C' ? 'CALL' : 'PUT'}</td>
                      <td className="num">${r.strike?.toFixed(0)}</td>
                      <td className="mut" style={{ fontSize: 10 }}>{r.expiry}</td>
                      <td className="num">{(r.volume||0).toLocaleString()}</td>
                      <td className="num">{(r.open_int||0).toLocaleString()}</td>
                      <td className={`num ${r.vol_oi > 10 ? 'warn' : ''}`}>{r.vol_oi?.toFixed(1)}x</td>
                      <td className="num">{r.iv_pct?.toFixed(1)}%</td>
                      <td className="num warn">{fmtK(r.premium_k || 0)}</td>
                      <td style={{ color: r.itm ? 'var(--mint)' : 'var(--muted)', fontSize: 10 }}>{r.itm ? 'ITM' : 'OTM'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: Yahoo Finance options chains · Sorted by premium · Vol/OI {'>'} 5x flags unusual activity
          </div>
        </div>
      </div>
    );
  }

  // ── COM — Commodities ────────────────────────────────────────────────────────
  const COMMODITY_TICKERS = [
    'GC=F','SI=F','HG=F','CL=F','BZ=F','NG=F','ZN=F',
    'ZC=F','ZW=F','ZS=F','CC=F','KC=F','CT=F','SB=F',
  ];
  const COMMODITY_NAMES = {
    'GC=F':'Gold','SI=F':'Silver','HG=F':'Copper','CL=F':'WTI Crude',
    'BZ=F':'Brent Crude','NG=F':'Natural Gas','ZN=F':'10Y T-Note',
    'ZC=F':'Corn','ZW=F':'Wheat','ZS=F':'Soybeans',
    'CC=F':'Cocoa','KC=F':'Coffee','CT=F':'Cotton','SB=F':'Sugar',
  };
  const COMMODITY_UNITS = {
    'GC=F':'$/oz','SI=F':'$/oz','HG=F':'$/lb','CL=F':'$/bbl',
    'BZ=F':'$/bbl','NG=F':'$/MMBtu','ZN=F':'pts',
    'ZC=F':'¢/bu','ZW=F':'¢/bu','ZS=F':'¢/bu',
    'CC=F':'$/ton','KC=F':'¢/lb','CT=F':'¢/lb','SB=F':'¢/lb',
  };
  const COMMODITY_GROUPS = {
    'Energy':   ['CL=F','BZ=F','NG=F'],
    'Metals':   ['GC=F','SI=F','HG=F'],
    'Grains':   ['ZC=F','ZW=F','ZS=F'],
    'Softs':    ['CC=F','KC=F','CT=F','SB=F'],
    'Rates':    ['ZN=F'],
  };

  function CommoditiesPanel({ snap }) {
    const all = [...(snap.macro || []), ...(snap.indices || []), ...(snap.tech || [])];
    const byTicker = {};
    for (const q of all) byTicker[q.ticker] = q;

    const rows = COMMODITY_TICKERS.map(t => ({
      ticker: t,
      name: COMMODITY_NAMES[t] || t,
      unit: COMMODITY_UNITS[t] || '',
      quote: byTicker[t] || null,
    })).filter(r => r.quote);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {Object.entries(COMMODITY_GROUPS).map(([group, tickers]) => {
          const groupRows = rows.filter(r => tickers.includes(r.ticker));
          if (!groupRows.length) return null;
          return (
            <div key={group} className="panel">
              <PH title={group.toUpperCase()} />
              <table className="dense">
                <thead><tr><th>NAME</th><th className="num">PRICE</th><th className="num">CHG</th><th className="num">CHG%</th><th>UNIT</th></tr></thead>
                <tbody>
                  {groupRows.map(r => {
                    const q = r.quote;
                    const up = (q.change_pct || q.change) >= 0;
                    return (
                      <tr key={r.ticker}>
                        <td className="lbl">{r.name}</td>
                        <td className="num" style={{ fontWeight: 700 }}>{q.price?.toFixed(2)}</td>
                        <td className={`num ${up ? 'up' : 'down'}`}>{up ? '+' : ''}{q.change?.toFixed(2)}</td>
                        <td className={`num ${up ? 'up' : 'down'}`}>{up ? '+' : ''}{q.change_pct?.toFixed(2)}%</td>
                        <td className="mut" style={{ fontSize: 9 }}>{r.unit}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
        {rows.length === 0 && <Empty msg="Loading commodities…" />}
      </div>
    );
  }

  // ── AI — arXiv Papers ────────────────────────────────────────────────────────
  function ArxivPanel({ snap, defaultTab = 'ai' }) {
    const ax = snap.arxiv || { ai: [], bio: [], quant: [], rob: [], sem: [] };
    const [tab, setTab] = useState(defaultTab);
    const [filter, setFilter] = useState('');
    const papers = ax[tab] || [];

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      if (!f) return papers;
      return papers.filter(p => p.title.toLowerCase().includes(f) || (p.authors||[]).join(' ').toLowerCase().includes(f));
    }, [papers, filter]);

    const [sel, setSel] = useState(null);
    const selected = sel !== null ? filtered[sel] : null;

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', gap: 6 }}>
        <div className="panel" style={{ flex: 2, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="ARXIV PREPRINTS"
            meta={`${filtered.length} PAPERS`}
            right={
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {[['ai','AI/ML'],['bio','BIO'],['quant','QUANT'],['rob','ROBOTICS'],['sem','SEMIS']].map(([k,l]) => (
                  <button key={k} className={`btn${tab===k?' on':''}`}
                    onClick={() => { setTab(k); setSel(null); }} style={{ padding: '1px 8px', fontSize: 10 }}>{l}</button>
                ))}
                <Filter value={filter} onChange={v => { setFilter(v); setSel(null); }} placeholder="search…" />
              </div>
            } />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : filtered.slice(0, 100).map((p, i) => (
              <div key={p.arxiv_id} onClick={() => setSel(i === sel ? null : i)}
                style={{ padding: '8px 10px', borderBottom: '1px solid var(--border)',
                  background: sel === i ? 'rgba(56,189,248,.08)' : 'transparent', cursor: 'pointer' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--cyan)', marginBottom: 2, lineHeight: 1.3 }}>
                  {p.title}
                </div>
                <div style={{ fontSize: 10, color: 'var(--muted)' }}>
                  {(p.authors||[]).slice(0,3).join(', ')}{p.authors?.length > 3 ? ' et al.' : ''}
                  <span style={{ marginLeft: 8, color: 'var(--dim)' }}>{p.published}</span>
                </div>
              </div>
            ))}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: arXiv.org · Free preprint server · Updated every 6 hours
          </div>
        </div>
        {selected && (
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PH title="ABSTRACT" right={
              <span className="mut" style={{ fontSize: 9 }}>{selected.arxiv_id}</span>
            } />
            <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 11, color: 'var(--cyan)', marginBottom: 8, lineHeight: 1.4 }}>
                {selected.title}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-2)', marginBottom: 8 }}>
                {(selected.authors||[]).join(', ')}
              </div>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 8 }}>
                {selected.published}
                {(selected.categories||[]).slice(0,4).map(c => (
                  <span key={c} className="pill" style={{ marginLeft: 4, fontSize: 9 }}>{c}</span>
                ))}
              </div>
              <div style={{ fontSize: 10, lineHeight: 1.6, color: 'var(--text)' }}>
                {selected.summary}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── HLT — WHO Global Health + ClinicalTrials ─────────────────────────────────
  function HealthPanel({ snap }) {
    const [mainTab, setMainTab] = useState('who');
    const who = snap.who || { by_country: {}, indicators: [] };
    const ct  = snap.clinicalTrials || { studies: [], by_condition: {}, total: 0 };
    const [filter, setFilter] = useState('');
    const [selInd, setSelInd] = useState('WHOSIS_000001');

    const COUNTRY_NAMES = {};  // fallback — will show ISO codes

    const indMeta = who.indicators.find(i => i.code === selInd) || { label: selInd, unit: '' };

    const rows = useMemo(() => {
      return Object.entries(who.by_country)
        .map(([iso, data]) => ({ iso, value: data[selInd] }))
        .filter(r => r.value != null)
        .sort((a, b) => b.value - a.value);
    }, [who.by_country, selInd]);

    const filtered = useMemo(() => {
      const f = filter.toUpperCase();
      if (!f) return rows;
      return rows.filter(r => r.iso.includes(f));
    }, [rows, filter]);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Main tab bar */}
        <div style={{ display: 'flex', gap: 0, flexShrink: 0 }}>
          {[['who','WHO GHO'],['trials','CLINICAL TRIALS']].map(([code, label]) => (
            <button key={code} className={`btn${mainTab===code?' on':''}`}
              onClick={() => setMainTab(code)}
              style={{ fontSize: 10, padding: '3px 14px' }}>{label}</button>
          ))}
          {mainTab === 'trials' && ct.total > 0 && (
            <span style={{ marginLeft: 8, fontSize: 9, color: 'var(--muted)', alignSelf: 'center' }}>
              {ct.total} RECRUITING
            </span>
          )}
        </div>

        {mainTab === 'who' && (
          <div style={{ flex: 1, display: 'flex', gap: 6, minHeight: 0 }}>
            <div style={{ width: 200, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div className="panel" style={{ flex: 1, overflow: 'auto' }}>
                <PH title="INDICATORS" />
                {who.indicators.map(ind => (
                  <div key={ind.code} onClick={() => setSelInd(ind.code)}
                    style={{ padding: '6px 10px', borderBottom: '1px solid var(--border)',
                      background: selInd === ind.code ? 'rgba(56,189,248,.08)' : 'transparent',
                      cursor: 'pointer', fontSize: 10 }}>
                    <div style={{ color: selInd === ind.code ? 'var(--cyan)' : 'var(--text)', fontWeight: selInd === ind.code ? 700 : 400 }}>
                      {ind.label}
                    </div>
                    <div className="mut" style={{ fontSize: 9 }}>{ind.unit}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <PH title={`${indMeta.label} BY COUNTRY`.toUpperCase()}
                meta={`${filtered.length} COUNTRIES`}
                right={<Filter value={filter} onChange={setFilter} placeholder="ISO code…" />} />
              <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
                {filtered.length === 0 ? <Empty /> : (
                  <table className="dense">
                    <thead><tr><th>#</th><th>COUNTRY</th><th className="num">{indMeta.label.toUpperCase()} ({indMeta.unit})</th></tr></thead>
                    <tbody>
                      {filtered.slice(0, 200).map((r, i) => (
                        <tr key={r.iso}>
                          <td className="mut" style={{ fontSize: 9, width: 30 }}>{i + 1}</td>
                          <td className="lbl">{r.iso}</td>
                          <td className="num" style={{ fontWeight: 600 }}>{r.value?.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
                Source: WHO Global Health Observatory · Free API · Latest available year
              </div>
            </div>
          </div>
        )}

        {mainTab === 'trials' && (
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PH title="CLINICAL TRIALS · ACTIVELY RECRUITING"
              meta={`${ct.studies.length} SHOWN`}
              right={<Filter value={filter} onChange={f => setFilter(f)} placeholder="condition, sponsor…" />}
            />
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {ct.studies.length === 0 ? <Empty msg="Loading ClinicalTrials.gov data…" /> : (() => {
                const f = filter.toLowerCase();
                const rows = f
                  ? ct.studies.filter(s =>
                      s.title.toLowerCase().includes(f) ||
                      (s.conditions || []).some(c => c.toLowerCase().includes(f)) ||
                      s.sponsor.toLowerCase().includes(f)
                    )
                  : ct.studies;
                return (
                  <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead><tr>
                      <th style={{ width: 100 }}>NCT ID</th>
                      <th>TITLE</th>
                      <th style={{ width: 80 }}>CONDITION</th>
                      <th style={{ width: 60 }}>PHASE</th>
                      <th style={{ width: 140 }}>SPONSOR</th>
                      <th style={{ width: 80 }}>UPDATED</th>
                    </tr></thead>
                    <tbody>
                      {rows.map(s => (
                        <tr key={s.nct_id}>
                          <td>
                            <a href={s.url} target="_blank" rel="noopener noreferrer"
                              style={{ color: 'var(--cyan)', textDecoration: 'none', fontSize: 10 }}>
                              {s.nct_id}
                            </a>
                          </td>
                          <td style={{ fontSize: 10, color: 'var(--text)', maxWidth: 0 }}>
                            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {s.title}
                            </div>
                          </td>
                          <td style={{ fontSize: 9, color: 'var(--text-2)' }}>{(s.conditions || [])[0] || '—'}</td>
                          <td><span className="pill" style={{ fontSize: 9 }}>{s.phase_label}</span></td>
                          <td style={{ fontSize: 9, color: 'var(--muted)' }}>{s.sponsor.slice(0,25)}</td>
                          <td style={{ fontSize: 9, color: 'var(--muted)' }}>{s.updated}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
            </div>
            <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
              ClinicalTrials.gov API v2 · Actively recruiting studies · Free, no auth · Updated hourly
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── MIG — UNHCR Forced Displacement ─────────────────────────────────────────
  function MigrationPanel({ snap }) {
    const unhcr = snap.unhcr || { totals: {}, by_origin: [], by_host: [] };
    const [tab, setTab] = useState('origin');
    const rows = tab === 'origin' ? unhcr.by_origin : unhcr.by_host;
    const [filter, setFilter] = useState('');

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      if (!f) return rows;
      return rows.filter(r => r.country.toLowerCase().includes(f));
    }, [rows, filter]);

    const fmt = (n) => {
      if (!n) return '—';
      if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
      if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
      return n.toLocaleString();
    };

    const t = unhcr.totals || {};

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            ['refugees',       'REFUGEES'],
            ['asylum_seekers', 'ASYLUM SEEKERS'],
            ['idps',           'IDPS'],
            ['stateless',      'STATELESS'],
          ].map(([k, l]) => (
            <div key={k} className="panel" style={{ flex: 1, padding: '8px 12px' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 2 }}>{l}</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--cyan)' }}>{fmt(t[k])}</div>
            </div>
          ))}
        </div>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="FORCED DISPLACEMENT" meta={`${filtered.length} COUNTRIES`}
            right={
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {[['origin','BY ORIGIN'],['host','BY HOST']].map(([k,l]) => (
                  <button key={k} className={`btn${tab===k?' on':''}`}
                    onClick={() => setTab(k)} style={{ padding: '1px 8px', fontSize: 10 }}>{l}</button>
                ))}
                <Filter value={filter} onChange={setFilter} placeholder="country…" />
              </div>
            } />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>COUNTRY</th>
                  <th className="num">REFUGEES</th>
                  <th className="num">ASYLUM</th>
                  <th className="num">IDPS</th>
                  <th className="num">STATELESS</th>
                  <th>YEAR</th>
                </tr></thead>
                <tbody>
                  {filtered.slice(0, 100).map((r, i) => (
                    <tr key={i}>
                      <td className="lbl">{r.country}</td>
                      <td className="num">{fmt(r.refugees)}</td>
                      <td className="num">{fmt(r.asylum)}</td>
                      <td className="num">{fmt(r.idps)}</td>
                      <td className="num">{fmt(r.stateless)}</td>
                      <td className="mut" style={{ fontSize: 9 }}>{r.year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: UNHCR Global Trends · Free API · Annual data
          </div>
        </div>
      </div>
    );
  }

  // ── LBR — Labor Markets (FRED) ──────────────────────────────────────────────
  const LABOR_SERIES = {
    'UNRATE':    { label: 'Unemployment Rate',          unit: '%' },
    'MANEMP':    { label: 'Manufacturing Employment',   unit: 'K persons' },
    'PAYEMS':    { label: 'Nonfarm Payrolls',           unit: 'K persons' },
    'CIVPART':   { label: 'Labor Force Participation',  unit: '%' },
    'LNS14000006': { label: 'Youth Unemployment (16-24)', unit: '%' },
  };

  function LaborPanel({ snap }) {
    const fred = snap.fred || { series: {} };
    const pop  = snap.population || { countries: [] };

    const globalUnemp = useMemo(() => {
      return pop.countries
        .filter(c => c.unemp != null && c.pop > 5000000)
        .sort((a, b) => b.unemp - a.unemp)
        .slice(0, 20);
    }, [pop.countries]);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', gap: 6 }}>
        <div className="panel" style={{ width: 280, display: 'flex', flexDirection: 'column' }}>
          <PH title="US LABOR (FRED)" right={<span className="pill pill-cyan">● FRED</span>} />
          {Object.entries(LABOR_SERIES).map(([code, meta]) => {
            const s = fred.series[code];
            const val = s?.observations?.slice(-1)[0]?.value;
            const prev = s?.observations?.slice(-2)[0]?.value;
            const up = val != null && prev != null ? val >= prev : null;
            return (
              <div key={code} style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
                <div className="mut" style={{ fontSize: 9 }}>{meta.label}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--cyan)' }}>
                    {val != null ? Number(val).toLocaleString() : '—'}
                  </span>
                  <span className="dim" style={{ fontSize: 9 }}>{meta.unit}</span>
                  {up !== null && <span className={up ? 'up' : 'down'} style={{ fontSize: 11 }}>{up ? '▲' : '▼'}</span>}
                </div>
              </div>
            );
          })}
          <div style={{ flex: 1 }} />
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: Federal Reserve (FRED)
          </div>
        </div>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="UNEMPLOYMENT BY COUNTRY (WORLD BANK)" meta={`${globalUnemp.length} COUNTRIES`} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {globalUnemp.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr><th>COUNTRY</th><th className="num">UNEMP %</th><th className="num">POPULATION</th></tr></thead>
                <tbody>
                  {globalUnemp.map((c, i) => (
                    <tr key={c.code}>
                      <td className="lbl">{c.country}</td>
                      <td className="num" style={{ color: c.unemp > 10 ? 'var(--rose)' : c.unemp < 4 ? 'var(--mint)' : 'var(--text)' }}>
                        {c.unemp.toFixed(1)}%
                      </td>
                      <td className="num mut">{c.pop >= 1e9 ? (c.pop/1e9).toFixed(1)+'B' : (c.pop/1e6).toFixed(0)+'M'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: World Bank
          </div>
        </div>
      </div>
    );
  }

  // ── MFG — Manufacturing (FRED) ───────────────────────────────────────────────
  // fred.series is keyed by display name (e.g. "Mfg Employment"), not series ID
  const MFG_SERIES = {
    'Mfg Employment':  { label: 'Manufacturing Employment', unit: 'K persons', code: 'MANEMP' },
    'Industrial Prod': { label: 'Industrial Production',    unit: 'index',     code: 'IPMAN' },
    'Mfg New Orders':  { label: 'Mfg New Orders',          unit: '$M',        code: 'AMTMNO' },
    'Trade Balance':   { label: 'Trade Balance',           unit: '$B',        code: 'BOPGSTB' },
    'Retail Sales MoM':{ label: 'Retail Sales',            unit: '$M',        code: 'RSXFS' },
  };

  function ManufacturingPanel({ snap }) {
    const fred = snap.fred || { series: {} };

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <PH title="US MANUFACTURING & TRADE (FRED)" right={<span className="pill pill-cyan">● FRED</span>} />
          {Object.entries(MFG_SERIES).map(([name, meta]) => {
            const s    = fred.series[name];
            const val  = s?.value;
            const prev = s?.prev;
            const chg  = val != null && prev != null && prev !== 0 ? ((val - prev) / Math.abs(prev) * 100) : null;
            const up   = chg != null ? chg >= 0 : null;
            return (
              <div key={name} style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)' }}>{meta.label}</div>
                  <div className="mut" style={{ fontSize: 9 }}>{meta.code} · {meta.unit} · {s?.date || '—'}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--cyan)', fontVariantNumeric: 'tabular-nums' }}>
                    {val != null ? Number(val).toLocaleString() : '—'}
                  </div>
                  {chg != null && (
                    <div className={`${up ? 'up' : 'down'}`} style={{ fontSize: 10 }}>
                      {up ? '▲' : '▼'} {Math.abs(chg).toFixed(2)}% MoM
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div style={{ flex: 1 }} />
          <div style={{ padding: '4px 8px', fontSize: 9, color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
            Source: Federal Reserve Economic Data (FRED) · St. Louis Fed
          </div>
        </div>
      </div>
    );
  }

  // ── URB — Urbanization (World Bank) ─────────────────────────────────────────
  function UrbanPanel({ snap }) {
    const pop = snap.population || { countries: [] };
    const [filter, setFilter] = useState('');

    const rows = useMemo(() => {
      return pop.countries
        .filter(c => c.urban_pct != null && c.pop > 1000000)
        .sort((a, b) => b.urban_pct - a.urban_pct);
    }, [pop.countries]);

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      if (!f) return rows;
      return rows.filter(r => r.country.toLowerCase().includes(f));
    }, [rows, filter]);

    const avgUrban = rows.length ? (rows.reduce((s, r) => s + r.urban_pct, 0) / rows.length).toFixed(1) : '—';

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            ['World Avg Urban', avgUrban + '%'],
            ['Most Urban', rows[0] ? rows[0].country + ' ' + rows[0].urban_pct?.toFixed(1) + '%' : '—'],
            ['Least Urban', rows.at(-1) ? rows.at(-1).country + ' ' + rows.at(-1).urban_pct?.toFixed(1) + '%' : '—'],
          ].map(([l, v]) => (
            <div key={l} className="panel" style={{ flex: 1, padding: '8px 12px' }}>
              <div className="mut" style={{ fontSize: 9 }}>{l}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--cyan)' }}>{v}</div>
            </div>
          ))}
        </div>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="URBANIZATION BY COUNTRY (WORLD BANK)"
            meta={`${filtered.length} COUNTRIES`}
            right={<Filter value={filter} onChange={setFilter} placeholder="search country…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty /> : (
              <table className="dense">
                <thead><tr>
                  <th>COUNTRY</th>
                  <th className="num">URBAN %</th>
                  <th className="num">POPULATION</th>
                  <th className="num">GDP/CAPITA</th>
                  <th className="num">LIFE EXP</th>
                </tr></thead>
                <tbody>
                  {filtered.slice(0, 200).map((c) => {
                    const bar = c.urban_pct / 100;
                    return (
                      <tr key={c.code}>
                        <td className="lbl">{c.country}</td>
                        <td className="num">
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}>
                            <div style={{ width: 40, height: 4, background: 'var(--surface-2)', borderRadius: 2 }}>
                              <div style={{ width: (bar * 100) + '%', height: '100%', background: 'var(--cyan)', borderRadius: 2 }} />
                            </div>
                            {c.urban_pct.toFixed(1)}%
                          </div>
                        </td>
                        <td className="num mut">{c.pop >= 1e9 ? (c.pop/1e9).toFixed(1)+'B' : (c.pop/1e6).toFixed(0)+'M'}</td>
                        <td className="num">{c.gdp_pc ? '$' + Math.round(c.gdp_pc).toLocaleString() : '—'}</td>
                        <td className="num">{c.life_exp ? c.life_exp.toFixed(1) : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: World Bank Open Data · Free API
          </div>
        </div>
      </div>
    );
  }

  // ── EDU — Education (World Bank) ─────────────────────────────────────────────
  function EducationPanel({ snap }) {
    const pop = snap.population || { countries: [] };
    const [metric, setMetric] = useState('literacy');
    const [filter, setFilter] = useState('');
    const fl = filter.toLowerCase();

    const METRICS = [
      { key: 'literacy',   label: 'Adult Literacy %',     unit: '%' },
      { key: 'enroll_pri', label: 'Primary Enrollment %', unit: '%' },
      { key: 'enroll_sec', label: 'Secondary Enrollment %', unit: '%' },
      { key: 'enroll_ter', label: 'Tertiary Enrollment %', unit: '%' },
      { key: 'edu_spend',  label: 'Education Spend % GDP', unit: '% GDP' },
    ];

    const rows = useMemo(() => {
      return pop.countries
        .filter(c => c[metric] != null && c.pop > 500000)
        .sort((a, b) => (b[metric] || 0) - (a[metric] || 0));
    }, [pop.countries, metric]);

    const filtered = rows.filter(c =>
      !fl || c.country.toLowerCase().includes(fl) || c.code.toLowerCase().includes(fl)
    );

    const meta = METRICS.find(m => m.key === metric);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ padding: '6px 10px', display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0, flexWrap: 'wrap' }}>
          <span style={{ color: 'var(--cyan)', fontSize: 11, letterSpacing: '.1em', fontWeight: 700 }}>◆ EDUCATION</span>
          {METRICS.map(m => (
            <button key={m.key} onClick={() => setMetric(m.key)}
              style={{ padding: '2px 8px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
                border: '1px solid', letterSpacing: '.06em',
                borderColor: metric === m.key ? 'var(--cyan)' : 'var(--border-2)',
                background: metric === m.key ? 'rgba(56,189,248,.12)' : 'transparent',
                color: metric === m.key ? 'var(--cyan)' : 'var(--text-2)' }}>
              {m.label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <Filter value={filter} onChange={setFilter} placeholder="country…" />
        </div>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title={`${meta?.label?.toUpperCase()} BY COUNTRY`}
            meta={`${filtered.length} COUNTRIES · World Bank`} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg="Loading education data… (World Bank, updates daily)" /> : (
              <table className="dense">
                <thead><tr>
                  <th style={{ width: 28 }}>#</th>
                  <th>COUNTRY</th>
                  <th className="num">{meta?.unit}</th>
                  <th className="num">BAR</th>
                  <th className="num">POPULATION</th>
                </tr></thead>
                <tbody>
                  {filtered.slice(0, 150).map((c, i) => {
                    const val = c[metric];
                    const pct = Math.min(val || 0, 120);
                    return (
                      <tr key={c.code}>
                        <td className="mut" style={{ fontSize: 9 }}>{i + 1}</td>
                        <td style={{ fontWeight: 600 }}>{c.country}</td>
                        <td className="num" style={{ color: 'var(--cyan)', fontWeight: 600 }}>
                          {val != null ? val.toFixed(1) : '—'}
                        </td>
                        <td style={{ width: 80 }}>
                          <div style={{ height: 6, background: 'var(--surface-2)', borderRadius: 2 }}>
                            <div style={{ width: Math.min(pct, 100) + '%', height: '100%',
                              background: pct >= 90 ? 'var(--mint)' : pct >= 60 ? 'var(--cyan)' : 'var(--amber)',
                              borderRadius: 2 }} />
                          </div>
                        </td>
                        <td className="num mut" style={{ fontSize: 9 }}>
                          {c.pop ? (c.pop / 1e6).toFixed(1) + 'M' : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: World Bank Open Data · SE series indicators · Updated annually
          </div>
        </div>
      </div>
    );
  }

  // ── REC — helpers ────────────────────────────────────────────────────────────
  const { useRef } = React;

  // ── REC — AI Stock Recommendations ──────────────────────────────────────────
  const SIGNAL_COLOR = {
    'STRONG BUY': 'var(--mint)',
    'BUY':        'var(--cyan)',
    'HOLD':       'var(--amber)',
    'REDUCE':     'var(--orange, #f97316)',
    'AVOID':      'var(--rose)',
  };
  const SIGNAL_BG = {
    'STRONG BUY': 'rgba(52,211,153,.12)',
    'BUY':        'rgba(56,189,248,.10)',
    'HOLD':       'rgba(251,191,36,.10)',
    'REDUCE':     'rgba(249,115,22,.10)',
    'AVOID':      'rgba(251,113,133,.10)',
  };

  const RATING_COLOR = { BUY: 'var(--mint)', HOLD: 'var(--amber)', SELL: 'var(--rose)' };
  const RATING_BG    = { BUY: 'rgba(52,211,153,.12)', HOLD: 'rgba(251,191,36,.12)', SELL: 'rgba(251,113,133,.12)' };

  // Compact detail pane for table-row clicks (no narrative)
  function StockDetailCompact({ s, onClose }) {
    if (!s) return null;
    const fmtPct = v => v == null ? '—' : (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%';
    const fmtK   = v => !v ? '—' : v >= 1000 ? '$' + (v/1000).toFixed(1) + 'M' : '$' + Math.round(v) + 'K';
    const sc = SIGNAL_COLOR[s.signal] || 'var(--text)';
    return (
      <div className="panel" style={{ width: 300, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <PH title={s.symbol} meta={s.signal}
          right={<button onClick={onClose} style={{ background:'transparent', border:'1px solid var(--border-2)',
            color:'var(--muted)', fontFamily:'var(--mono)', fontSize:10, padding:'1px 6px', cursor:'pointer' }}>✕</button>} />
        <div style={{ overflow: 'auto', flex: 1 }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 12, fontWeight: 700 }}>{s.name || s.symbol}</div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '6px 0 10px' }}>
              <span style={{ fontSize: 16, fontWeight: 700 }}>${Number(s.price).toFixed(2)}</span>
              <span className={(s.change_pct||0) >= 0 ? 'up' : 'down'}>{fmtPct(s.change_pct)}</span>
              <span style={{ marginLeft: 'auto', fontSize: 20, fontWeight: 700, color: sc }}>{s.score}</span>
            </div>
            {[['Momentum',s.score_momentum,'var(--cyan)'],['Valuation',s.score_valuation,'var(--mint)'],
              ['Quality',s.score_quality,'var(--amber)'],['Options',s.score_options,'#8b5cf6'],['Macro',s.score_macro,'var(--rose)']
            ].map(([l,v,c]) => (
              <div key={l} style={{ marginBottom: 4 }}>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:9, color:'var(--muted)', marginBottom:2 }}>
                  <span>{l}</span><span>{v?.toFixed(1)}</span>
                </div>
                <div style={{ height:4, background:'var(--surface-2)', borderRadius:2 }}>
                  <div style={{ width:(v||0)+'%', height:'100%', background:c, borderRadius:2 }} />
                </div>
              </div>
            ))}
          </div>
          <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)' }}>
            {[['P/E',s.pe?s.pe.toFixed(1)+'x':'—'],['Fwd P/E',s.forward_pe?s.forward_pe.toFixed(1)+'x':'—'],
              ['Margin',s.profit_margin?(s.profit_margin*100).toFixed(1)+'%':'—'],['Beta',s.beta?s.beta.toFixed(2):'—'],
              ['Target',s.analyst_target?'$'+Number(s.analyst_target).toFixed(0):'—'],
              ['Upside',s.upside_pct!=null?fmtPct(s.upside_pct):'—'],
              ['Calls',fmtK(s.call_premium_k)],['Puts',fmtK(s.put_premium_k)]
            ].map(([k,v]) => (
              <div key={k} style={{ display:'flex', justifyContent:'space-between', padding:'2px 0' }}>
                <span className="mut" style={{ fontSize:10 }}>{k}</span>
                <span style={{ fontSize:10, fontWeight:600 }}>{v}</span>
              </div>
            ))}
          </div>
          {(s.reasons||[]).length > 0 && (
            <div style={{ padding: '8px 14px' }}>
              {(s.reasons||[]).map((r,i) => (
                <div key={i} style={{ display:'flex', gap:6, marginBottom:6, fontSize:10, lineHeight:1.5 }}>
                  <span style={{ color:sc, flexShrink:0 }}>◆</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Full analyst report for custom ticker analysis
  function AnalystReport({ s, onClose }) {
    if (!s) return null;
    const n = s.narrative || {};
    const rating = n.rating || (s.signal === 'STRONG BUY' || s.signal === 'BUY' ? 'BUY' : s.signal === 'HOLD' ? 'HOLD' : 'SELL');
    const rc  = RATING_COLOR[rating] || 'var(--text)';
    const rbg = RATING_BG[rating]    || 'transparent';
    const sc  = SIGNAL_COLOR[s.signal] || 'var(--text)';
    const fmtPct = v => v == null ? '—' : (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%';
    const fmtK   = v => !v ? '—' : v >= 1000 ? '$' + (v/1000).toFixed(1) + 'M' : '$' + Math.round(v) + 'K';
    const fmtMC  = v => {
      if (!v) return '—';
      if (v >= 1e12) return '$' + (v/1e12).toFixed(2) + 'T';
      if (v >= 1e9)  return '$' + (v/1e9).toFixed(1) + 'B';
      return '$' + (v/1e6).toFixed(0) + 'M';
    };
    const ana = n.analysis || {};
    const SECTIONS = [
      { key: 'momentum',  label: 'MOMENTUM',    color: 'var(--cyan)',  score: s.score_momentum  },
      { key: 'valuation', label: 'VALUATION',   color: 'var(--mint)',  score: s.score_valuation },
      { key: 'quality',   label: 'QUALITY',     color: 'var(--amber)', score: s.score_quality   },
      { key: 'macro',     label: 'MACRO',        color: 'var(--rose)',  score: s.score_macro     },
      { key: 'options',   label: 'OPTIONS FLOW', color: '#8b5cf6',     score: s.score_options   },
    ];

    return (
      <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        {/* Header row */}
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 12, alignItems: 'center', flexShrink: 0 }}>
          {/* Rating badge */}
          <div style={{ padding: '6px 16px', background: rbg, border: '2px solid ' + rc,
            display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 72 }}>
            <div style={{ fontSize: 9, color: rc, letterSpacing: '.12em', marginBottom: 1 }}>RATING</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: rc, letterSpacing: '.08em' }}>{rating}</div>
          </div>
          {/* Company info */}
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>{s.name || s.symbol}</div>
            <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 1 }}>
              {s.symbol}
              {s.sector ? ' · ' + s.sector : ''}
              {s.industry ? ' · ' + s.industry : ''}
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 4 }}>
              <span style={{ fontSize: 16, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>${Number(s.price).toFixed(2)}</span>
              <span className={(s.change_pct||0) >= 0 ? 'up' : 'down'} style={{ fontSize: 12 }}>{fmtPct(s.change_pct)}</span>
              {s.market_cap && <span style={{ fontSize: 10, color: 'var(--muted)' }}>MCap {fmtMC(s.market_cap)}</span>}
            </div>
          </div>
          {/* Score + signal */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: sc, lineHeight: 1 }}>{s.score}</div>
            <div style={{ fontSize: 9, color: sc, fontWeight: 700, letterSpacing: '.06em', marginTop: 2 }}>{s.signal}</div>
            <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 1 }}>/100 composite</div>
          </div>
          <button onClick={onClose} style={{ background:'transparent', border:'1px solid var(--border-2)',
            color:'var(--muted)', fontFamily:'var(--mono)', fontSize:11, padding:'4px 8px', cursor:'pointer',
            alignSelf: 'flex-start' }}>✕</button>
        </div>

        <div style={{ overflow: 'auto', flex: 1 }}>
          {/* Factor bars row */}
          <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 12 }}>
            {SECTIONS.map(({ key, label, color, score }) => (
              <div key={key} style={{ flex: 1 }}>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:9, color:'var(--muted)', marginBottom:3 }}>
                  <span>{label}</span><span style={{ color }}>{score?.toFixed(0)}</span>
                </div>
                <div style={{ height: 5, background: 'var(--surface-2)', borderRadius: 3 }}>
                  <div style={{ width: (score||0) + '%', height: '100%', background: color, borderRadius: 3, transition: 'width .4s ease' }} />
                </div>
              </div>
            ))}
          </div>

          {/* Data summary */}
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 9, color: 'var(--cyan)', letterSpacing: '.1em', fontWeight: 700, marginBottom: 6 }}>◆ DATA SUMMARY</div>
            {/* Key metrics grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px 12px', marginBottom: 8 }}>
              {[
                ['Price',      '$' + Number(s.price).toFixed(2)],
                ['P/E',        s.pe ? s.pe.toFixed(1) + 'x' : '—'],
                ['Fwd P/E',    s.forward_pe ? s.forward_pe.toFixed(1) + 'x' : '—'],
                ['Margin',     s.profit_margin ? (s.profit_margin*100).toFixed(1) + '%' : '—'],
                ['Beta',       s.beta ? s.beta.toFixed(2) : '—'],
                ['52w High',   s.week_52_high ? '$' + Number(s.week_52_high).toFixed(0) : '—'],
                ['52w Low',    s.week_52_low  ? '$' + Number(s.week_52_low).toFixed(0)  : '—'],
                ['Analyst Tgt',s.analyst_target ? '$' + Number(s.analyst_target).toFixed(0) : '—'],
                ['Upside',     s.upside_pct != null ? fmtPct(s.upside_pct) : '—'],
                ['Call Prem',  fmtK(s.call_premium_k)],
                ['Put Prem',   fmtK(s.put_premium_k)],
                ['MCap',       fmtMC(s.market_cap)],
              ].map(([k,v]) => (
                <div key={k}>
                  <div style={{ fontSize: 8, color: 'var(--muted)', marginBottom: 1 }}>{k}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
                </div>
              ))}
            </div>
            {/* Summary prose */}
            {n.summary && (
              <div style={{ fontSize: 10, color: 'var(--text-2)', lineHeight: 1.65, padding: '8px 10px',
                background: 'var(--surface)', borderLeft: '2px solid var(--border-2)', borderRadius: 2 }}>
                {n.summary}
              </div>
            )}
          </div>

          {/* Business description */}
          {s.description && (
            <div style={{ padding: '8px 14px', borderBottom: '1px solid var(--border)', fontSize: 10, color: 'var(--text-2)', lineHeight: 1.6 }}>
              <span style={{ color: 'var(--muted)', fontSize: 9, letterSpacing: '.06em', marginRight: 6 }}>ABOUT</span>
              {s.description}
            </div>
          )}

          {/* Verbal analysis sections */}
          <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 9, color: 'var(--cyan)', letterSpacing: '.1em', fontWeight: 700, marginBottom: 8 }}>◆ VERBAL ANALYSIS</div>
            {SECTIONS.map(({ key, label, color, score }) => {
              const txt = ana[key];
              if (!txt) return null;
              return (
                <div key={key} style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                    <div style={{ width: 3, height: 14, background: color, borderRadius: 2, flexShrink: 0 }} />
                    <span style={{ fontSize: 9, color, fontWeight: 700, letterSpacing: '.1em' }}>{label}</span>
                    <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
                    <span style={{ fontSize: 9, color, fontVariantNumeric: 'tabular-nums' }}>{score?.toFixed(0)}/100</span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text)', lineHeight: 1.7, paddingLeft: 11 }}>{txt}</div>
                </div>
              );
            })}
          </div>

          {/* Conclusion */}
          {n.conclusion && (
            <div style={{ padding: '12px 14px' }}>
              <div style={{ fontSize: 9, color: rc, letterSpacing: '.1em', fontWeight: 700, marginBottom: 8 }}>◆ CONCLUSION — {rating}</div>
              <div style={{ padding: '10px 14px', background: rbg, border: '1px solid ' + rc, borderRadius: 2,
                fontSize: 10, color: 'var(--text)', lineHeight: 1.7 }}>
                {n.conclusion}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  function RecPanel({ snap }) {
    const rec = snap.recommendations || { stocks: [], macro: {} };
    const macro = rec.macro || {};
    const stocks = rec.stocks || [];
    const [sel, setSel] = useState(null);
    const [filter, setFilter] = useState('ALL');
    const [query, setQuery]   = useState('');
    const [custom, setCustom] = useState(null);   // custom analyzed ticker result
    const [loading, setLoading] = useState(false);
    const [loadErr, setLoadErr] = useState('');
    const inputRef = useRef(null);

    const filtered = filter === 'ALL' ? stocks : stocks.filter(s => s.signal === filter);
    const tableSelected = sel != null ? stocks.find(s => s.symbol === sel) : null;

    const fmtPct = v => v == null ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
    const fmtNum = (v, dp = 1) => v == null ? '—' : Number(v).toFixed(dp);

    const runSearch = async () => {
      const sym = query.trim().toUpperCase();
      if (!sym) return;
      setLoading(true); setLoadErr(''); setCustom(null); setSel(null);
      try {
        const fn = window.DeltaLive && window.DeltaLive.fetchTickerAnalysis;
        if (!fn) throw new Error('fetchTickerAnalysis not available');
        const result = await fn(sym);
        if (result.error) { setLoadErr(result.error); }
        else { setCustom(result); }
      } catch (e) {
        setLoadErr(e.message || 'Failed to fetch');
      } finally {
        setLoading(false);
      }
    };

    const regime = macro.regime || '—';
    const regColor = regime === 'RISK-ON' ? 'var(--mint)' : regime === 'RISK-OFF' ? 'var(--rose)' : 'var(--amber)';
    const scorePct = macro.score_pct ?? 50;

    const rightPane = custom
      ? <AnalystReport s={custom} onClose={() => setCustom(null)} />
      : tableSelected
        ? <StockDetailCompact s={tableSelected} onClose={() => setSel(null)} />
        : null;

    // Top picks — highest-scored stocks (prefer BUY+, fall back to all ranked)
    const buyStocks = stocks.filter(s => s.signal === 'STRONG BUY' || s.signal === 'BUY');
    const topPicks = (buyStocks.length >= 3 ? buyStocks : stocks).slice(0, 6);

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>

        {/* TODAY'S TOP PICKS */}
        {topPicks.length > 0 && (
          <div className="panel" style={{ padding: '8px 12px', flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: 'var(--cyan)', letterSpacing: '.12em', marginBottom: 6, fontWeight: 700 }}>
              ★ TODAY'S TOP PICKS
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {topPicks.map((s, i) => {
                const sc = SIGNAL_COLOR[s.signal] || 'var(--text)';
                const active = !custom && sel === s.symbol;
                return (
                  <div key={s.symbol} onClick={() => { setCustom(null); setSel(active ? null : s.symbol); }}
                    style={{
                      cursor: 'pointer', padding: '6px 10px', border: '1px solid',
                      borderColor: active ? sc : 'var(--border-2)',
                      background: active ? 'rgba(56,189,248,.08)' : 'var(--surface)',
                      display: 'flex', flexDirection: 'column', gap: 2, minWidth: 72,
                      transition: 'border-color .15s, background .15s',
                    }}>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                      <span style={{ fontSize: 9, color: 'var(--muted)', fontVariantNumeric: 'tabular-nums' }}>#{i + 1}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', letterSpacing: '.04em' }}>{s.symbol}</span>
                    </div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: sc }}>{s.score}</div>
                    <div style={{ fontSize: 8, color: sc, letterSpacing: '.06em', fontWeight: 700 }}>
                      {s.signal === 'STRONG BUY' ? '★ STRONG BUY' : s.signal}
                    </div>
                    <div style={{ fontSize: 9, color: (s.change_pct || 0) >= 0 ? 'var(--mint)' : 'var(--rose)' }}>
                      {(s.change_pct || 0) >= 0 ? '+' : ''}{(s.change_pct || 0).toFixed(2)}%
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Search bar */}
        <div className="panel" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <span style={{ color: 'var(--cyan)', fontSize: 11, letterSpacing: '.1em', whiteSpace: 'nowrap' }}>◆ ANALYZE TICKER</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value.toUpperCase())}
            onKeyDown={e => { if (e.key === 'Enter') runSearch(); }}
            placeholder="Enter any ticker — AAPL, BRK.A, PLTR, 0700.HK…"
            style={{ flex: 1, background: 'var(--bg)', border: '1px solid var(--border-2)', color: 'var(--text)',
              fontFamily: 'var(--mono)', fontSize: 11, padding: '4px 8px', outline: 'none', letterSpacing: '.05em' }}
          />
          <button onClick={runSearch} disabled={loading}
            style={{ padding: '4px 14px', fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '.08em',
              background: 'var(--cyan)', color: 'var(--bg)', border: 'none', cursor: loading ? 'wait' : 'pointer',
              opacity: loading ? 0.6 : 1, fontWeight: 700 }}>
            {loading ? 'ANALYZING…' : 'ANALYZE'}
          </button>
          {loadErr && <span style={{ color: 'var(--rose)', fontSize: 10 }}>{loadErr}</span>}
          <span style={{ color: 'var(--muted)', fontSize: 9, marginLeft: 6, whiteSpace: 'nowrap' }}>uses live terminal data</span>
        </div>

        {/* Macro regime banner */}
        <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
          <div className="panel" style={{ flex: 2, padding: '8px 14px', display: 'flex', gap: 20, alignItems: 'center' }}>
            <div>
              <div className="mut" style={{ fontSize: 9, marginBottom: 2 }}>MACRO REGIME</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: regColor, letterSpacing: '.1em' }}>{regime}</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: 'var(--muted)', marginBottom: 3 }}>
                <span>RISK-OFF</span><span>NEUTRAL</span><span>RISK-ON</span>
              </div>
              <div style={{ height: 7, background: 'var(--surface-2)', borderRadius: 4, position: 'relative' }}>
                <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: scorePct + '%',
                  background: 'linear-gradient(90deg, var(--rose), var(--amber), var(--mint))',
                  borderRadius: 4, transition: 'width .6s ease' }} />
                <div style={{ position: 'absolute', top: -3, left: `calc(${scorePct}% - 4px)`,
                  width: 8, height: 13, background: 'var(--text)', borderRadius: 2 }} />
              </div>
            </div>
            <div style={{ fontSize: 13, fontVariantNumeric: 'tabular-nums', color: regColor, fontWeight: 700 }}>
              {scorePct}/100
            </div>
          </div>
          {[
            ['VIX',        macro.vix,         null,  (macro.signals||{}).vix         ],
            ['Curve 10y2y', macro.yield_curve, '%',   (macro.signals||{}).yield_curve ],
            ['Fed Funds',  macro.fed_funds,   '%',   (macro.signals||{}).fed         ],
            ['GDP',        macro.gdp,         '%',   (macro.signals||{}).growth      ],
          ].map(([label, val, unit, sig]) => (
            <div key={label} className="panel" style={{ flex: 1, padding: '8px 12px' }}>
              <div className="mut" style={{ fontSize: 9 }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--cyan)', fontVariantNumeric: 'tabular-nums' }}>
                {val != null ? Number(val).toFixed(2) + (unit || '') : '—'}
              </div>
              {sig && <div style={{ fontSize: 9, color: 'var(--muted)', marginTop: 1 }}>{sig}</div>}
            </div>
          ))}
        </div>

        {/* Main content */}
        <div style={{ flex: 1, display: 'flex', gap: 6, minHeight: 0 }}>
          {/* Ranked table */}
          <div className="panel" style={{ flex: custom ? 1 : tableSelected ? 2 : 3, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PH title="AI STOCK RECOMMENDATIONS"
              meta={`${filtered.length} SECURITIES`}
              right={
                <div style={{ display: 'flex', gap: 3 }}>
                  {['ALL','STRONG BUY','BUY','HOLD','REDUCE','AVOID'].map(f => (
                    <button key={f} onClick={() => setFilter(f)}
                      style={{
                        padding: '1px 6px', fontSize: 9, cursor: 'pointer',
                        fontFamily: 'var(--mono)', letterSpacing: '.04em',
                        background: filter === f ? (SIGNAL_BG[f] || 'var(--surface-2)') : 'transparent',
                        border: '1px solid ' + (filter === f ? (SIGNAL_COLOR[f] || 'var(--border-2)') : 'var(--border-2)'),
                        color: filter === f ? (SIGNAL_COLOR[f] || 'var(--text)') : 'var(--text-2)',
                      }}>
                      {f === 'ALL' ? 'ALL' : f === 'STRONG BUY' ? '★ BUY+' : f}
                    </button>
                  ))}
                </div>
              } />
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {filtered.length === 0 ? <Empty msg="Computing recommendations…" /> : (
                <table className="dense">
                  <thead><tr>
                    <th style={{ width: 26 }}>#</th>
                    <th>TICKER</th>
                    <th>SIGNAL</th>
                    <th className="num">SCORE</th>
                    <th className="num">MOM</th>
                    <th className="num">VAL</th>
                    <th className="num">QUAL</th>
                    <th className="num">OPT</th>
                    <th className="num">MCR</th>
                    <th className="num">PRICE</th>
                    <th className="num">CHG%</th>
                    <th className="num">UPSIDE</th>
                    <th className="num">P/E</th>
                    <th className="num">FWD P/E</th>
                    <th className="num">MARGIN</th>
                  </tr></thead>
                  <tbody>
                    {filtered.map((s, i) => {
                      const active = !custom && sel === s.symbol;
                      const sc = SIGNAL_COLOR[s.signal] || 'var(--text)';
                      const upColor = (s.upside_pct || 0) > 0 ? 'var(--mint)' : 'var(--rose)';
                      return (
                        <tr key={s.symbol} onClick={() => { setCustom(null); setSel(active ? null : s.symbol); }}
                          style={{ cursor: 'pointer', background: active ? 'rgba(56,189,248,.08)' : 'transparent' }}>
                          <td className="mut" style={{ fontSize: 9 }}>{i + 1}</td>
                          <td className="lbl" style={{ fontWeight: 700 }}>{s.symbol}</td>
                          <td>
                            <span style={{ color: sc, fontSize: 9, fontWeight: 700,
                              padding: '1px 5px', background: SIGNAL_BG[s.signal] || 'transparent',
                              border: '1px solid ' + sc }}>
                              {s.signal === 'STRONG BUY' ? '★ ' + s.signal : s.signal}
                            </span>
                          </td>
                          <td className="num" style={{ fontWeight: 700, color: sc }}>{s.score}</td>
                          <td className="num" style={{ fontSize: 10 }}>{fmtNum(s.score_momentum)}</td>
                          <td className="num" style={{ fontSize: 10 }}>{fmtNum(s.score_valuation)}</td>
                          <td className="num" style={{ fontSize: 10 }}>{fmtNum(s.score_quality)}</td>
                          <td className="num" style={{ fontSize: 10 }}>{fmtNum(s.score_options)}</td>
                          <td className="num" style={{ fontSize: 10 }}>{fmtNum(s.score_macro)}</td>
                          <td className="num" style={{ fontVariantNumeric: 'tabular-nums' }}>${s.price?.toFixed(2)}</td>
                          <td className={`num ${(s.change_pct||0) >= 0 ? 'up' : 'down'}`}>{fmtPct(s.change_pct)}</td>
                          <td className="num" style={{ color: upColor }}>{s.upside_pct != null ? fmtPct(s.upside_pct) : '—'}</td>
                          <td className="num mut" style={{ fontSize: 10 }}>{s.pe ? s.pe.toFixed(1) + 'x' : '—'}</td>
                          <td className="num mut" style={{ fontSize: 10 }}>{s.forward_pe ? s.forward_pe.toFixed(1) + 'x' : '—'}</td>
                          <td className="num mut" style={{ fontSize: 10 }}>{s.profit_margin ? (s.profit_margin*100).toFixed(1) + '%' : '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
            <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
              Momentum 30% · Valuation 25% · Quality 20% · Options 10% · Macro 15% · NOT FINANCIAL ADVICE
            </div>
          </div>

          {/* Detail / custom analysis pane */}
          {rightPane}
        </div>
      </div>
    );
  }

  // ── EDGAR Panel ───────────────────────────────────────────────────────────────
  function EdgarPanel({ snap }) {
    const [view, setView]     = useState('trades');  // trades | 8k | 10q
    const [filter, setFilter] = useState('');
    const edgar = snap.edgar || { insider_trades: [], filings_8k: [], filings_10q: [] };
    const fl = filter.toLowerCase();

    const trades = useMemo(() => {
      const t = edgar.insider_trades || [];
      if (!fl) return t;
      return t.filter(r =>
        (r.ticker||'').toLowerCase().includes(fl) ||
        (r.insider_name||'').toLowerCase().includes(fl) ||
        (r.role||'').toLowerCase().includes(fl) ||
        (r.action||'').toLowerCase().includes(fl)
      );
    }, [edgar.insider_trades, fl]);

    const filings8k = useMemo(() => {
      const f = edgar.filings_8k || [];
      if (!fl) return f;
      return f.filter(r =>
        (r.ticker||'').toLowerCase().includes(fl) ||
        (r.company||'').toLowerCase().includes(fl) ||
        (r.title||'').toLowerCase().includes(fl)
      );
    }, [edgar.filings_8k, fl]);

    const filings10q = useMemo(() => {
      const f = edgar.filings_10q || [];
      if (!fl) return f;
      return f.filter(r =>
        (r.ticker||'').toLowerCase().includes(fl) ||
        (r.company||'').toLowerCase().includes(fl)
      );
    }, [edgar.filings_10q, fl]);

    const fmtVal = (v) => {
      if (!v) return '—';
      if (v >= 1e9) return '$' + (v/1e9).toFixed(1) + 'B';
      if (v >= 1e6) return '$' + (v/1e6).toFixed(1) + 'M';
      if (v >= 1e3) return '$' + (v/1e3).toFixed(0) + 'K';
      return '$' + v.toFixed(0);
    };
    const fmtShares = (n) => {
      if (!n) return '—';
      if (n >= 1e6) return (n/1e6).toFixed(2) + 'M';
      if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
      return n.toLocaleString();
    };

    const tabs = [
      { key: 'trades', label: `INSIDER TRADES (${(edgar.insider_trades||[]).length})` },
      { key: '8k',     label: `8-K EVENTS (${(edgar.filings_8k||[]).length})` },
      { key: '10q',    label: `EARNINGS (${(edgar.filings_10q||[]).length})` },
    ];

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <PH title="INS · SEC INSIDER ACTIVITY" meta="Form 4 · 8-K · 10-Q/K" right={<Filter value={filter} onChange={setFilter} placeholder="filter ticker / name…" />} />

          {/* sub-tabs */}
          <div style={{ display: 'flex', gap: 2, padding: '3px 8px', borderBottom: '1px solid var(--border)' }}>
            {tabs.map(tb => (
              <button key={tb.key} onClick={() => setView(tb.key)}
                style={{ fontFamily: 'var(--mono)', fontSize: 9, padding: '2px 8px', cursor: 'pointer',
                  background: view === tb.key ? 'var(--cyan)' : 'var(--panel)',
                  color: view === tb.key ? 'var(--bg)' : 'var(--muted)',
                  border: '1px solid var(--border-2)' }}>
                {tb.label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {view === 'trades' && (
              trades.length === 0 ? <Empty msg="No insider trades found — EDGAR poller running…" /> : (
                <table className="data-table" style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ width: 50 }}>TICKER</th>
                      <th>INSIDER</th>
                      <th style={{ width: 70 }}>ROLE</th>
                      <th style={{ width: 40 }}>ACTION</th>
                      <th style={{ width: 70, textAlign: 'right' }}>SHARES</th>
                      <th style={{ width: 75, textAlign: 'right' }}>VALUE</th>
                      <th style={{ width: 75, textAlign: 'right' }}>PRICE</th>
                      <th style={{ width: 70 }}>DATE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.slice(0, 150).map((t, i) => {
                      const isBuy = t.action === 'BUY';
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ fontWeight: 700, color: 'var(--cyan)' }}>
                            <a href={t.filing_url} target="_blank" rel="noreferrer"
                              style={{ color: 'var(--cyan)', textDecoration: 'none' }}>{t.ticker}</a>
                          </td>
                          <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              title={t.insider_name}>{t.insider_name || '—'}</td>
                          <td style={{ color: 'var(--muted)', fontSize: 9 }}>{t.role || '—'}</td>
                          <td style={{ color: isBuy ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>
                            {isBuy ? '▲ BUY' : '▼ SELL'}
                          </td>
                          <td style={{ textAlign: 'right' }}>{fmtShares(t.shares)}</td>
                          <td style={{ textAlign: 'right', color: isBuy ? 'var(--green)' : 'var(--red)' }}>
                            {fmtVal(t.value_usd)}
                          </td>
                          <td style={{ textAlign: 'right', color: 'var(--muted)' }}>
                            {t.price ? '$' + Number(t.price).toFixed(2) : '—'}
                          </td>
                          <td style={{ color: 'var(--muted)' }}>{t.date || '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )
            )}
            {view === '8k' && (
              filings8k.length === 0 ? <Empty msg="No 8-K filings found" /> : (
                <table className="data-table" style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ width: 55 }}>TICKER</th>
                      <th>COMPANY</th>
                      <th>TITLE / EVENT</th>
                      <th style={{ width: 80 }}>DATE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filings8k.slice(0, 100).map((f, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ fontWeight: 700, color: 'var(--cyan)' }}>
                          <a href={f.url} target="_blank" rel="noreferrer"
                            style={{ color: 'var(--cyan)', textDecoration: 'none' }}>{f.ticker}</a>
                        </td>
                        <td style={{ color: 'var(--muted)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={f.company}>{f.company}</td>
                        <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={f.title}>{f.title || 'Material Event'}</td>
                        <td style={{ color: 'var(--muted)' }}>{f.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
            {view === '10q' && (
              filings10q.length === 0 ? <Empty msg="No earnings filings found" /> : (
                <table className="data-table" style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ width: 55 }}>TICKER</th>
                      <th>COMPANY</th>
                      <th style={{ width: 60 }}>FORM</th>
                      <th style={{ width: 80 }}>DATE</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filings10q.slice(0, 100).map((f, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ fontWeight: 700, color: 'var(--cyan)' }}>
                          <a href={f.url} target="_blank" rel="noreferrer"
                            style={{ color: 'var(--cyan)', textDecoration: 'none' }}>{f.ticker}</a>
                        </td>
                        <td style={{ color: 'var(--muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={f.company}>{f.company}</td>
                        <td style={{ color: 'var(--yellow)' || 'var(--cyan)' }}>{f.form}</td>
                        <td style={{ color: 'var(--muted)' }}>{f.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>

          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: SEC EDGAR · Form 4 BUY/SELL only · Watchlist: top 20 US equities · Updates hourly
          </div>
        </div>
      </div>
    );
  }

  // ── ALERTS — Price Alert System ──────────────────────────────────────────────
  const ALERTS_KEY = 'delta_alerts';

  function loadAlerts() {
    try { return JSON.parse(localStorage.getItem(ALERTS_KEY) || '[]'); } catch { return []; }
  }
  function saveAlerts(alerts) {
    localStorage.setItem(ALERTS_KEY, JSON.stringify(alerts));
  }

  function getPriceFromSnap(snap, ticker) {
    const t = ticker.toUpperCase();
    const all = [...(snap.indices || []), ...(snap.tech || []), ...(snap.macro || [])];
    const found = all.find(r => (r.ticker || '').toUpperCase() === t);
    return found ? found.price : null;
  }

  function AlertsPanel({ snap }) {
    const { useState: useStateL, useEffect, useRef, useMemo: useMemoL } = React;
    const [alerts, setAlerts] = useStateL(() => loadAlerts());
    const [ticker, setTicker] = useStateL('');
    const [condition, setCondition] = useStateL('above');
    const [price, setPrice] = useStateL('');
    const [note, setNote] = useStateL('');
    const [flashIds, setFlashIds] = useStateL({});
    const snapRef = useRef(snap);

    useEffect(() => { snapRef.current = snap; }, [snap]);

    // Prune triggered alerts older than 24h
    useEffect(() => {
      const pruned = loadAlerts().filter(a => {
        if (!a.triggered) return true;
        const age = Date.now() - new Date(a.triggered_at).getTime();
        return age < 24 * 60 * 60 * 1000;
      });
      saveAlerts(pruned);
      setAlerts(pruned);
    }, []);

    // Check alerts every 2s
    useEffect(() => {
      const id = setInterval(() => {
        const current = loadAlerts();
        let changed = false;
        const nowFlash = {};
        const updated = current.map(a => {
          if (a.triggered) return a;
          const p = getPriceFromSnap(snapRef.current, a.ticker);
          if (p == null) return a;
          const hit = a.condition === 'above' ? p >= a.price : p <= a.price;
          if (hit) {
            changed = true;
            nowFlash[a.id] = true;
            return { ...a, triggered: true, triggered_at: new Date().toISOString() };
          }
          return a;
        });
        if (changed) {
          saveAlerts(updated);
          setAlerts(updated);
          setFlashIds(prev => ({ ...prev, ...nowFlash }));
          // Remove flash highlights after 3s
          setTimeout(() => setFlashIds(prev => {
            const next = { ...prev };
            Object.keys(nowFlash).forEach(k => delete next[k]);
            return next;
          }), 3000);
        }
      }, 2000);
      return () => clearInterval(id);
    }, []);

    function addAlert() {
      const t = ticker.trim().toUpperCase();
      const p = parseFloat(price);
      if (!t || isNaN(p)) return;
      const alert = {
        id: Date.now() + '-' + Math.random().toString(36).slice(2),
        ticker: t,
        condition,
        price: p,
        note: note.trim(),
        created: new Date().toISOString(),
        triggered: false,
        triggered_at: null,
      };
      const updated = [...loadAlerts(), alert];
      saveAlerts(updated);
      setAlerts(updated);
      setTicker(''); setPrice(''); setNote('');
    }

    function deleteAlert(id) {
      const updated = loadAlerts().filter(a => a.id !== id);
      saveAlerts(updated);
      setAlerts(updated);
    }

    const active = useMemoL(() => alerts.filter(a => !a.triggered), [alerts]);
    const triggered = useMemoL(() =>
      alerts.filter(a => a.triggered)
        .sort((a, b) => new Date(b.triggered_at) - new Date(a.triggered_at))
        .slice(0, 20),
      [alerts]
    );

    const inputStyle = {
      background: 'var(--bg)', border: '1px solid var(--border-2)', color: 'var(--text)',
      fontFamily: 'var(--mono)', fontSize: 10, padding: '2px 6px', outline: 'none',
    };

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6, overflow: 'auto' }}>
        <div className="panel">
          <PH title="PRICE ALERTS" meta={`${active.length} ACTIVE`} />

          {/* Add form */}
          <div style={{ padding: '6px 8px', display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
            <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
              placeholder="TICKER" style={{ ...inputStyle, width: 70 }}
              onKeyDown={e => e.key === 'Enter' && addAlert()} />
            <div style={{ display: 'flex', gap: 0 }}>
              {['above', 'below'].map(c => (
                <button key={c} className={`btn${condition === c ? ' on' : ''}`}
                  onClick={() => setCondition(c)}
                  style={{ padding: '1px 8px', fontSize: 10, textTransform: 'uppercase' }}>
                  {c}
                </button>
              ))}
            </div>
            <input value={price} onChange={e => setPrice(e.target.value)}
              placeholder="PRICE" type="number" step="0.01"
              style={{ ...inputStyle, width: 80 }}
              onKeyDown={e => e.key === 'Enter' && addAlert()} />
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder="note (optional)" style={{ ...inputStyle, width: 140 }}
              onKeyDown={e => e.key === 'Enter' && addAlert()} />
            <button className="btn on" onClick={addAlert}
              style={{ padding: '1px 10px', fontSize: 10 }}>ADD</button>
          </div>

          {/* Active alerts table */}
          {active.length === 0
            ? <Empty msg="No active alerts — add one above" />
            : (
              <div style={{ overflow: 'auto' }}>
                <table className="dense" style={{ width: '100%' }}>
                  <thead><tr>
                    <th>TICKER</th>
                    <th>CONDITION</th>
                    <th style={{ textAlign: 'right' }}>TARGET</th>
                    <th style={{ textAlign: 'right' }}>CURRENT</th>
                    <th>NOTE</th>
                    <th></th>
                  </tr></thead>
                  <tbody>
                    {active.map(a => {
                      const cur = getPriceFromSnap(snap, a.ticker);
                      const isFlashing = flashIds[a.id];
                      return (
                        <tr key={a.id} style={{
                          background: isFlashing ? 'var(--mint)' : undefined,
                          color: isFlashing ? 'var(--bg)' : undefined,
                          transition: 'background 0.3s',
                        }}>
                          <td style={{ fontWeight: 700, color: isFlashing ? 'var(--bg)' : 'var(--cyan)' }}>{a.ticker}</td>
                          <td style={{ color: isFlashing ? 'var(--bg)' : a.condition === 'above' ? 'var(--mint)' : 'var(--rose)', textTransform: 'uppercase', fontSize: 10 }}>
                            {a.condition}
                          </td>
                          <td className="num">${a.price.toFixed(2)}</td>
                          <td className="num" style={{ color: cur == null ? 'var(--muted)' : cur >= a.price ? 'var(--mint)' : 'var(--rose)' }}>
                            {cur != null ? '$' + cur.toFixed(2) : '—'}
                          </td>
                          <td style={{ color: 'var(--muted)', fontSize: 10, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              title={a.note}>{a.note || '—'}</td>
                          <td>
                            <button className="btn" onClick={() => deleteAlert(a.id)}
                              style={{ padding: '0px 6px', fontSize: 9, color: 'var(--rose)' }}>DEL</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )
          }
        </div>

        {/* Triggered alerts */}
        {triggered.length > 0 && (
          <div className="panel" style={{ opacity: 0.7 }}>
            <PH title="TRIGGERED" meta={`LAST ${triggered.length}`} />
            <div style={{ overflow: 'auto' }}>
              <table className="dense" style={{ width: '100%' }}>
                <thead><tr>
                  <th>TICKER</th>
                  <th>CONDITION</th>
                  <th style={{ textAlign: 'right' }}>TARGET</th>
                  <th>NOTE</th>
                  <th>TRIGGERED AT</th>
                  <th></th>
                </tr></thead>
                <tbody>
                  {triggered.map(a => (
                    <tr key={a.id}>
                      <td style={{ fontWeight: 700, color: 'var(--muted)' }}>{a.ticker}</td>
                      <td style={{ color: a.condition === 'above' ? 'var(--mint)' : 'var(--rose)', opacity: 0.6, textTransform: 'uppercase', fontSize: 10 }}>{a.condition}</td>
                      <td className="num">${a.price.toFixed(2)}</td>
                      <td style={{ color: 'var(--muted)', fontSize: 10 }}>{a.note || '—'}</td>
                      <td style={{ color: 'var(--muted)', fontSize: 10 }}>
                        {a.triggered_at ? new Date(a.triggered_at).toLocaleString() : '—'}
                      </td>
                      <td>
                        <button className="btn" onClick={() => deleteAlert(a.id)}
                          style={{ padding: '0px 6px', fontSize: 9, color: 'var(--muted)' }}>DEL</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── PORTFOLIO — Holdings & P&L ────────────────────────────────────────────────
  const PORTFOLIO_KEY = 'delta_portfolio';

  function loadPortfolio() {
    try { return JSON.parse(localStorage.getItem(PORTFOLIO_KEY) || '[]'); } catch { return []; }
  }
  function savePortfolio(positions) {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(positions));
  }

  function PortfolioPanel({ snap }) {
    const { useState: useStateP, useMemo: useMemoP } = React;
    const [positions, setPositions] = useStateP(() => loadPortfolio());
    const [ticker, setTicker] = useStateP('');
    const [shares, setShares] = useStateP('');
    const [avgCost, setAvgCost] = useStateP('');
    const [note, setNote] = useStateP('');

    function addPosition() {
      const t = ticker.trim().toUpperCase();
      const sh = parseFloat(shares);
      const ac = parseFloat(avgCost);
      if (!t || isNaN(sh) || isNaN(ac) || sh <= 0 || ac <= 0) return;
      const pos = {
        id: Date.now() + '-' + Math.random().toString(36).slice(2),
        ticker: t,
        shares: sh,
        avg_cost: ac,
        note: note.trim(),
        added: new Date().toISOString(),
      };
      const updated = [...loadPortfolio(), pos];
      savePortfolio(updated);
      setPositions(updated);
      setTicker(''); setShares(''); setAvgCost(''); setNote('');
    }

    function deletePosition(id) {
      const updated = loadPortfolio().filter(p => p.id !== id);
      savePortfolio(updated);
      setPositions(updated);
    }

    const rows = useMemoP(() => {
      return positions.map(pos => {
        const cur = getPriceFromSnap(snap, pos.ticker);
        const mktVal = cur != null ? cur * pos.shares : null;
        const costBasis = pos.avg_cost * pos.shares;
        const pnl = mktVal != null ? mktVal - costBasis : null;
        const pnlPct = pnl != null ? (pnl / costBasis) * 100 : null;
        // Day change: cur vs prev_close. snap rows may have chg_pct field
        const all = [...(snap.indices || []), ...(snap.tech || []), ...(snap.macro || [])];
        const row = all.find(r => (r.ticker || '').toUpperCase() === pos.ticker.toUpperCase());
        const prevClose = (cur != null && row && row.chg_pct != null)
          ? cur / (1 + row.chg_pct / 100)
          : null;
        const dayChg = (cur != null && prevClose != null) ? (cur - prevClose) * pos.shares : null;
        return { ...pos, cur, mktVal, costBasis, pnl, pnlPct, dayChg };
      });
    }, [positions, snap]);

    const totals = useMemoP(() => {
      const totalMkt = rows.reduce((s, r) => s + (r.mktVal || 0), 0);
      const totalCost = rows.reduce((s, r) => s + r.costBasis, 0);
      const totalPnl = rows.reduce((s, r) => s + (r.pnl || 0), 0);
      return { totalMkt, totalCost, totalPnl };
    }, [rows]);

    const inputStyle = {
      background: 'var(--bg)', border: '1px solid var(--border-2)', color: 'var(--text)',
      fontFamily: 'var(--mono)', fontSize: 10, padding: '2px 6px', outline: 'none',
    };

    function fmtMoney(v) {
      if (v == null) return '—';
      const abs = Math.abs(v);
      if (abs >= 1e6) return (v < 0 ? '-' : '') + '$' + (abs / 1e6).toFixed(2) + 'M';
      if (abs >= 1e3) return (v < 0 ? '-' : '') + '$' + (abs / 1e3).toFixed(1) + 'K';
      return (v < 0 ? '-$' : '$') + abs.toFixed(2);
    }

    function pnlColor(v) {
      if (v == null) return 'var(--muted)';
      return v >= 0 ? 'var(--mint)' : 'var(--rose)';
    }

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6, overflow: 'auto' }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="PORTFOLIO" meta={`${positions.length} POSITIONS`} />

          {/* Add position form */}
          <div style={{ padding: '6px 8px', display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
            <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
              placeholder="TICKER" style={{ ...inputStyle, width: 70 }}
              onKeyDown={e => e.key === 'Enter' && addPosition()} />
            <input value={shares} onChange={e => setShares(e.target.value)}
              placeholder="SHARES" type="number" step="0.0001"
              style={{ ...inputStyle, width: 80 }}
              onKeyDown={e => e.key === 'Enter' && addPosition()} />
            <input value={avgCost} onChange={e => setAvgCost(e.target.value)}
              placeholder="COST BASIS" type="number" step="0.01"
              style={{ ...inputStyle, width: 90 }}
              onKeyDown={e => e.key === 'Enter' && addPosition()} />
            <input value={note} onChange={e => setNote(e.target.value)}
              placeholder="note (optional)" style={{ ...inputStyle, width: 130 }}
              onKeyDown={e => e.key === 'Enter' && addPosition()} />
            <button className="btn on" onClick={addPosition}
              style={{ padding: '1px 10px', fontSize: 10 }}>ADD</button>
          </div>

          {/* Holdings table */}
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {rows.length === 0
              ? <Empty msg="No positions — add one above" />
              : (
                <table className="dense" style={{ width: '100%' }}>
                  <thead><tr>
                    <th>TICKER</th>
                    <th style={{ textAlign: 'right' }}>SHARES</th>
                    <th style={{ textAlign: 'right' }}>COST BASIS</th>
                    <th style={{ textAlign: 'right' }}>PRICE</th>
                    <th style={{ textAlign: 'right' }}>MKT VAL</th>
                    <th style={{ textAlign: 'right' }}>UNRL P&L $</th>
                    <th style={{ textAlign: 'right' }}>UNRL P&L %</th>
                    <th style={{ textAlign: 'right' }}>DAY CHG $</th>
                    <th>NOTE</th>
                    <th></th>
                  </tr></thead>
                  <tbody>
                    {rows.map(r => (
                      <tr key={r.id}>
                        <td style={{ fontWeight: 700, color: 'var(--cyan)' }}>{r.ticker}</td>
                        <td className="num">{r.shares % 1 === 0 ? r.shares.toLocaleString() : r.shares.toFixed(4)}</td>
                        <td className="num">${r.avg_cost.toFixed(2)}</td>
                        <td className="num" style={{ color: r.cur != null ? 'var(--text)' : 'var(--muted)' }}>
                          {r.cur != null ? '$' + r.cur.toFixed(2) : '—'}
                        </td>
                        <td className="num">{fmtMoney(r.mktVal)}</td>
                        <td className="num" style={{ color: pnlColor(r.pnl), fontWeight: 600 }}>
                          {r.pnl != null ? (r.pnl >= 0 ? '+' : '') + fmtMoney(r.pnl) : '—'}
                        </td>
                        <td className="num" style={{ color: pnlColor(r.pnlPct) }}>
                          {r.pnlPct != null ? (r.pnlPct >= 0 ? '+' : '') + r.pnlPct.toFixed(2) + '%' : '—'}
                        </td>
                        <td className="num" style={{ color: pnlColor(r.dayChg) }}>
                          {r.dayChg != null ? (r.dayChg >= 0 ? '+' : '') + fmtMoney(r.dayChg) : '—'}
                        </td>
                        <td style={{ color: 'var(--muted)', fontSize: 10, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={r.note}>{r.note || '—'}</td>
                        <td>
                          <button className="btn" onClick={() => deletePosition(r.id)}
                            style={{ padding: '0px 6px', fontSize: 9, color: 'var(--rose)' }}>DEL</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr style={{ borderTop: '1px solid var(--border)', fontWeight: 700 }}>
                      <td colSpan={4} style={{ padding: '3px 6px', fontSize: 10, color: 'var(--muted)' }}>TOTAL</td>
                      <td className="num">{fmtMoney(totals.totalMkt)}</td>
                      <td className="num" style={{ color: pnlColor(totals.totalPnl), fontWeight: 700 }}>
                        {totals.totalPnl >= 0 ? '+' : ''}{fmtMoney(totals.totalPnl)}
                      </td>
                      <td className="num" style={{ color: pnlColor(totals.totalPnl) }}>
                        {totals.totalCost > 0 ? (totals.totalPnl >= 0 ? '+' : '') + ((totals.totalPnl / totals.totalCost) * 100).toFixed(2) + '%' : '—'}
                      </td>
                      <td colSpan={3}></td>
                    </tr>
                  </tfoot>
                </table>
              )
            }
          </div>

          {/* Summary bar */}
          {rows.length > 0 && (
            <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)', display: 'flex', gap: 16 }}>
              <span>MKT VALUE: <span style={{ color: 'var(--text)' }}>{fmtMoney(totals.totalMkt)}</span></span>
              <span>COST BASIS: <span style={{ color: 'var(--text)' }}>{fmtMoney(totals.totalCost)}</span></span>
              <span>TOTAL P&L: <span style={{ color: pnlColor(totals.totalPnl), fontWeight: 700 }}>
                {totals.totalPnl >= 0 ? '+' : ''}{fmtMoney(totals.totalPnl)}
                {totals.totalCost > 0 ? ` (${totals.totalPnl >= 0 ? '+' : ''}${((totals.totalPnl / totals.totalCost) * 100).toFixed(2)}%)` : ''}
              </span></span>
            </div>
          )}
          {rows.length > 0 && <PnlHistoryChart rows={rows} />}
        </div>
      </div>
    );
  }

  // ── Earnings Calendar Panel ───────────────────────────────────────────────────
  function EarningsPanel({ snap }) {
    const [view, setView]     = useState('upcoming');  // upcoming | recent
    const [filter, setFilter] = useState('');
    const earnings = snap.earnings || { upcoming: [], recent: [] };
    const fl = filter.toLowerCase();

    const fmtEps = (v) => {
      if (v == null) return '—';
      return Number(v).toFixed(2);
    };
    const fmtRev = (v) => {
      if (v == null) return '—';
      if (v >= 1e9)  return '$' + (v / 1e9).toFixed(1) + 'B';
      if (v >= 1e6)  return '$' + (v / 1e6).toFixed(1) + 'M';
      if (v >= 1e3)  return '$' + (v / 1e3).toFixed(0) + 'K';
      return '$' + Number(v).toFixed(0);
    };
    const fmtQY = (q, y) => {
      if (!q && !y) return '—';
      if (q && y)   return `Q${q}/'${String(y).slice(2)}`;
      if (y)        return String(y);
      return `Q${q}`;
    };

    const surpriseColor = (pct) => {
      if (pct == null) return 'var(--muted)';
      if (pct > 0)     return '#00cc66';
      if (pct < 0)     return '#ff4466';
      return 'var(--text)';
    };

    const upcoming = useMemo(() => {
      const rows = earnings.upcoming || [];
      if (!fl) return rows;
      return rows.filter(r => (r.symbol || '').toLowerCase().includes(fl));
    }, [earnings.upcoming, fl]);

    const recent = useMemo(() => {
      const rows = earnings.recent || [];
      if (!fl) return rows;
      return rows.filter(r => (r.symbol || '').toLowerCase().includes(fl));
    }, [earnings.recent, fl]);

    const tabs = [
      { key: 'upcoming', label: `UPCOMING (${(earnings.upcoming || []).length})` },
      { key: 'recent',   label: `RECENT (${(earnings.recent   || []).length})` },
    ];

    const rows = view === 'upcoming' ? upcoming : recent;

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <PH title="EPS · EARNINGS CALENDAR" meta="Finnhub · 2 wk ahead / 1 wk back"
              right={<Filter value={filter} onChange={setFilter} placeholder="filter symbol…" />} />

          {/* sub-tabs */}
          <div style={{ display: 'flex', gap: 2, padding: '3px 8px', borderBottom: '1px solid var(--border)' }}>
            {tabs.map(tb => (
              <button key={tb.key} onClick={() => setView(tb.key)}
                style={{ fontFamily: 'var(--mono)', fontSize: 9, padding: '2px 8px', cursor: 'pointer',
                  background: view === tb.key ? 'var(--cyan)' : 'var(--panel)',
                  color:      view === tb.key ? 'var(--bg)'   : 'var(--muted)',
                  border: '1px solid var(--border-2)' }}>
                {tb.label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            {rows.length === 0
              ? <Empty msg={view === 'upcoming' ? 'No upcoming earnings — poller running…' : 'No recent earnings found'} />
              : (
                <table className="data-table" style={{ width: '100%', fontSize: 10, borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ width: 60 }}>DATE</th>
                      <th style={{ width: 65 }}>SYMBOL</th>
                      <th style={{ width: 40 }}>WHEN</th>
                      <th style={{ width: 55 }}>EPS EST</th>
                      <th style={{ width: 55 }}>EPS ACT</th>
                      <th style={{ width: 65 }}>SURPRISE%</th>
                      <th style={{ width: 80 }}>REV EST</th>
                      <th style={{ width: 50 }}>Q/Y</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => {
                      const spct = r.surprise_pct;
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ color: 'var(--muted)' }}>{r.date || '—'}</td>
                          <td style={{ fontWeight: 700, color: 'var(--cyan)' }}>{r.symbol}</td>
                          <td style={{ color: 'var(--yellow)' }}>{r.hour || '—'}</td>
                          <td style={{ color: 'var(--text)' }}>{fmtEps(r.eps_estimate)}</td>
                          <td style={{ color: 'var(--text)' }}>{fmtEps(r.eps_actual)}</td>
                          <td style={{ color: surpriseColor(spct), fontWeight: spct != null ? 600 : 400 }}>
                            {spct != null ? (spct > 0 ? '+' : '') + spct.toFixed(1) + '%' : '—'}
                          </td>
                          <td style={{ color: 'var(--muted)' }}>{fmtRev(r.revenue_estimate)}</td>
                          <td style={{ color: 'var(--muted)' }}>{fmtQY(r.quarter, r.year)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )
            }
          </div>

          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: Finnhub (yfinance fallback) · Updates hourly · BMO = Before Market Open · AMC = After Market Close
          </div>
        </div>
      </div>
    );
  }

  // ── Charts Panel ─────────────────────────────────────────────────────────────
  function SvgChart({ bars, mode, prevClose, chartType }) {
    if (!bars || bars.length < 2) return <div style={{ padding: 20, color: 'var(--muted)', fontSize: 11 }}>No chart data</div>;

    const W = 600, H = 180, PL = 52, PR = 8, PT = 10, PB = 28;
    const cw = W - PL - PR, ch = H - PT - PB;

    const isCandle = chartType === 'CANDLE';
    const allLows  = isCandle ? bars.map(b => b.l || b.c) : bars.map(b => b.c);
    const allHighs = isCandle ? bars.map(b => b.h || b.c) : bars.map(b => b.c);
    const minP = Math.min(...allLows), maxP = Math.max(...allHighs);
    const range = maxP - minP || maxP * 0.001;

    const x = (i) => PL + (i / (bars.length - 1)) * cw;
    const y = (p) => PT + ch - ((p - minP) / range) * ch;

    const first = bars[0].c, last = bars[bars.length-1].c;
    const up = last >= (prevClose || first);
    const color = up ? 'var(--mint)' : 'var(--rose)';
    const fillId = `cf${Math.random().toString(36).slice(2,7)}`;

    const linePts = bars.map((b, i) => `${x(i)},${y(b.c)}`).join(' ');
    const areaPath = `M${x(0)},${y(bars[0].c)} ` +
      bars.slice(1).map((b, i) => `L${x(i+1)},${y(b.c)}`).join(' ') +
      ` L${x(bars.length-1)},${PT+ch} L${x(0)},${PT+ch} Z`;

    const yTicks = Array.from({length: 4}, (_, i) => minP + (range * i / 3));
    const xStep = Math.max(1, Math.floor(bars.length / 5));
    const xTicks = bars.filter((_, i) => i % xStep === 0 || i === bars.length - 1).map((b) => ({
      x: x(bars.indexOf(b)),
      label: mode === 'INTRADAY'
        ? new Date(b.t * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})
        : new Date(b.t * 1000).toLocaleDateString([], {month:'short', day:'numeric'}),
    }));

    const candleW = Math.max(1, cw / bars.length * 0.7);

    return (
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {yTicks.map((v, i) => (
          <line key={i} x1={PL} x2={W-PR} y1={y(v)} y2={y(v)}
            stroke="var(--border)" strokeWidth="0.5" strokeDasharray="3,3" />
        ))}
        {prevClose && prevClose >= minP && prevClose <= maxP && (
          <line x1={PL} x2={W-PR} y1={y(prevClose)} y2={y(prevClose)}
            stroke="var(--muted)" strokeWidth="0.8" strokeDasharray="4,2" />
        )}

        {isCandle ? (
          bars.map((b, i) => {
            const cx = x(i);
            const candleUp = b.c >= b.o;
            const cColor = candleUp ? '#22c55e' : '#ef4444';
            const bodyTop = y(Math.max(b.o, b.c));
            const bodyBot = y(Math.min(b.o, b.c));
            const bodyH = Math.max(1, bodyBot - bodyTop);
            return (
              <g key={i}>
                <line x1={cx} x2={cx} y1={y(b.h || b.c)} y2={y(b.l || b.c)}
                  stroke={cColor} strokeWidth="1" />
                <rect x={cx - candleW/2} y={bodyTop} width={candleW} height={bodyH}
                  fill={candleUp ? cColor : cColor} fillOpacity={candleUp ? 0.85 : 1}
                  stroke={cColor} strokeWidth="0.5" />
              </g>
            );
          })
        ) : (
          <>
            <path d={areaPath} fill={`url(#${fillId})`} />
            <polyline points={linePts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
          </>
        )}

        {yTicks.map((v, i) => (
          <text key={i} x={PL - 4} y={y(v) + 3} textAnchor="end"
            fontSize="9" fill="var(--muted)" fontFamily="var(--mono)">
            {v >= 1000 ? v.toFixed(0) : v.toFixed(2)}
          </text>
        ))}
        {xTicks.map((t, i) => (
          <text key={i} x={t.x} y={H - 4} textAnchor="middle"
            fontSize="8" fill="var(--muted)" fontFamily="var(--mono)">
            {t.label}
          </text>
        ))}
      </svg>
    );
  }

  function PnlHistoryChart({ rows }) {
    const { useEffect: useEff, useRef: useRefH, useMemo: useMemoH } = React;

    // Load + update history
    const hist = useMemoH(() => {
      const today = new Date().toISOString().slice(0, 10);
      let h = {};
      try { h = JSON.parse(localStorage.getItem('delta_pfl_history') || '{}'); } catch(e) {}
      // Record today's value if positions exist
      const total = rows.reduce((s, r) => s + (r.mktVal || 0), 0);
      if (total > 0 && rows.length > 0) {
        h[today] = total;
        try { localStorage.setItem('delta_pfl_history', JSON.stringify(h)); } catch(e) {}
      }
      return Object.entries(h).sort((a,b)=>a[0].localeCompare(b[0])).slice(-90);
    }, [rows]);

    if (hist.length < 2) return null;

    const W = 600, H = 100, PL = 60, PR = 8, PT = 8, PB = 20;
    const cw = W - PL - PR, ch = H - PT - PB;
    const vals = hist.map(([,v]) => v);
    const minV = Math.min(...vals) * 0.995, maxV = Math.max(...vals) * 1.005;
    const range = maxV - minV || maxV * 0.001;
    const x = (i) => PL + (i / (hist.length - 1)) * cw;
    const y = (v) => PT + ch - ((v - minV) / range) * ch;

    const first = vals[0], last = vals[vals.length-1];
    const up = last >= first;
    const color = up ? 'var(--mint)' : 'var(--rose)';
    const fillId = `pf${Math.random().toString(36).slice(2,6)}`;
    const linePts = hist.map(([,v], i) => `${x(i)},${y(v)}`).join(' ');
    const areaPath = `M${x(0)},${y(vals[0])} ` + hist.slice(1).map(([,v],i) => `L${x(i+1)},${y(v)}`).join(' ')
      + ` L${x(hist.length-1)},${PT+ch} L${x(0)},${PT+ch} Z`;

    const yTicks = [minV, (minV+maxV)/2, maxV];
    const fmt = v => v >= 1e6 ? '$'+(v/1e6).toFixed(2)+'M' : '$'+(v/1e3).toFixed(1)+'K';

    // X ticks: first, mid, last
    const xMarks = [0, Math.floor(hist.length/2), hist.length-1];

    return (
      <div style={{ borderTop: '1px solid var(--border)', padding: '4px 0 0' }}>
        <div style={{ fontSize: 9, color: 'var(--muted)', padding: '0 8px 2px', display: 'flex', justifyContent: 'space-between' }}>
          <span>PORTFOLIO VALUE · {hist.length} DAYS</span>
          <span style={{ color: up ? 'var(--mint)' : 'var(--rose)' }}>
            {up ? '+' : ''}{(((last-first)/first)*100).toFixed(2)}% vs {hist[0][0]}
          </span>
        </div>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <path d={areaPath} fill={`url(#${fillId})`} />
          <polyline points={linePts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
          {yTicks.map((v, i) => (
            <text key={i} x={PL-4} y={y(v)+3} textAnchor="end" fontSize="8" fill="var(--muted)" fontFamily="var(--mono)">{fmt(v)}</text>
          ))}
          {xMarks.map((idx) => (
            <text key={idx} x={x(idx)} y={H-3} textAnchor="middle" fontSize="7.5" fill="var(--muted)" fontFamily="var(--mono)">{hist[idx][0].slice(5)}</text>
          ))}
        </svg>
      </div>
    );
  }

  function ChartsPanel({ snap }) {
    const charts = snap.charts || { intraday: {}, daily: {} };
    const polygonData = snap.polygonData || { bars: {}, fundamentals: {} };
    const allQuotes = [...(snap.indices||[]), ...(snap.tech||[]), ...(snap.macro||[])];
    const SYMBOLS = Object.keys(charts.intraday).length
      ? Object.keys(charts.intraday)
      : ['SPY','AAPL','MSFT','NVDA','TSLA','META','AMZN','AMD','GOOGL','QQQ','GLD','TLT','XLK','XLE'];

    const [sel, setSel] = useState(SYMBOLS[0] || 'SPY');
    const [mode, setMode] = useState('INTRADAY');
    const [chartType, setChartType] = useState('LINE');
    const [view, setView] = useState('CHART');

    // Use Polygon bars for daily when available, fall back to yfinance
    const bars = mode === 'INTRADAY'
      ? (charts.intraday[sel] || [])
      : (polygonData.bars[sel] || charts.daily[sel] || []);
    const fundData = polygonData.fundamentals[sel] || null;
    const quote = allQuotes.find(q => q.ticker === sel);
    const last = bars.length ? bars[bars.length - 1].c : null;
    const prevClose = quote ? (quote.price - quote.change) : (bars.length > 1 ? bars[0].c : null);
    const chgPct = prevClose && last ? ((last - prevClose) / prevClose * 100) : null;
    const chgColor = chgPct == null ? 'var(--muted)' : chgPct >= 0 ? 'var(--mint)' : 'var(--rose)';

    function TabBtn({ label, active, onClick }) {
      return (
        <button onClick={onClick}
          style={{ padding: '2px 10px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
            border: '1px solid', letterSpacing: '.06em',
            borderColor: active ? 'var(--cyan)' : 'var(--border-2)',
            background: active ? 'rgba(56,189,248,.12)' : 'transparent',
            color: active ? 'var(--cyan)' : 'var(--text-2)' }}>
          {label}
        </button>
      );
    }

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', gap: 6, minHeight: 0 }}>
        {/* Symbol list */}
        <div className="panel" style={{ width: 100, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="SYMBOLS" />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {SYMBOLS.map(sym => {
              const q = allQuotes.find(r => r.ticker === sym);
              const pct = q ? q.change_pct : null;
              return (
                <div key={sym} onClick={() => setSel(sym)}
                  style={{ padding: '5px 8px', cursor: 'pointer', borderBottom: '1px solid var(--border)',
                    background: sel === sym ? 'rgba(56,189,248,.08)' : 'transparent',
                    borderLeft: sel === sym ? '2px solid var(--cyan)' : '2px solid transparent' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: sel === sym ? 'var(--cyan)' : 'var(--text)' }}>{sym}</div>
                  {pct != null && (
                    <div style={{ fontSize: 9, color: pct >= 0 ? 'var(--mint)' : 'var(--rose)' }}>
                      {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Chart / Company area */}
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border)', flexShrink: 0, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '.05em' }}>{sel}</span>
            {fundData && <span style={{ fontSize: 10, color: 'var(--muted)' }}>{fundData.name}</span>}
            {last != null && <span style={{ fontSize: 18, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>${last.toFixed(2)}</span>}
            {chgPct != null && <span style={{ fontSize: 12, color: chgColor, fontWeight: 600 }}>{chgPct >= 0 ? '+' : ''}{chgPct.toFixed(2)}%</span>}
            <div style={{ flex: 1 }} />
            <TabBtn label="CHART"   active={view==='CHART'}   onClick={() => setView('CHART')} />
            {fundData && <TabBtn label="COMPANY" active={view==='COMPANY'} onClick={() => setView('COMPANY')} />}
            {view === 'CHART' && <>
              <div style={{ width: 1, background: 'var(--border)', height: 16 }} />
              <TabBtn label="INTRADAY" active={mode==='INTRADAY'} onClick={() => setMode('INTRADAY')} />
              <TabBtn label="1 YEAR"   active={mode==='DAILY'}    onClick={() => setMode('DAILY')} />
              <div style={{ width: 1, background: 'var(--border)', height: 16 }} />
              <TabBtn label="LINE"   active={chartType==='LINE'}   onClick={() => setChartType('LINE')} />
              <TabBtn label="CANDLE" active={chartType==='CANDLE'} onClick={() => setChartType('CANDLE')} />
            </>}
          </div>

          {view === 'CHART' ? (
            bars.length > 1 ? (
              <div style={{ flex: 1, padding: '8px 4px', minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <SvgChart bars={bars} mode={mode} prevClose={prevClose} chartType={chartType} />
                <div style={{ display: 'flex', gap: 16, padding: '4px 52px', fontSize: 10, color: 'var(--muted)' }}>
                  {[['O', bars[bars.length-1].o], ['H', bars[bars.length-1].h], ['L', bars[bars.length-1].l], ['C', bars[bars.length-1].c]].map(([k,v]) => (
                    <span key={k}><span style={{ color: 'var(--text-2)' }}>{k}</span> {v?.toFixed(2)}</span>
                  ))}
                  <span><span style={{ color: 'var(--text-2)' }}>VOL</span> {bars[bars.length-1].v?.toLocaleString()}</span>
                  {mode === 'DAILY' && polygonData.bars[sel] && <span style={{ color: 'var(--cyan)', fontSize: 9 }}>● POLYGON</span>}
                </div>
              </div>
            ) : (
              <Empty msg={`Loading ${sel} chart data…`} />
            )
          ) : (
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {fundData ? (() => {
                const fmtMkt = v => {
                  if (!v) return '—';
                  if (v >= 1e12) return '$' + (v/1e12).toFixed(2) + 'T';
                  if (v >= 1e9)  return '$' + (v/1e9).toFixed(1) + 'B';
                  return '$' + (v/1e6).toFixed(0) + 'M';
                };
                const rows = [
                  ['Full Name',       fundData.name],
                  ['Exchange',        fundData.primary_exchange],
                  ['Type',            fundData.type],
                  ['SIC',             fundData.sic_description],
                  ['Market Cap',      fmtMkt(fundData.market_cap)],
                  ['Employees',       fundData.total_employees?.toLocaleString()],
                  ['Shares Out',      fundData.weighted_shares_outstanding ? (fundData.weighted_shares_outstanding/1e6).toFixed(1)+'M' : null],
                  ['Listed',          fundData.list_date],
                  ['CIK',             fundData.cik],
                  ['Homepage',        fundData.homepage_url],
                  ['HQ',              fundData.address ? `${fundData.address.city}, ${fundData.address.state}` : null],
                ].filter(([,v]) => v);
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                      {[['Market Cap', fmtMkt(fundData.market_cap)], ['Employees', fundData.total_employees?.toLocaleString()], ['Exchange', fundData.primary_exchange]].map(([k,v]) => v && (
                        <div key={k} style={{ background: 'var(--surface-2)', border: '1px solid var(--border-2)', padding: '8px 14px', minWidth: 100 }}>
                          <div style={{ fontSize: 9, color: 'var(--muted)', letterSpacing: '.06em', marginBottom: 4 }}>{k}</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--cyan)' }}>{v}</div>
                        </div>
                      ))}
                    </div>
                    {fundData.description && (
                      <div style={{ fontSize: 11, color: 'var(--text-2)', lineHeight: 1.6, maxWidth: 700 }}>
                        {fundData.description}
                      </div>
                    )}
                    <table style={{ fontSize: 11, borderCollapse: 'collapse', width: '100%', maxWidth: 500 }}>
                      <tbody>
                        {rows.map(([k, v]) => (
                          <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: '5px 8px', color: 'var(--muted)', whiteSpace: 'nowrap', width: 140 }}>{k}</td>
                            <td style={{ padding: '5px 8px', color: 'var(--text)' }}>
                              {k === 'Homepage'
                                ? <span style={{ color: 'var(--cyan)', cursor: 'pointer' }} onClick={() => window.open(v, '_blank')}>{v}</span>
                                : v}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <div style={{ fontSize: 9, color: 'var(--muted)' }}>SOURCE: POLYGON.IO / MASSIVE.COM</div>
                  </div>
                );
              })() : <Empty msg="No company data available" />}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Dark Pool Panel ───────────────────────────────────────────────────────────
  function DarkpoolPanel({ snap }) {
    const dp = snap.darkpool || { prints: [], ats_vol: [] };
    const [tab, setTab] = useState('PRINTS');
    const [filter, setFilter] = useState('');
    const fl = filter.toLowerCase();

    const prints = (snap.optionsFlow?.unusual || [])
      .filter(u => (u.premium_k || 0) >= 50)
      .map(u => ({
        ticker:    u.ticker,
        type:      u.type === 'C' ? 'CALL' : 'PUT',
        strike:    u.strike,
        expiry:    u.expiry,
        volume:    u.volume,
        premium_k: u.premium_k,
        value:     (u.premium_k || 0) * 1000,
        iv_pct:    u.iv_pct,
        itm:       u.itm,
      }))
      .sort((a, b) => b.premium_k - a.premium_k)
      .filter(r => !fl || (r.ticker||'').toLowerCase().includes(fl));
    const ats = (dp.ats_vol || []).filter(r =>
      !fl || (r.symbol||'').toLowerCase().includes(fl) || (r.name||'').toLowerCase().includes(fl)
    );

    const fmtVal = v => {
      if (!v) return '—';
      if (v >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
      if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
      return '$' + (v / 1e3).toFixed(0) + 'K';
    };
    const fmtShares = v => {
      if (!v) return '—';
      if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
      if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
      return v.toLocaleString();
    };

    const tabs = [
      { k: 'PRINTS', label: `BLOCK PRINTS (${prints.length})` },
      { k: 'ATS',    label: `SHORT VOLUME (${ats.length})` },
    ];

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ padding: '6px 10px', display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
          <span style={{ color: 'var(--cyan)', fontSize: 11, letterSpacing: '.1em', fontWeight: 700 }}>◆ DARK POOL</span>
          {tabs.map(t => (
            <button key={t.k} onClick={() => setTab(t.k)}
              style={{ padding: '2px 10px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
                letterSpacing: '.06em', border: '1px solid', fontWeight: tab === t.k ? 700 : 400,
                borderColor: tab === t.k ? 'var(--cyan)' : 'var(--border-2)',
                background: tab === t.k ? 'rgba(56,189,248,.12)' : 'transparent',
                color: tab === t.k ? 'var(--cyan)' : 'var(--text-2)' }}>
              {t.label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <Filter value={filter} onChange={setFilter} placeholder="filter ticker…" />
        </div>

        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title={tab === 'PRINTS' ? 'LARGE BLOCK PRINTS · OPTIONS FLOW' : 'FINRA REGSHO · SHORT SALE VOLUME'}
            meta={tab === 'PRINTS' ? 'Institutional options activity $50K+ premium' : 'FINRA RegSho daily — api.finra.org'} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {tab === 'PRINTS' ? (
              prints.length === 0 ? <Empty msg="Loading block prints… (options flow must load first)" /> : (
                <table className="dense">
                  <thead><tr>
                    <th>TICKER</th><th>TYPE</th><th>STRIKE</th><th>EXPIRY</th>
                    <th className="num">VOLUME</th><th className="num">PREMIUM</th>
                    <th className="num">IV%</th><th>ITM</th>
                  </tr></thead>
                  <tbody>
                    {prints.map((r, i) => (
                      <tr key={i}>
                        <td className="lbl" style={{ fontWeight: 700 }}>{r.ticker}</td>
                        <td><span className={'pill ' + (r.type === 'CALL' ? 'pill-mint' : 'pill-rose')} style={{ fontSize: 9 }}>{r.type}</span></td>
                        <td className="num">${r.strike?.toFixed(0)}</td>
                        <td className="mut" style={{ fontSize: 10 }}>{r.expiry}</td>
                        <td className="num">{r.volume?.toLocaleString()}</td>
                        <td className="num" style={{ color: 'var(--cyan)', fontWeight: 600 }}>{fmtVal(r.value)}</td>
                        <td className="num">{r.iv_pct?.toFixed(1)}%</td>
                        <td style={{ fontSize: 9, color: r.itm ? 'var(--mint)' : 'var(--muted)' }}>{r.itm ? 'ITM' : 'OTM'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            ) : (
              ats.length === 0 ? <Empty msg="Loading FINRA short sale data…" /> : (
                <table className="dense">
                  <thead><tr>
                    <th>SYMBOL</th><th className="num">TOTAL VOL</th>
                    <th className="num">SHORT VOL</th><th className="num">SHORT%</th>
                    <th className="num">EXEMPT</th><th>DATE</th>
                  </tr></thead>
                  <tbody>
                    {ats.map((r, i) => (
                      <tr key={i}>
                        <td className="lbl" style={{ fontWeight: 700 }}>{r.symbol}</td>
                        <td className="num">{fmtShares(r.total)}</td>
                        <td className="num">{fmtShares(r.short)}</td>
                        <td className="num" style={{ color: r.short_pct > 50 ? 'var(--rose)' : r.short_pct > 35 ? 'var(--amber)' : 'var(--mint)', fontWeight: 600 }}>{r.short_pct?.toFixed(1)}%</td>
                        <td className="num mut">{fmtShares(r.exempt)}</td>
                        <td className="mut" style={{ fontSize: 10 }}>{r.date}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Block prints derived from unusual options flow · Short volume via FINRA RegSho · NOT FINANCIAL ADVICE
          </div>
        </div>
      </div>
    );
  }

  // ── Crypto Panel (CoinMarketCap) ──────────────────────────────────────────────
  function CryptoPanel({ snap }) {
    const coins = snap.cmcCoins || [];
    const [filter, setFilter] = useState('');
    const fl = filter.toLowerCase();

    const fmtPrice = p => {
      if (p == null) return '—';
      if (p >= 1000) return '$' + p.toLocaleString(undefined, { maximumFractionDigits: 0 });
      if (p >= 1)    return '$' + p.toFixed(2);
      if (p >= 0.01) return '$' + p.toFixed(4);
      return '$' + p.toFixed(6);
    };
    const fmtBig = v => {
      if (!v) return '—';
      if (v >= 1e12) return '$' + (v/1e12).toFixed(2) + 'T';
      if (v >= 1e9)  return '$' + (v/1e9).toFixed(1) + 'B';
      if (v >= 1e6)  return '$' + (v/1e6).toFixed(0) + 'M';
      return '$' + v.toFixed(0);
    };
    const pctCell = v => {
      if (v == null) return <td style={{ padding: '5px 8px', color: 'var(--muted)' }}>—</td>;
      const c = v >= 0 ? 'var(--mint)' : 'var(--rose)';
      return <td style={{ padding: '5px 8px', color: c, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}%</td>;
    };

    const rows = fl
      ? coins.filter(c => c.symbol.toLowerCase().includes(fl) || c.name.toLowerCase().includes(fl))
      : coins;

    if (!coins.length) return <Empty msg="Loading crypto data…" />;

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="CRYPTO" meta={`TOP ${coins.length} · COINMARKETCAP · 5 MIN`}
            right={<Filter value={filter} onChange={setFilter} placeholder="filter…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ position: 'sticky', top: 0, background: 'var(--bg-2)', zIndex: 1 }}>
                  {['#','SYMBOL','NAME','PRICE','1H%','24H%','7D%','MKT CAP','VOL 24H','DOMINANCE'].map(h => (
                    <th key={h} style={{ padding: '4px 8px', textAlign: h === '#' || h === 'SYMBOL' ? 'left' : 'right',
                      fontSize: 9, color: 'var(--muted)', letterSpacing: '.06em', fontWeight: 600,
                      borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(c => (
                  <tr key={c.symbol} style={{ borderBottom: '1px solid var(--border)', cursor: 'default' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'rgba(56,189,248,.04)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '5px 8px', color: 'var(--muted)', fontSize: 10 }}>{c.rank}</td>
                    <td style={{ padding: '5px 8px', fontWeight: 700, color: 'var(--cyan)', letterSpacing: '.04em' }}>{c.symbol}</td>
                    <td style={{ padding: '5px 8px', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{c.name}</td>
                    <td style={{ padding: '5px 8px', fontWeight: 600, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{fmtPrice(c.price)}</td>
                    {pctCell(c.change_1h)}
                    {pctCell(c.change_24h)}
                    {pctCell(c.change_7d)}
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: 'var(--text-2)', fontVariantNumeric: 'tabular-nums' }}>{fmtBig(c.market_cap)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: 'var(--text-2)', fontVariantNumeric: 'tabular-nums' }}>{fmtBig(c.volume_24h)}</td>
                    <td style={{ padding: '5px 8px', textAlign: 'right', color: 'var(--muted)', fontVariantNumeric: 'tabular-nums' }}>
                      {c.dominance != null ? c.dominance.toFixed(2) + '%' : '—'}
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

  // ── THR — CISA Threat Intelligence ───────────────────────────────────────────
  function ThreatPanel({ snap }) {
    const { advisories } = snap.threats || { advisories: [] };
    const [filter, setFilter] = useState('ALL');

    const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
    const sevColor = s => ({
      CRITICAL: 'var(--rose)', HIGH: 'var(--amber)', MEDIUM: 'var(--cyan)',
      LOW: 'var(--text-2)', INFO: 'var(--muted)',
    }[s] || 'var(--muted)');

    const levels = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
    const filtered = advisories
      .filter(a => filter === 'ALL' || a.severity === filter)
      .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9));

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="CYBER THREAT ADVISORIES" meta={`${filtered.length} ADVISORIES · CISA`}
            right={
              <div style={{ display: 'flex', gap: 3 }}>
                {levels.map(l => (
                  <button key={l} onClick={() => setFilter(l)} style={{
                    padding: '1px 7px', fontSize: 9, fontFamily: 'var(--mono)', cursor: 'pointer',
                    border: '1px solid', letterSpacing: '.05em',
                    borderColor: filter === l ? sevColor(l === 'ALL' ? 'MEDIUM' : l) : 'var(--border-2)',
                    background: filter === l ? 'rgba(56,189,248,.08)' : 'transparent',
                    color: filter === l ? sevColor(l === 'ALL' ? 'MEDIUM' : l) : 'var(--text-2)',
                  }}>{l}</button>
                ))}
              </div>
            } />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg="Loading threat advisories…" /> : (
              <table className="dense">
                <thead><tr>
                  <th>DATE</th>
                  <th>SEV</th>
                  <th>SOURCE</th>
                  <th>ADVISORY</th>
                </tr></thead>
                <tbody>
                  {filtered.map((a, i) => (
                    <tr key={i}>
                      <td className="mut" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{a.date}</td>
                      <td style={{ fontWeight: 600, color: sevColor(a.severity), whiteSpace: 'nowrap', fontSize: 10 }}>
                        {a.severity}
                      </td>
                      <td className="mut" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{a.source}</td>
                      <td style={{ fontSize: 11, maxWidth: 500 }}>{a.title}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ padding: '6px 10px', borderTop: '1px solid var(--border)', fontSize: 9, color: 'var(--muted)' }}>
            Source: CISA Cybersecurity Advisories · US Dept of Homeland Security · Updates every 30 min
          </div>
        </div>
      </div>
    );
  }

  // ── OCN — Sea Ice & Ocean ─────────────────────────────────────────────────────
  function SparkLine({ trend, color }) {
    if (!trend || trend.length < 2) return null;
    const W = 220, H = 40, PL = 4, PR = 4, PT = 4, PB = 4;
    const cw = W - PL - PR, ch = H - PT - PB;
    const vals = trend.map(r => r.extent);
    const mn = Math.min(...vals), mx = Math.max(...vals);
    const rng = mx - mn || 0.001;
    const x = i => PL + (i / (trend.length - 1)) * cw;
    const y = v => PT + ch - ((v - mn) / rng) * ch;
    const pts = trend.map((r, i) => `${x(i).toFixed(1)},${y(r.extent).toFixed(1)}`).join(' ');
    return (
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
        <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    );
  }

  function OceanPanel({ snap }) {
    const ocean = snap.ocean || {
      arctic:    { extent: null, date: '', anomaly: null, trend: [] },
      antarctic: { extent: null, date: '', anomaly: null, trend: [] },
    };
    const { arctic, antarctic } = ocean;

    const fmtExt = v => v != null ? v.toFixed(3) + ' M km²' : '—';
    const fmtAno = v => {
      if (v == null) return '—';
      return (v >= 0 ? '+' : '') + v.toFixed(3) + ' M km²';
    };
    const anomalyColor = v => v == null ? 'var(--muted)' : v < 0 ? 'var(--rose)' : 'var(--mint)';

    const arcticTrend = arctic.trend.length >= 2
      ? (() => {
          const first = arctic.trend[0].extent, last = arctic.trend[arctic.trend.length - 1].extent;
          return { dir: last > first ? 'up' : 'down', delta: (last - first).toFixed(3) };
        })() : null;
    const antarTrend = antarctic.trend.length >= 2
      ? (() => {
          const first = antarctic.trend[0].extent, last = antarctic.trend[antarctic.trend.length - 1].extent;
          return { dir: last > first ? 'up' : 'down', delta: (last - first).toFixed(3) };
        })() : null;

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Summary tiles */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { label: 'ARCTIC EXTENT',     value: fmtExt(arctic.extent),    date: arctic.date,    anomaly: arctic.anomaly,    color: 'var(--cyan)', trend: arcticTrend },
            { label: 'ANTARCTIC EXTENT',  value: fmtExt(antarctic.extent), date: antarctic.date, anomaly: antarctic.anomaly, color: 'var(--violet)', trend: antarTrend },
          ].map(item => (
            <div key={item.label} className="panel" style={{ flex: 1, padding: '12px 16px' }}>
              <div className="mut" style={{ fontSize: 9, letterSpacing: '.1em', marginBottom: 4 }}>{item.label}</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: item.color, fontVariantNumeric: 'tabular-nums' }}>
                {item.value}
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 4, alignItems: 'center' }}>
                <span className="mut" style={{ fontSize: 9 }}>AS OF {item.date || '—'}</span>
                {item.anomaly != null && (
                  <span style={{ fontSize: 10, color: anomalyColor(item.anomaly), fontWeight: 600 }}>
                    ANOM {fmtAno(item.anomaly)}
                  </span>
                )}
                {item.trend && (
                  <span style={{ fontSize: 10, color: item.trend.dir === 'up' ? 'var(--mint)' : 'var(--rose)' }}>
                    {item.trend.dir === 'up' ? '▲' : '▼'} {Math.abs(item.trend.delta)} M km² (60d)
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Charts */}
        <div style={{ display: 'flex', gap: 6, flex: 1, minHeight: 0 }}>
          {[
            { label: 'ARCTIC SEA ICE · 60-DAY TREND', data: arctic,    color: 'var(--cyan)',   clim_label: '1981–2010 median Arctic' },
            { label: 'ANTARCTIC SEA ICE · 60-DAY TREND', data: antarctic, color: 'var(--violet)', clim_label: '1981–2010 median Antarctic' },
          ].map(item => (
            <div key={item.label} className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              <PH title={item.label} meta={item.data.trend.length + ' DAYS'} />
              <div style={{ flex: 1, padding: '8px 4px', minHeight: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                {item.data.trend.length < 2 ? <Empty /> : (() => {
                  const rows = item.data.trend;
                  const W = 560, H = 160, PL = 52, PR = 8, PT = 10, PB = 28;
                  const cw = W - PL - PR, ch = H - PT - PB;
                  const vals = rows.map(r => r.extent);
                  const mn = Math.min(...vals) * 0.99, mx = Math.max(...vals) * 1.01;
                  const rng = mx - mn || 0.001;
                  const x = i => PL + (i / (rows.length - 1)) * cw;
                  const y = v => PT + ch - ((v - mn) / rng) * ch;
                  const pts = rows.map((r, i) => `${x(i).toFixed(1)},${y(r.extent).toFixed(1)}`).join(' ');
                  const area = `M${x(0).toFixed(1)},${y(rows[0].extent).toFixed(1)} `
                    + rows.slice(1).map((r, i) => `L${x(i+1).toFixed(1)},${y(r.extent).toFixed(1)}`).join(' ')
                    + ` L${x(rows.length-1).toFixed(1)},${PT+ch} L${x(0).toFixed(1)},${PT+ch} Z`;
                  const yTicks = [mn, (mn+mx)/2, mx];
                  const xTicks = [0, Math.floor(rows.length/2), rows.length-1].map(idx => ({ x: x(idx), label: rows[idx].date.slice(5) }));
                  const fillId = 'ocean_' + item.label[0];
                  return (
                    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
                      <defs>
                        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={item.color} stopOpacity="0.25" />
                          <stop offset="100%" stopColor={item.color} stopOpacity="0.02" />
                        </linearGradient>
                      </defs>
                      {yTicks.map((v, i) => (
                        <line key={i} x1={PL} x2={W-PR} y1={y(v)} y2={y(v)}
                          stroke="var(--border)" strokeWidth="0.5" strokeDasharray="3,3" />
                      ))}
                      <path d={area} fill={`url(#${fillId})`} />
                      <polyline points={pts} fill="none" stroke={item.color} strokeWidth="1.5" strokeLinejoin="round" />
                      {yTicks.map((v, i) => (
                        <text key={i} x={PL-4} y={y(v)+3} textAnchor="end" fontSize="9" fill="var(--muted)" fontFamily="var(--mono)">{v.toFixed(2)}</text>
                      ))}
                      {xTicks.map((t, i) => (
                        <text key={i} x={t.x} y={H-4} textAnchor="middle" fontSize="8" fill="var(--muted)" fontFamily="var(--mono)">{t.label}</text>
                      ))}
                    </svg>
                  );
                })()}
              </div>
              <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
                Source: NSIDC Sea Ice Index v4 · NOAA/NASA · Anomaly vs 1981–2010 climatological median
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── TRD — Global Trade ────────────────────────────────────────────────────────
  function TradePanel({ snap }) {
    const tradeData = snap.trade || { countries: [] };
    const rows = tradeData.countries || [];
    const [filter, setFilter] = useState('');
    const [sortCol, setSortCol] = useState('exports_bn');
    const [sortDir, setSortDir] = useState('desc');

    const toggleSort = col => {
      if (col === sortCol) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
      else { setSortCol(col); setSortDir('desc'); }
    };

    const fmtBn = v => {
      if (v == null) return '—';
      const abs = Math.abs(v);
      if (abs >= 1000) return (v < 0 ? '-' : '') + '$' + (abs / 1000).toFixed(2) + 'T';
      return (v < 0 ? '-$' : '$') + abs.toFixed(0) + 'B';
    };
    const balColor = v => v == null ? 'var(--muted)' : v >= 0 ? 'var(--mint)' : 'var(--rose)';

    const fl = filter.toLowerCase();
    const filtered = rows
      .filter(r => !fl || r.country.toLowerCase().includes(fl) || r.iso.toLowerCase().includes(fl))
      .sort((a, b) => {
        const av = a[sortCol], bv = b[sortCol];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return sortDir === 'asc' ? av - bv : bv - av;
      });

    const totalExp = rows.reduce((s, r) => s + (r.exports_bn || 0), 0);
    const totalImp = rows.reduce((s, r) => s + (r.imports_bn || 0), 0);

    const SortTh = ({ col, children }) => (
      <th onClick={() => toggleSort(col)} style={{ cursor: 'pointer', textAlign: 'right' }}>
        {children}{sortCol === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
      </th>
    );

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Summary tiles */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            ['TOTAL EXPORTS',  fmtBn(totalExp)],
            ['TOTAL IMPORTS',  fmtBn(totalImp)],
            ['NET BALANCE',    fmtBn(totalExp - totalImp)],
            ['COUNTRIES',      filtered.length],
          ].map(([l, v]) => (
            <div key={l} className="panel" style={{ flex: 1, padding: '8px 12px' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 2 }}>{l}</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--cyan)' }}>{v}</div>
            </div>
          ))}
        </div>

        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="WORLD TRADE BY COUNTRY"
            meta={`${filtered.length} COUNTRIES · WORLD BANK`}
            right={<Filter value={filter} onChange={setFilter} placeholder="search country…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg="Loading trade data…" /> : (
              <table className="dense">
                <thead><tr>
                  <th style={{ width: 36 }}>#</th>
                  <th>COUNTRY</th>
                  <th style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'center' }}>ISO</th>
                  <SortTh col="exports_bn">EXPORTS</SortTh>
                  <SortTh col="imports_bn">IMPORTS</SortTh>
                  <SortTh col="balance_bn">BALANCE</SortTh>
                  <th className="num">YR</th>
                </tr></thead>
                <tbody>
                  {filtered.map((r, i) => {
                    const maxExp = filtered[0]?.exports_bn || 1;
                    return (
                      <tr key={r.iso}>
                        <td className="mut" style={{ fontSize: 9, width: 30 }}>{i + 1}</td>
                        <td className="lbl" style={{ fontWeight: 600 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: Math.max(2, ((r.exports_bn || 0) / maxExp) * 50), height: 6, background: 'var(--cyan)', opacity: 0.6, borderRadius: 1, flexShrink: 0 }} />
                            {r.country}
                          </div>
                        </td>
                        <td className="mut" style={{ fontSize: 9, textAlign: 'center' }}>{r.iso}</td>
                        <td className="num" style={{ fontWeight: 600 }}>{fmtBn(r.exports_bn)}</td>
                        <td className="num">{fmtBn(r.imports_bn)}</td>
                        <td className="num" style={{ color: balColor(r.balance_bn), fontWeight: r.balance_bn != null ? 600 : 400 }}>
                          {r.balance_bn != null ? (r.balance_bn >= 0 ? '+' : '') + fmtBn(r.balance_bn) : '—'}
                        </td>
                        <td className="num mut" style={{ fontSize: 9 }}>{r.year}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: World Bank Open Data · Exports + Imports of Goods &amp; Services (NE.EXP/IMP.GNFS.CD) · Annual
          </div>
        </div>
      </div>
    );
  }

  // ── ELE — Elections Calendar ──────────────────────────────────────────────────
  function ElectionsPanel({ snap }) {
    const electionsData = snap.elections || { elections: [] };
    const all = electionsData.elections || [];
    const [filter, setFilter] = useState('');
    const [yearFilter, setYearFilter] = useState('2026');

    const years = [...new Set(all.map(e => e.year).filter(Boolean))].sort();

    const fl = filter.toLowerCase();
    const filtered = all.filter(e => {
      if (yearFilter !== 'ALL' && e.year !== yearFilter) return false;
      if (!fl) return true;
      return e.country.toLowerCase().includes(fl) || e.type.toLowerCase().includes(fl);
    });

    // Group by month
    const byMonth = {};
    for (const e of filtered) {
      const month = e.date ? e.date.slice(0, 7) : 'Unknown';
      if (!byMonth[month]) byMonth[month] = [];
      byMonth[month].push(e);
    }
    const months = Object.keys(byMonth).sort();

    // Stats
    const upcoming = filtered.filter(e => e.date >= new Date().toISOString().slice(0, 10));
    const past     = filtered.filter(e => e.date && e.date < new Date().toISOString().slice(0, 10));

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Stat tiles */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            ['UPCOMING',   upcoming.length],
            ['PAST',       past.length],
            ['TOTAL',      filtered.length],
            ['COUNTRIES',  new Set(filtered.map(e => e.country)).size],
          ].map(([l, v]) => (
            <div key={l} className="panel" style={{ flex: 1, padding: '8px 12px' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 2 }}>{l}</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--cyan)' }}>{v}</div>
            </div>
          ))}
        </div>

        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="ELECTION CALENDAR 2025–2026"
            meta={`${filtered.length} ELECTIONS · WIKIDATA`}
            right={
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {['ALL', ...(years.length <= 4 ? years : ['2025', '2026'])].map(y => (
                  <button key={y} className={`btn${yearFilter === y ? ' on' : ''}`}
                    onClick={() => setYearFilter(y)} style={{ padding: '1px 6px', fontSize: 10 }}>{y}</button>
                ))}
                <Filter value={filter} onChange={setFilter} placeholder="country / type…" />
              </div>
            } />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg="Loading election calendar…" /> :
              months.map(month => {
                const monthElections = byMonth[month];
                const today = new Date().toISOString().slice(0, 10);
                return (
                  <div key={month}>
                    <div style={{ padding: '4px 8px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)',
                      fontSize: 10, fontWeight: 700, color: 'var(--cyan)', letterSpacing: '.1em', position: 'sticky', top: 0, zIndex: 1 }}>
                      {new Date(month + '-01').toLocaleString('en-US', { month: 'long', year: 'numeric' })}
                      <span className="mut" style={{ fontWeight: 400, marginLeft: 8 }}>{monthElections.length} elections</span>
                    </div>
                    {monthElections.map((e, i) => {
                      const isPast = e.date < today;
                      return (
                        <div key={i} style={{
                          padding: '6px 10px', borderBottom: '1px solid var(--border)',
                          display: 'flex', alignItems: 'center', gap: 12,
                          opacity: isPast ? 0.65 : 1,
                          background: !isPast && e.date === today ? 'rgba(56,189,248,.06)' : 'transparent',
                        }}>
                          <span style={{ fontVariantNumeric: 'tabular-nums', fontSize: 11, color: 'var(--muted)', minWidth: 80 }}>
                            {e.date}
                          </span>
                          <span style={{ fontWeight: 700, color: 'var(--cyan)', minWidth: 160 }}>
                            {e.country}
                          </span>
                          <span style={{ fontSize: 10, color: 'var(--text-2)', flex: 1 }}>
                            {e.type}
                          </span>
                          {isPast && <span className="mut" style={{ fontSize: 9, letterSpacing: '.06em' }}>PAST</span>}
                          {!isPast && e.date === today && <span style={{ color: 'var(--amber)', fontSize: 9, fontWeight: 700 }}>TODAY</span>}
                          {e.wiki && (
                            <a href={e.wiki} target="_blank" rel="noreferrer"
                              style={{ color: 'var(--muted)', fontSize: 9, textDecoration: 'none' }}
                              onMouseEnter={e => e.currentTarget.style.color = 'var(--cyan)'}
                              onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}>
                              WP ↗
                            </a>
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })
            }
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: Wikidata · CC0 · National elections only (excludes regional, by-elections) · WP = Wikipedia article
          </div>
        </div>
      </div>
    );
  }

  // ── LEK — Data Breach Catalog (HIBP) ─────────────────────────────────────────
  function LeaksPanel({ snap }) {
    const leaks = snap.leaks || { breaches: [], total_pwned: 0, by_class: {} };
    const [filter, setFilter] = useState('');
    const [classFilter, setClassFilter] = useState('ALL');
    const [sortCol, setSortCol] = useState('added_date');
    const [sortDir, setSortDir] = useState('desc');

    const topClasses = Object.keys(leaks.by_class).slice(0, 8);

    const fl = filter.toLowerCase();
    const rows = (leaks.breaches || [])
      .filter(b => {
        if (classFilter !== 'ALL' && !b.data_classes.includes(classFilter)) return false;
        if (!fl) return true;
        return b.title.toLowerCase().includes(fl) || b.domain.toLowerCase().includes(fl);
      })
      .sort((a, b) => {
        const av = a[sortCol], bv = b[sortCol];
        if (!av && !bv) return 0;
        if (!av) return 1;
        if (!bv) return -1;
        const cmp = typeof av === 'number' ? av - bv : av.localeCompare(bv);
        return sortDir === 'asc' ? cmp : -cmp;
      });

    const fmtPwn = n => {
      if (!n) return '—';
      if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
      if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
      if (n >= 1e3) return (n / 1e3).toFixed(0) + 'K';
      return n.toLocaleString();
    };
    const fmtTotal = n => {
      if (!n) return '0';
      if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
      return (n / 1e9).toFixed(1) + 'B';
    };

    const SortTh = ({ col, align, children }) => (
      <th onClick={() => { if (col === sortCol) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortCol(col); setSortDir('desc'); } }}
        style={{ cursor: 'pointer', textAlign: align || 'left' }}>
        {children}{sortCol === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
      </th>
    );

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Summary tiles */}
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            ['TOTAL BREACHES',      leaks.breaches.length],
            ['ACCOUNTS PWNED',      fmtTotal(leaks.total_pwned) + ' accounts'],
            ['DATA CLASSES',        Object.keys(leaks.by_class).length],
            ['VERIFIED BREACHES',   leaks.breaches.filter(b => b.verified).length],
          ].map(([l, v]) => (
            <div key={l} className="panel" style={{ flex: 1, padding: '8px 12px' }}>
              <div className="mut" style={{ fontSize: 9, marginBottom: 2 }}>{l}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--rose)' }}>{v}</div>
            </div>
          ))}
        </div>

        {/* Class filter chips */}
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {['ALL', ...topClasses].map(c => (
            <button key={c} onClick={() => setClassFilter(c)}
              style={{
                padding: '1px 7px', fontSize: 9, cursor: 'pointer', fontFamily: 'var(--mono)',
                border: '1px solid', letterSpacing: '.04em',
                borderColor: classFilter === c ? 'var(--rose)' : 'var(--border-2)',
                background: classFilter === c ? 'rgba(251,113,133,.1)' : 'transparent',
                color: classFilter === c ? 'var(--rose)' : 'var(--text-2)',
              }}>
              {c === 'ALL' ? 'ALL' : c}
              {c !== 'ALL' && leaks.by_class[c] ? <span className="mut"> {leaks.by_class[c]}</span> : null}
            </button>
          ))}
        </div>

        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="DATA BREACH CATALOG"
            meta={`${rows.length} BREACHES · HIBP`}
            right={<Filter value={filter} onChange={setFilter} placeholder="domain / title…" />} />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {rows.length === 0 ? <Empty msg="Loading breach catalog…" /> : (
              <table className="dense">
                <thead><tr>
                  <SortTh col="title">BREACH</SortTh>
                  <th>DOMAIN</th>
                  <SortTh col="breach_date" align="right">BREACH DATE</SortTh>
                  <SortTh col="added_date"  align="right">ADDED</SortTh>
                  <SortTh col="pwn_count"   align="right">ACCOUNTS</SortTh>
                  <th>DATA CLASSES</th>
                  <th style={{ width: 40 }}>VRF</th>
                </tr></thead>
                <tbody>
                  {rows.slice(0, 200).map((b, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600, color: 'var(--rose)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {b.title}
                      </td>
                      <td className="mut" style={{ fontSize: 10 }}>{b.domain || '—'}</td>
                      <td className="num mut" style={{ fontSize: 10 }}>{b.breach_date}</td>
                      <td className="num mut" style={{ fontSize: 10 }}>{b.added_date}</td>
                      <td className="num" style={{ color: b.pwn_count > 1e7 ? 'var(--rose)' : b.pwn_count > 1e6 ? 'var(--amber)' : 'var(--text)', fontWeight: 600 }}>
                        {fmtPwn(b.pwn_count)}
                      </td>
                      <td style={{ fontSize: 9, color: 'var(--muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title={(b.data_classes || []).join(', ')}>
                        {(b.data_classes || []).slice(0, 4).join(', ')}{b.data_classes?.length > 4 ? '…' : ''}
                      </td>
                      <td style={{ fontSize: 9, color: b.verified ? 'var(--mint)' : 'var(--muted)', textAlign: 'center' }}>
                        {b.verified ? '✓' : ''}
                        {b.sensitive ? <span style={{ color: 'var(--rose)', marginLeft: 2 }}>⚠</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: Have I Been Pwned (haveibeenpwned.com) · Public breach catalog · ✓ Verified  ⚠ Sensitive
          </div>
        </div>
      </div>
    );
  }

  // ── CLD — Cloudflare Radar ────────────────────────────────────────────────────
  function CloudflarePanel({ snap }) {
    const cf = snap.cloudflare || { bgp_leaks: [], bgp_stats: {} };
    const [tab, setTab] = useState('leaks');

    const bgp   = cf.bgp_leaks || [];
    const stats = cf.bgp_stats || {};

    const tabBtn = (key, label) => (
      <button key={key} onClick={() => setTab(key)}
        style={{ padding: '2px 10px', fontFamily: 'var(--mono)', fontSize: 9, cursor: 'pointer',
          border: '1px solid', letterSpacing: '.06em',
          borderColor: tab === key ? 'var(--cyan)' : 'var(--border-2)',
          background: tab === key ? 'rgba(56,189,248,.12)' : 'transparent',
          color: tab === key ? 'var(--cyan)' : 'var(--text-2)' }}>
        {label}
      </button>
    );

    const statsRows = [
      { label: 'Total Prefixes',    val: stats.total_prefixes,   fmt: v => v?.toLocaleString() },
      { label: 'Distinct Origins',  val: stats.distinct_origins, fmt: v => v?.toLocaleString() },
      { label: 'Invalid Routes',    val: stats.invalid_routes,   fmt: v => v?.toLocaleString(), danger: true },
      { label: 'RPKI Valid',        val: stats.rpki_valid,       fmt: v => v?.toLocaleString() },
      { label: 'RPKI Invalid',      val: stats.rpki_invalid,     fmt: v => v?.toLocaleString(), danger: true },
    ];

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ padding: '6px 10px', display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <span style={{ color: 'var(--cyan)', fontSize: 11, letterSpacing: '.1em', fontWeight: 700, marginRight: 4 }}>◆ CLOUDFLARE RADAR · BGP</span>
          {[['leaks','BGP LEAKS'],['stats','ROUTE STATS']].map(([k,l]) => tabBtn(k, l))}
        </div>

        {tab === 'leaks' && (
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PH title="BGP ROUTE LEAK EVENTS" meta={`${bgp.length} EVENTS · Cloudflare Radar`} />
            <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {bgp.length === 0 ? <Empty msg="No BGP leak events detected — loading…" /> : (
                <table className="dense">
                  <thead><tr>
                    <th>DATE</th>
                    <th>LEAK ASN</th>
                    <th className="num">PREFIXES</th>
                    <th className="num">PEERS</th>
                    <th>COUNTRIES</th>
                  </tr></thead>
                  <tbody>
                    {bgp.map((e, i) => (
                      <tr key={i}>
                        <td className="mut" style={{ fontSize: 10 }}>{e.date}</td>
                        <td className="lbl" style={{ fontWeight: 700 }}>AS{e.leak_asn}</td>
                        <td className="num" style={{ color: e.prefixes > 1000 ? 'var(--rose)' : 'var(--amber)' }}>{(e.prefixes || 0).toLocaleString()}</td>
                        <td className="num">{(e.peers || 0).toLocaleString()}</td>
                        <td className="mut" style={{ fontSize: 9 }}>{(e.countries || []).slice(0, 3).join(', ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
              Source: Cloudflare Radar BGP · Route leak detection · Updates hourly
            </div>
          </div>
        )}

        {tab === 'stats' && (
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PH title="GLOBAL BGP ROUTE STATISTICS" meta="Cloudflare Radar · /radar/bgp/routes/stats" />
            <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {!Object.keys(stats).length
                ? <Empty msg="Loading BGP route statistics…" />
                : statsRows.map(row => (
                    <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                      <span style={{ fontSize: 11, color: 'var(--text-2)' }}>{row.label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: row.danger ? 'var(--rose)' : 'var(--cyan)' }}>
                        {row.val != null ? row.fmt(row.val) : '—'}
                      </span>
                    </div>
                  ))
              }
            </div>
            <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)', marginTop: 'auto' }}>
              Source: Cloudflare Radar BGP · Updates hourly
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── POL / TER — GDELT Event Feed ─────────────────────────────────────────────
  function GdeltPanel({ snap, mode }) {
    const gd = snap.gdelt || { pol: [], ter: [], dip: [] };
    const events = mode === 'ter' ? (gd.ter || []) : mode === 'dip' ? (gd.dip || []) : (gd.pol || []);
    const [filter, setFilter] = useState('');
    const [sel, setSel] = useState(null);

    const QUAD_LABEL = { 1: 'Verbal Coop', 2: 'Material Coop', 3: 'Verbal Conflict', 4: 'Material Conflict' };
    const QUAD_COLOR = { 1: 'var(--green)', 2: 'var(--cyan)', 3: 'var(--amber)', 4: 'var(--rose)' };

    const filtered = useMemo(() => {
      const f = filter.toLowerCase();
      if (!f) return events;
      return events.filter(e =>
        (e.label||'').toLowerCase().includes(f) ||
        (e.location||'').toLowerCase().includes(f) ||
        (e.actor1||'').toLowerCase().includes(f) ||
        (e.actor2||'').toLowerCase().includes(f) ||
        (e.country||'').toLowerCase().includes(f)
      );
    }, [events, filter]);

    const { sorted, col, dir, toggle: sortToggle } = useSort(filtered, 'mentions');
    function toggle(c) { sortToggle(c); setSel(null); }

    const selected = sel !== null ? sorted[sel] : null;

    const titleLabel = mode === 'ter' ? 'SECURITY INCIDENTS' : mode === 'dip' ? 'DIPLOMATIC EVENTS' : 'POLITICAL EVENTS';
    const source = mode === 'ter'
      ? 'GDELT 2.0 · CAMEO codes 18-20 (Assault/Fight/Mass Violence) · 2h rolling window'
      : mode === 'dip'
      ? 'GDELT 2.0 · CAMEO codes 03-09 (Cooperate/Consult/Diplomacy/Aid) · 2h rolling window'
      : 'GDELT 2.0 · CAMEO codes 10-17 (Demand/Protest/Threaten/Coerce) · 2h rolling window';

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', gap: 6 }}>
        <div className="panel" style={{ flex: 2, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title={titleLabel}
            meta={`${filtered.length} EVENTS`}
            right={<Filter value={filter} onChange={v => { setFilter(v); setSel(null); }} placeholder="location, actor…" />}
          />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg={events.length === 0 ? 'Loading GDELT data…' : 'No matches'} /> : (
              <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ width: 120 }}>EVENT TYPE</th>
                    <th style={{ width: 130 }}>LOCATION</th>
                    <th style={{ width: 60 }}>COUNTRY</th>
                    <th style={{ width: 110 }}>QUAD CLASS</th>
                    <Sortable col="mentions" active={col==='mentions'} dir={dir} onClick={toggle}>MENTIONS</Sortable>
                    <Sortable col="goldstein" active={col==='goldstein'} dir={dir} onClick={toggle}>GOLDSTEIN</Sortable>
                    <th style={{ width: 70 }}>DATE</th>
                    <th>SOURCE</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.slice(0, 80).map((e, i) => (
                    <tr key={e.event_id + i}
                      onClick={() => setSel(i === sel ? null : i)}
                      style={{ background: sel === i ? 'rgba(56,189,248,.08)' : 'transparent', cursor: 'pointer' }}>
                      <td style={{ color: QUAD_COLOR[e.quad_class] || 'var(--text)', fontSize: 10, fontWeight: 600 }}>
                        {e.label}
                      </td>
                      <td style={{ fontSize: 10, color: 'var(--text-2)' }}>{e.location || '—'}</td>
                      <td className="num" style={{ fontSize: 10 }}>{e.country || '—'}</td>
                      <td style={{ fontSize: 9 }}>
                        <span style={{ color: QUAD_COLOR[e.quad_class] || 'var(--muted)' }}>
                          {QUAD_LABEL[e.quad_class] || '—'}
                        </span>
                      </td>
                      <td className="num">{e.mentions}</td>
                      <td className={`num ${e.goldstein < -5 ? 'neg' : e.goldstein < 0 ? 'warn' : 'pos'}`}>
                        {e.goldstein?.toFixed(1)}
                      </td>
                      <td style={{ fontSize: 9, color: 'var(--muted)' }}>
                        {e.day ? `${e.day.slice(0,4)}-${e.day.slice(4,6)}-${e.day.slice(6,8)}` : '—'}
                      </td>
                      <td style={{ fontSize: 9, color: 'var(--dim)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {e.url ? e.url.replace(/^https?:\/\/(www\.)?/, '').slice(0, 50) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            {source}
          </div>
        </div>
        {selected && (
          <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <PH title="EVENT DETAIL" />
            <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
              <div style={{ marginBottom: 6 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: QUAD_COLOR[selected.quad_class] || 'var(--cyan)' }}>
                  {selected.label}
                </span>
                <span className="pill" style={{ marginLeft: 8, fontSize: 9 }}>CAMEO {selected.event_code}</span>
              </div>
              {selected.location && (
                <div style={{ marginBottom: 4 }}>
                  <span style={{ fontSize: 9, color: 'var(--muted)' }}>LOCATION </span>
                  <span style={{ fontSize: 10 }}>{selected.location}</span>
                  {selected.country && <span className="pill" style={{ marginLeft: 6, fontSize: 9 }}>{selected.country}</span>}
                </div>
              )}
              {(selected.actor1 || selected.actor2) && (
                <div style={{ marginBottom: 4 }}>
                  <span style={{ fontSize: 9, color: 'var(--muted)' }}>ACTORS </span>
                  <span style={{ fontSize: 10 }}>{[selected.actor1, selected.actor2].filter(Boolean).join(' → ')}</span>
                </div>
              )}
              <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                {[
                  ['Quad Class', QUAD_LABEL[selected.quad_class] || '—'],
                  ['Goldstein', selected.goldstein?.toFixed(2)],
                  ['Mentions', selected.mentions],
                  ['Articles', selected.articles],
                  ['Avg Tone', selected.avg_tone?.toFixed(2)],
                  ['Date', selected.day ? `${selected.day.slice(0,4)}-${selected.day.slice(4,6)}-${selected.day.slice(6,8)}` : '—'],
                ].map(([k, v]) => (
                  <div key={k} style={{ background: 'var(--bg-2)', borderRadius: 4, padding: '6px 8px' }}>
                    <div style={{ fontSize: 9, color: 'var(--muted)' }}>{k}</div>
                    <div style={{ fontSize: 11, fontWeight: 600 }}>{v}</div>
                  </div>
                ))}
              </div>
              {selected.url && (
                <div style={{ marginTop: 10, wordBreak: 'break-all', fontSize: 9, color: 'var(--dim)' }}>
                  {selected.url}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  function PolPanel({ snap }) { return <GdeltPanel snap={snap} mode="pol" />; }
  function TerPanel({ snap }) { return <GdeltPanel snap={snap} mode="ter" />; }
  function DipPanel({ snap }) { return <GdeltPanel snap={snap} mode="dip" />; }

  // ── INV — Petroleum & Gas Inventory ──────────────────────────────────────────
  function InventoryPanel({ snap }) {
    const oil = snap.energy?.oil || {};
    const gas = snap.energy?.gas || {};

    function MiniSpark({ history, color = 'var(--cyan)' }) {
      const vals = (history || []).map(d => d.value).filter(v => v != null).reverse();
      if (vals.length < 2) return null;
      const min = Math.min(...vals), max = Math.max(...vals);
      const range = max - min || 1;
      const w = 80, h = 24;
      const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * w},${h - ((v - min) / range) * h}`).join(' ');
      return (
        <svg width={w} height={h} style={{ display: 'block' }}>
          <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
        </svg>
      );
    }

    const STOCKS = [
      {
        label: 'Crude Oil (Commercial)',
        unit: 'MB',
        value: oil.us_inventory_mb,
        date: oil.us_inventory_date,
        history: oil.crude_history,
        color: 'var(--amber)',
        note: 'U.S. commercial crude in storage',
      },
      {
        label: 'Crude (Cushing, OK)',
        unit: 'MB',
        value: oil.cushing_inventory_mb,
        date: oil.us_inventory_date,
        history: oil.cushing_history,
        color: 'var(--amber)',
        note: 'WTI delivery point',
      },
      {
        label: 'Total Gasoline',
        unit: 'MB',
        value: oil.gasoline_inventory_mb,
        date: oil.us_inventory_date,
        history: oil.gasoline_history,
        color: 'var(--cyan)',
        note: 'Finished + blending components',
      },
      {
        label: 'Distillate Fuel Oil',
        unit: 'MB',
        value: oil.distillate_inventory_mb,
        date: oil.us_inventory_date,
        history: oil.distillate_history,
        color: 'var(--text-2)',
        note: 'Diesel + heating oil',
      },
      {
        label: 'Nat Gas Storage (L48)',
        unit: 'BCF',
        value: gas.gas_storage_bcf,
        date: gas.gas_storage_date,
        history: gas.gas_storage_history,
        color: 'var(--green)',
        note: 'Underground working gas',
      },
    ];

    function fmt(v, unit) {
      if (v == null) return '—';
      const n = Number(v);
      if (unit === 'BCF') return n.toLocaleString() + ' BCF';
      return (n / 1000).toFixed(1) + 'B bbl';
    }

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="US ENERGY INVENTORY" meta="EIA WEEKLY" />
          <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
            <div style={{ display: 'grid', gap: 8 }}>
              {STOCKS.map(s => (
                <div key={s.label} style={{ background: 'var(--bg-2)', borderRadius: 6, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10, color: 'var(--muted)', marginBottom: 2 }}>{s.label}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: s.color, fontFamily: 'JetBrains Mono, monospace' }}>
                      {fmt(s.value, s.unit)}
                    </div>
                    <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 2 }}>
                      {s.note} · as of {s.date || '—'}
                    </div>
                  </div>
                  <div style={{ flexShrink: 0 }}>
                    <MiniSpark history={s.history} color={s.color} />
                    <div style={{ fontSize: 8, color: 'var(--dim)', textAlign: 'right', marginTop: 2 }}>52-week</div>
                  </div>
                  {s.history && s.history.length >= 2 && (() => {
                    const h = s.history.filter(d => d.value != null);
                    if (h.length < 2) return null;
                    const curr = Number(h[0].value), prev = Number(h[1].value);
                    const chg = curr - prev;
                    const pct = prev ? (chg / prev * 100) : 0;
                    return (
                      <div style={{ textAlign: 'right', minWidth: 70 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: chg > 0 ? 'var(--rose)' : 'var(--green)' }}>
                          {chg > 0 ? '+' : ''}{chg < 1000 ? chg.toFixed(0) : (chg/1000).toFixed(1)+'K'}
                        </div>
                        <div style={{ fontSize: 9, color: 'var(--muted)' }}>
                          {pct > 0 ? '+' : ''}{pct.toFixed(1)}% W/W
                        </div>
                      </div>
                    );
                  })()}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 12, fontSize: 9, color: 'var(--dim)' }}>
              For crude oil, rising inventory is bearish (supply glut). For gas, seasonally high storage signals lower prices.
            </div>
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: EIA Open Data API v2 · Weekly release (Wednesdays) · MBBL = thousand barrels · BCF = billion cubic feet
          </div>
        </div>
      </div>
    );
  }

  // ── HAC — CISA Known Exploited Vulns (Incident Response) ─────────────────────
  function HacPanel({ snap }) {
    const ransomware = snap.cve?.ransomware || [];
    const [filter, setFilter] = useState('');
    const fl = filter.toLowerCase();

    const filtered = useMemo(() => {
      if (!fl) return ransomware;
      return ransomware.filter(r =>
        (r.victim||'').toLowerCase().includes(fl) ||
        (r.group||'').toLowerCase().includes(fl) ||
        (r.country||'').toLowerCase().includes(fl)
      );
    }, [ransomware, fl]);

    const { sorted, col, dir, toggle } = useSort(filtered, 'date', 'desc');

    // Group by ransomware gang for summary
    const byGroup = useMemo(() => {
      const m = {};
      for (const r of ransomware) {
        const g = r.group || 'unknown';
        m[g] = (m[g] || 0) + 1;
      }
      return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, 8);
    }, [ransomware]);

    const fmtDate = d => {
      if (!d) return '—';
      try { return new Date(d).toISOString().slice(0, 10); } catch { return d; }
    };

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {/* Gang activity summary */}
        <div className="panel" style={{ padding: '8px 12px', flexShrink: 0 }}>
          <div style={{ fontSize: 9, color: 'var(--cyan)', letterSpacing: '.1em', fontWeight: 700, marginBottom: 8 }}>
            ◆ ACTIVE RANSOMWARE GROUPS · LAST 30 DAYS
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {byGroup.map(([g, n]) => (
              <div key={g} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '3px 8px',
                background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 2 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--rose)' }}>{g}</span>
                <span style={{ fontSize: 9, color: 'var(--muted)' }}>{n}</span>
              </div>
            ))}
            {byGroup.length === 0 && <span className="mut" style={{ fontSize: 10 }}>Loading…</span>}
          </div>
        </div>

        {/* Incident table */}
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="RANSOMWARE INCIDENTS"
            meta={`${ransomware.length} CONFIRMED · ransomware.live`}
            right={<Filter value={filter} onChange={setFilter} placeholder="victim, group, country…" />}
          />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg="Loading ransomware incident feed…" /> : (
              <table className="dense">
                <thead><tr>
                  <Sortable col="date"    active={col==='date'}    dir={dir} onClick={toggle}>DATE</Sortable>
                  <Sortable col="victim"  active={col==='victim'}  dir={dir} onClick={toggle}>VICTIM</Sortable>
                  <Sortable col="group"   active={col==='group'}   dir={dir} onClick={toggle}>GROUP</Sortable>
                  <Sortable col="country" active={col==='country'} dir={dir} onClick={toggle}>CTY</Sortable>
                  <th>WEBSITE</th>
                </tr></thead>
                <tbody>
                  {sorted.map((r, i) => (
                    <tr key={i}>
                      <td className="mut" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>{fmtDate(r.date)}</td>
                      <td style={{ fontWeight: 600, fontSize: 11 }}>{r.victim}</td>
                      <td><span className="pill pill-rose" style={{ fontSize: 9 }}>{r.group}</span></td>
                      <td className="lbl" style={{ fontSize: 10 }}>{r.country}</td>
                      <td className="mut" style={{ fontSize: 9 }}>{r.website}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Source: ransomware.live · confirmed victims · updated hourly
          </div>
        </div>
      </div>
    );
  }

  // ── ISS — International Space Station ────────────────────────────────────────
  function ISSPanel({ snap }) {
    const sp = snap.space || {};
    const iss = sp.iss || null;
    const tg  = sp.tiangong || null;
    const crew = sp.crew || [];
    const issCrew = crew.filter(c => c.craft === 'ISS');
    const tgCrew  = crew.filter(c => c.craft === 'Tiangong');

    function StatBox({ label, value, unit, color = 'var(--cyan)' }) {
      return (
        <div style={{ background: 'var(--bg-2)', borderRadius: 6, padding: '10px 14px', textAlign: 'center' }}>
          <div style={{ fontSize: 9, color: 'var(--muted)', marginBottom: 4 }}>{label}</div>
          <div style={{ fontSize: 20, fontWeight: 700, color, fontFamily: 'JetBrains Mono, monospace' }}>{value ?? '—'}</div>
          {unit && <div style={{ fontSize: 9, color: 'var(--dim)', marginTop: 2 }}>{unit}</div>}
        </div>
      );
    }

    function StationBlock({ station, crewList, title, color }) {
      if (!station) return (
        <div style={{ background: 'var(--bg-2)', borderRadius: 6, padding: 14, color: 'var(--muted)', fontSize: 10 }}>
          {title}: no position data
        </div>
      );
      return (
        <div style={{ background: 'var(--bg-2)', borderRadius: 6, padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color, marginBottom: 10 }}>{title}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
            <StatBox label="ALTITUDE" value={station.altitude_km?.toFixed(1)} unit="km" color={color} />
            <StatBox label="VELOCITY" value={station.velocity_kms?.toFixed(2)} unit="km/s" color={color} />
            <StatBox label="POSITION" value={station.ground_track || `${station.lat?.toFixed(1)}° ${station.lon?.toFixed(1)}°`} color="var(--text)" />
            <StatBox label="VISIBILITY" value={(station.visibility || '—').toUpperCase()} color={station.visibility === 'daylight' ? 'var(--amber)' : 'var(--muted)'} />
          </div>
          {crewList.length > 0 && (
            <div>
              <div style={{ fontSize: 9, color: 'var(--muted)', marginBottom: 6 }}>CREW ({crewList.length})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {crewList.map(c => (
                  <span key={c.name} style={{
                    background: 'var(--bg-3)', padding: '3px 10px', borderRadius: 4,
                    fontSize: 10, color: 'var(--text)'
                  }}>{c.name}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    return (
      <div style={{ padding: 6, height: '100%', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <PH title="SPACE STATIONS" meta={`${crew.length} CREW IN ORBIT`} />
          <div style={{ flex: 1, overflow: 'auto', padding: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <StationBlock station={iss} crewList={issCrew} title="INTERNATIONAL SPACE STATION (ISS)" color="var(--cyan)" />
            <StationBlock station={tg} crewList={tgCrew} title="TIANGONG (CSS)" color="var(--rose)" />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
              <StatBox label="ACTIVE SATELLITES" value={(sp.active_count||0).toLocaleString()} color="var(--green)" />
              <StatBox label="STARLINK SATS" value={(sp.starlink_count||0).toLocaleString()} color="var(--amber)" />
              <StatBox label="TOTAL IN ORBIT" value={`${((sp.active_count||0) + (sp.starlink_count||0)).toLocaleString()}+`} color="var(--text-2)" />
            </div>
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            ISS position: wheretheiss.at · Tiangong: TLE propagation · Crew: open-notify.org · Updated every 60s
          </div>
        </div>
      </div>
    );
  }

  // ── INT — Country Intelligence / Risk Index ───────────────────────────────────
  function IntPanel({ snap }) {
    const { useState: useStateL, useMemo: useMemoL } = React;
    const gdelt = snap.gdelt || { pol: [], ter: [], dip: [] };
    const [filter, setFilter] = useStateL('');

    const NAMES = {
      US:'United States', RU:'Russia', UA:'Ukraine', CN:'China', IR:'Iran', IL:'Israel',
      PS:'Palestine', SY:'Syria', AF:'Afghanistan', IQ:'Iraq', YE:'Yemen', SO:'Somalia',
      LY:'Libya', SD:'Sudan', ET:'Ethiopia', MM:'Myanmar', PK:'Pakistan', IN:'India',
      GB:'United Kingdom', FR:'France', DE:'Germany', TR:'Turkey', SA:'Saudi Arabia',
      EG:'Egypt', NG:'Nigeria', VE:'Venezuela', KP:'North Korea', MX:'Mexico',
      BR:'Brazil', ZA:'South Africa', KE:'Kenya', ML:'Mali', NE:'Niger', CF:'Cent. Africa',
    };

    const countries = useMemoL(() => {
      const map = {};
      const inc = (country, type, mentions) => {
        if (!country || country === '—' || country.length < 2 || country.length > 3) return;
        if (!map[country]) map[country] = { country, ter: 0, pol: 0, dip: 0 };
        map[country][type] += mentions;
      };
      (gdelt.ter || []).forEach(e => inc(e.country, 'ter', e.mentions || 1));
      (gdelt.pol || []).forEach(e => inc(e.country, 'pol', e.mentions || 1));
      (gdelt.dip || []).forEach(e => inc(e.country, 'dip', e.mentions || 1));
      return Object.values(map)
        .map(c => ({ ...c, threat_score: c.ter * 2 + c.pol }))
        .sort((a, b) => b.threat_score - a.threat_score)
        .slice(0, 60);
    }, [gdelt]);

    const filtered = useMemoL(() => {
      if (!filter) return countries;
      const f = filter.toLowerCase();
      return countries.filter(c =>
        c.country.toLowerCase().includes(f) ||
        (NAMES[c.country] || '').toLowerCase().includes(f)
      );
    }, [countries, filter]);

    const maxScore = countries[0]?.threat_score || 1;

    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <PH title="INTEL · COUNTRY RISK INDEX"
            meta={`${countries.length} COUNTRIES · 2h WINDOW`}
            right={<Filter value={filter} onChange={setFilter} placeholder="country…" />}
          />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg={countries.length === 0 ? 'Loading GDELT intelligence…' : 'No matches'} /> : (
              <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>
                  <th style={{ width: 32 }}>#</th>
                  <th style={{ width: 48 }}>CODE</th>
                  <th>COUNTRY</th>
                  <th style={{ width: 60, color: 'var(--rose)' }}>TERROR</th>
                  <th style={{ width: 60, color: 'var(--amber)' }}>POLIT</th>
                  <th style={{ width: 60, color: 'var(--green)' }}>DIPL</th>
                  <th style={{ width: 70 }}>THREAT</th>
                  <th>HEAT</th>
                </tr></thead>
                <tbody>
                  {filtered.map((c, i) => (
                    <tr key={c.country}>
                      <td className="num" style={{ color: 'var(--muted)', fontSize: 10 }}>{i + 1}</td>
                      <td><span className="pill" style={{ fontSize: 9 }}>{c.country}</span></td>
                      <td style={{ fontSize: 10 }}>{NAMES[c.country] || c.country}</td>
                      <td className="num" style={{ color: c.ter > 0 ? 'var(--rose)' : 'var(--muted)', fontSize: 10 }}>{c.ter}</td>
                      <td className="num" style={{ color: c.pol > 0 ? 'var(--amber)' : 'var(--muted)', fontSize: 10 }}>{c.pol}</td>
                      <td className="num" style={{ color: c.dip > 0 ? 'var(--green)' : 'var(--muted)', fontSize: 10 }}>{c.dip}</td>
                      <td className="num" style={{ color: 'var(--rose)', fontWeight: 700, fontSize: 11 }}>{c.threat_score}</td>
                      <td style={{ paddingRight: 12 }}>
                        <div style={{ height: 5, background: 'var(--surface-2)', borderRadius: 3 }}>
                          <div style={{ width: (c.threat_score / maxScore * 100) + '%', height: '100%',
                            background: c.ter > c.pol ? 'var(--rose)' : 'var(--amber)', borderRadius: 3 }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            GDELT 2.0 event intel · Threat = Terror×2 + Political mentions · 2h rolling window
          </div>
        </div>
      </div>
    );
  }

  // ── DAR — Dark Web / Threat Intelligence ─────────────────────────────────────
  function DarPanel({ snap }) {
    const { useState: useStateL, useMemo: useMemoL } = React;
    const kev        = snap.cve?.kev        || [];
    const ransomware = snap.cve?.ransomware  || [];
    const advisories = snap.threats?.advisories || [];
    const breaches   = snap.leaks?.breaches  || [];
    const [tab, setTab] = useStateL('kev');
    const [filter, setFilter] = useStateL('');

    const { sorted: sortedKev, col, dir, toggle } = useSort(kev, 'date_added');

    const recentBreaches = useMemoL(() =>
      [...breaches].sort((a, b) => (b.added_date || '').localeCompare(a.added_date || '')).slice(0, 60),
      [breaches]
    );

    const filteredBreaches = useMemoL(() => {
      if (!filter) return recentBreaches;
      const f = filter.toLowerCase();
      return recentBreaches.filter(b =>
        (b.title || b.name || '').toLowerCase().includes(f) ||
        (b.domain || '').toLowerCase().includes(f)
      );
    }, [recentBreaches, filter]);

    const filteredAdv = useMemoL(() => {
      if (!filter) return advisories;
      const f = filter.toLowerCase();
      return advisories.filter(a => (a.title || '').toLowerCase().includes(f));
    }, [advisories, filter]);

    const fmt = n => !n ? '—' : n >= 1e9 ? (n/1e9).toFixed(1)+'B' : n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(0)+'K' : n;

    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <PH title="DARK WEB · THREAT INTELLIGENCE" />
          <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', padding: '0 8px', flexShrink: 0 }}>
            {[
              ['kev',  `KEV (${kev.length})`],
              ['ran',  `RANSOMWARE (${ransomware.length})`],
              ['adv',  `ADVISORIES (${advisories.length})`],
              ['brk',  `BREACHES (${breaches.length})`],
            ].map(([code, label]) => (
              <button key={code} className={`btn${tab===code?' on':''}`}
                onClick={() => { setTab(code); setFilter(''); }}
                style={{ fontSize: 9, padding: '3px 10px' }}>
                {label}
              </button>
            ))}
            <div style={{ flex: 1 }} />
            {(tab === 'brk' || tab === 'adv') && (
              <Filter value={filter} onChange={setFilter} placeholder="filter…" />
            )}
          </div>

          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {tab === 'kev' && (
              kev.length === 0 ? <Empty msg="Loading CISA KEV data…" /> : (
                <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th style={{ width: 150 }}>CVE ID</th>
                    <th>VULNERABILITY NAME</th>
                    <th style={{ width: 90 }}>VENDOR</th>
                    <Sortable col="date_added" active={col==='date_added'} dir={dir} onClick={toggle}>ADDED</Sortable>
                    <Sortable col="due_date"   active={col==='due_date'}   dir={dir} onClick={toggle}>PATCH DUE</Sortable>
                    <th style={{ width: 70 }}>RANSOMWARE</th>
                  </tr></thead>
                  <tbody>
                    {sortedKev.slice(0,60).map(k => (
                      <tr key={k.id}>
                        <td><span className="pill" style={{ fontSize: 9, color: 'var(--rose)' }}>{k.id}</span></td>
                        <td style={{ fontSize: 10 }}>{k.name || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{k.vendor || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{k.date_added || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--amber)' }}>{k.due_date || '—'}</td>
                        <td style={{ fontSize: 9, textAlign: 'center', color: k.ransomware === 'Known' ? 'var(--rose)' : 'var(--muted)' }}>
                          {k.ransomware === 'Known' ? '⚠ YES' : 'no'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {tab === 'ran' && (
              ransomware.length === 0 ? <Empty msg="Loading ransomware data…" /> : (
                <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th>VICTIM</th>
                    <th style={{ width: 120 }}>GROUP</th>
                    <th style={{ width: 50 }}>COUNTRY</th>
                    <th style={{ width: 170 }}>DATE</th>
                  </tr></thead>
                  <tbody>
                    {[...ransomware].sort((a,b)=>(b.date||'').localeCompare(a.date||'')).slice(0,60).map((r, i) => (
                      <tr key={i}>
                        <td style={{ fontSize: 11, fontWeight: 600 }}>{r.victim || '—'}</td>
                        <td><span className="pill" style={{ fontSize: 9, color: 'var(--rose)' }}>{r.group || '—'}</span></td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{r.country || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{r.date ? r.date.slice(0,16).replace('T',' ') : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {tab === 'adv' && (
              filteredAdv.length === 0 ? <Empty msg="Loading advisories…" /> : (
                <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th>ADVISORY TITLE</th>
                    <th style={{ width: 80 }}>SOURCE</th>
                    <th style={{ width: 80 }}>DATE</th>
                    <th style={{ width: 70 }}>SEVERITY</th>
                  </tr></thead>
                  <tbody>
                    {filteredAdv.slice(0,60).map((a, i) => (
                      <tr key={i}>
                        <td style={{ fontSize: 10 }}>
                          {a.link
                            ? <a href={a.link} target="_blank" rel="noopener noreferrer"
                                style={{ color: 'var(--cyan)', textDecoration: 'none' }}>{a.title || '—'}</a>
                            : (a.title || '—')}
                        </td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{a.source || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{a.date || '—'}</td>
                        <td style={{ fontSize: 9, color: a.severity === 'Critical' ? 'var(--rose)' : a.severity === 'High' ? 'var(--amber)' : 'var(--text-2)' }}>{a.severity || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {tab === 'brk' && (
              filteredBreaches.length === 0 ? <Empty msg="Loading breach index…" /> : (
                <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead><tr>
                    <th>SERVICE / BREACH</th>
                    <th style={{ width: 120 }}>DOMAIN</th>
                    <th style={{ width: 90 }}>BREACH DATE</th>
                    <th style={{ width: 80 }}>ACCOUNTS</th>
                    <th>DATA CLASSES</th>
                  </tr></thead>
                  <tbody>
                    {filteredBreaches.map((b, i) => (
                      <tr key={i}>
                        <td style={{ fontSize: 11, fontWeight: 600 }}>{b.title || b.name || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{b.domain || '—'}</td>
                        <td style={{ fontSize: 9, color: 'var(--muted)' }}>{b.breach_date || '—'}</td>
                        <td className="num" style={{ color: 'var(--rose)', fontSize: 10 }}>{fmt(b.pwn_count)}</td>
                        <td style={{ fontSize: 9, color: 'var(--text-2)' }}>
                          {(b.data_classes || []).slice(0, 4).join(', ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            CISA KEV · CISA Ransomware Tracker · CISA Advisories · HaveIBeenPwned Breach Index
          </div>
        </div>
      </div>
    );
  }

  // ── SOC — HackerNews Top Stories ─────────────────────────────────────────────
  function SocPanel({ snap }) {
    const { useState: useStateL, useMemo: useMemoL } = React;
    const stories = snap.hackernews?.stories || [];
    const [filter, setFilter] = useStateL('');

    const filtered = useMemoL(() => {
      if (!filter) return stories;
      const f = filter.toLowerCase();
      return stories.filter(s =>
        s.title.toLowerCase().includes(f) || s.domain.toLowerCase().includes(f)
      );
    }, [stories, filter]);

    const { sorted, col, dir, toggle } = useSort(filtered, 'score');

    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <PH title="HACKER NEWS · TOP STORIES"
            meta={`${stories.length} STORIES`}
            right={<Filter value={filter} onChange={setFilter} placeholder="title, domain…" />}
          />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {sorted.length === 0 ? <Empty msg={stories.length === 0 ? 'Loading HN data…' : 'No matches'} /> : (
              <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ width: 32 }}>#</th>
                    <th>TITLE</th>
                    <th style={{ width: 120 }}>DOMAIN</th>
                    <Sortable col="score" active={col==='score'} dir={dir} onClick={toggle}>SCORE</Sortable>
                    <Sortable col="comments" active={col==='comments'} dir={dir} onClick={toggle}>CMTS</Sortable>
                    <th style={{ width: 70 }}>AGE</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((s, i) => (
                    <tr key={s.id}>
                      <td className="num" style={{ color: 'var(--muted)', fontSize: 10 }}>{i + 1}</td>
                      <td style={{ maxWidth: 0 }}>
                        <a href={s.url} target="_blank" rel="noopener noreferrer"
                          style={{ color: 'var(--cyan)', textDecoration: 'none', fontSize: 11, fontWeight: 600,
                            display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.title}
                        </a>
                        <span style={{ fontSize: 9, color: 'var(--muted)' }}>by {s.author}</span>
                      </td>
                      <td style={{ fontSize: 9, color: 'var(--text-2)' }}>{s.domain}</td>
                      <td className="num pos">{s.score}</td>
                      <td className="num" style={{ color: 'var(--text-2)' }}>{s.comments}</td>
                      <td style={{ fontSize: 9, color: 'var(--muted)' }}>{s.time_ago}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            Hacker News · hacker-news.firebaseio.com · Free API · Updated every 10m
          </div>
        </div>
      </div>
    );
  }

  // ── PRT — Global Vessel Destinations / Ports ──────────────────────────────────
  function PortsPanel({ snap }) {
    const { useState: useStateL, useMemo: useMemoL } = React;
    const ships = snap.ships || [];
    const [filter, setFilter] = useStateL('');

    const ports = useMemoL(() => {
      const counts = {};
      const typeMaps = {};
      for (const v of ships) {
        const dest = (v.destination || '').trim().toUpperCase();
        if (!dest || dest === '—' || dest.length < 2) continue;
        counts[dest] = (counts[dest] || 0) + 1;
        if (!typeMaps[dest]) typeMaps[dest] = {};
        const tn = v.type_name || 'Unknown';
        typeMaps[dest][tn] = (typeMaps[dest][tn] || 0) + 1;
      }
      return Object.entries(counts)
        .map(([dest, count]) => {
          const tm = typeMaps[dest] || {};
          const topType = Object.entries(tm).sort((a, b) => b[1] - a[1])[0];
          return { dest, count, topType: topType ? topType[0] : '—' };
        })
        .sort((a, b) => b.count - a.count)
        .slice(0, 60);
    }, [ships]);

    const filtered = useMemoL(() => {
      if (!filter) return ports;
      const f = filter.toLowerCase();
      return ports.filter(p => p.dest.toLowerCase().includes(f));
    }, [ports, filter]);

    const maxCount = ports[0]?.count || 1;
    const total = ships.length;

    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <PH title="VESSEL DESTINATIONS · GLOBAL PORTS"
            meta={`${ports.length} PORTS · ${total} VESSELS`}
            right={<Filter value={filter} onChange={setFilter} placeholder="port name…" />}
          />
          <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            {filtered.length === 0 ? <Empty msg={ships.length === 0 ? 'Loading vessel data…' : 'No ports found'} /> : (
              <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ width: 32 }}>#</th>
                    <th>DESTINATION</th>
                    <th style={{ width: 120 }}>TOP VESSEL TYPE</th>
                    <th style={{ width: 60 }}>VESSELS</th>
                    <th style={{ width: 60 }}>SHARE</th>
                    <th>CONCENTRATION</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p, i) => (
                    <tr key={p.dest}>
                      <td className="num" style={{ color: 'var(--muted)', fontSize: 10 }}>{i + 1}</td>
                      <td style={{ fontSize: 11, fontWeight: 600 }}>{p.dest}</td>
                      <td style={{ fontSize: 9, color: 'var(--text-2)' }}>{p.topType}</td>
                      <td className="num pos">{p.count}</td>
                      <td className="num" style={{ color: 'var(--muted)', fontSize: 10 }}>
                        {total > 0 ? (p.count / total * 100).toFixed(1) + '%' : '—'}
                      </td>
                      <td style={{ paddingRight: 12 }}>
                        <div style={{ height: 5, background: 'var(--surface-2)', borderRadius: 3 }}>
                          <div style={{ width: (p.count / maxCount * 100) + '%', height: '100%',
                            background: 'var(--cyan)', borderRadius: 3 }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--border)', padding: '4px 8px', fontSize: 9, color: 'var(--muted)' }}>
            AIS vessel destinations · Derived from live AIS feed · Updated every 30s
          </div>
        </div>
      </div>
    );
  }

  // ── Merge ─────────────────────────────────────────────────────────────────────
  Object.assign(window.DeltaPanels, {
    OptionsFlowPanel,
    CommoditiesPanel,
    ArxivPanel,
    HealthPanel,
    MigrationPanel,
    LaborPanel,
    ManufacturingPanel,
    UrbanPanel, EducationPanel,
    RecPanel,
    EdgarPanel,
    AlertsPanel,
    PortfolioPanel,
    EarningsPanel,
    DarkpoolPanel,
    ChartsPanel,
    CryptoPanel,
    ThreatPanel,
    OceanPanel,
    TradePanel,
    ElectionsPanel,
    LeaksPanel,
    CloudflarePanel,
    PolPanel,
    TerPanel,
    DipPanel,
    IntPanel,
    DarPanel,
    HacPanel,
    InventoryPanel,
    ISSPanel,
    SocPanel,
    PortsPanel,
  });
})();
