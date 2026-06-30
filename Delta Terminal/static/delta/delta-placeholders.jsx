// delta-placeholders.jsx — procedurally-themed placeholder panels for the 50+ stub tabs.
// Exposes window.DeltaPlaceholders[<TAB_CODE>] = Component({snap})

(function () {
  const { useMemo, useState } = React;
  const round = (n, d = 2) => Math.round(n * Math.pow(10, d)) / Math.pow(10, d);
  const { fmt, fmtInt, fmtAbbr, rng, between, pick } = window.DeltaData;
  const { TAB_NAMES } = window.DeltaCats;

  // ───────── tiny primitives ─────────
  function Head({ title, meta, right }) {
    return (
      <div className="panel-head">
        <span>◆ {title}</span>
        <span style={{ flex: 1 }} />
        {meta && <span className="meta">{meta}</span>}
        {right}
      </div>
    );
  }
  function Pill({ tone, children }) {
    return <span className={`pill pill-${tone}`}>{children}</span>;
  }
  function Spark({ seed, up, w = 80, h = 22 }) {
    const r = rng(seed * 9301 + 7);
    let x = 0; const pts = [];
    for (let i = 0; i < 20; i++) { x += (r() - 0.45) * (up ? 1 : -1); pts.push(x); }
    const min = Math.min(...pts), max = Math.max(...pts);
    const range = max - min || 1;
    const path = pts.map((p, i) => `${i * (w / 19)},${h - ((p - min) / range) * (h - 2) - 1}`).join(' ');
    return (
      <svg width={w} height={h} style={{ display: 'block' }}>
        <polyline points={path} fill="none"
          stroke={up ? 'var(--mint)' : 'var(--rose)'} strokeWidth="1.2" opacity="0.9" />
      </svg>
    );
  }
  function Bars({ values, w = 120, h = 36 }) {
    const max = Math.max(...values, 1);
    const bw = w / values.length;
    return (
      <svg width={w} height={h} style={{ display: 'block' }}>
        {values.map((v, i) => {
          const bh = (v / max) * (h - 2);
          return <rect key={i} x={i * bw + 1} y={h - bh} width={bw - 2} height={bh}
            fill="var(--cyan)" opacity="0.7" />;
        })}
      </svg>
    );
  }
  function Stat({ label, value, color, sub }) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <span className="mut" style={{ fontSize: 9, letterSpacing: '.12em' }}>{label}</span>
        <span style={{ fontSize: 18, fontWeight: 600, color: color || 'var(--text)', lineHeight: 1.2 }}>{value}</span>
        {sub && <span className="mut" style={{ fontSize: 10 }}>{sub}</span>}
      </div>
    );
  }
  function StatGrid({ items }) {
    return (
      <div className="panel" style={{ padding: '10px 12px', display: 'grid',
        gridTemplateColumns: `repeat(${items.length}, 1fr)`, gap: 12 }}>
        {items.map((it, i) => <Stat key={i} {...it} />)}
      </div>
    );
  }
  function ListPanel({ title, meta, headers, rows, right }) {
    return (
      <div className="panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%' }}>
        <Head title={title} meta={meta} right={right} />
        <div style={{ overflow: 'auto', flex: 1 }}>
          <table className="dense">
            <thead><tr>{headers.map((h, i) => (
              <th key={i} style={{ textAlign: h.align || 'left' }}>{h.label}</th>
            ))}</tr></thead>
            <tbody>{rows.map((r, i) => (
              <tr key={i}>{r.map((c, j) => (
                <td key={j} className={headers[j].num ? 'num' : ''}
                  style={{ textAlign: headers[j].align || 'left' }}>{c}</td>
              ))}</tr>
            ))}</tbody>
          </table>
        </div>
      </div>
    );
  }
  function makeWrap(stats, panels) {
    return (
      <div style={{ display: 'grid', gridTemplateRows: stats ? 'auto 1fr' : '1fr', gap: 6, height: '100%', padding: 6 }}>
        {stats && <StatGrid items={stats} />}
        <div style={{ display: 'grid', gridTemplateColumns: panels.length > 1 ? `repeat(${panels.length}, 1fr)` : '1fr', gap: 6, minHeight: 0 }}>
          {panels}
        </div>
      </div>
    );
  }

  // ───────── DOMAIN BUILDERS ─────────
  const ALL = {};

  // ============ FINANCE ============
  ALL.EQT = ({ snap }) => {
    const r = rng(42);
    const stocks = snap.tech.concat(
      [['BRK.B','Berkshire',452.10,0.2],['JPM','JPMorgan',254.18,0.4],['V','Visa',312.55,0.1],
       ['UNH','UnitedHealth',570.42,-0.3],['XOM','Exxon',118.20,-0.5],['LLY','Eli Lilly',810.55,1.2],
       ['MA','Mastercard',512.30,0.3],['PG','P&G',171.10,-0.1],['HD','Home Depot',410.80,0.6]]
        .map(([t,n,p,c]) => ({ ticker:t, name:n, price:p, change_pct: c + (r()-.5),
          change: (p*c/100), arrow: c>=0?'▲':'▼', color: c>=0?'up':'down', day_high:p*1.01, day_low:p*0.99, volume: Math.floor(between(2e6,9e7,r)) }))
    );
    return makeWrap(
      [
        { label: 'S&P 500', value: '5,837.12', color: 'var(--mint)', sub: '+0.34%' },
        { label: 'BREADTH', value: '312 / 188', sub: 'advancers / decliners' },
        { label: 'NEW HI / LO', value: '84 / 21', color: 'var(--mint)' },
        { label: 'VOLUME', value: '4.21B', sub: 'NYSE composite' },
        { label: 'TICK', value: '+412', color: 'var(--mint)' },
        { label: 'TRIN', value: '0.91', color: 'var(--mint)' },
      ],
      [
        <ListPanel key="a" title="MOST ACTIVE · LARGE CAP" meta={`${stocks.length} symbols`}
          headers={[
            { label: 'SYM' }, { label: 'NAME' }, { label: 'PRICE', align: 'right', num: true },
            { label: 'Δ%', align: 'right', num: true }, { label: 'VOL', align: 'right', num: true },
            { label: 'TREND', align: 'center' },
          ]}
          rows={stocks.map((s, i) => [
            <span className="lbl">{s.ticker}</span>,
            <span className="mut">{s.name}</span>,
            fmt(s.price),
            <span className={s.color}>{s.arrow} {Math.abs(s.change_pct).toFixed(2)}%</span>,
            <span className="mut">{fmtAbbr(s.volume)}</span>,
            <Spark seed={i+1} up={s.color === 'up'} />,
          ])} />,
        <ListPanel key="b" title="SECTOR PERFORMANCE · TODAY"
          headers={[{label:'SECTOR'},{label:'CHG %',align:'right',num:true},{label:'WEIGHT',align:'right',num:true},{label:'BAR'}]}
          rows={[
            ['Technology', 0.78, 32.4], ['Health Care', -0.21, 12.1], ['Financials', 0.42, 13.6],
            ['Consumer Disc', 0.62, 10.8], ['Communications', 0.91, 8.7], ['Industrials', 0.18, 8.1],
            ['Consumer Stap', -0.08, 5.8], ['Energy', -1.21, 3.6], ['Utilities', -0.32, 2.4],
            ['Real Estate', 0.15, 2.2], ['Materials', -0.41, 2.3],
          ].map(([s, c, w]) => [
            s, <span className={c >= 0 ? 'up' : 'down'}>{c >= 0 ? '+' : ''}{c.toFixed(2)}%</span>,
            <span className="mut">{w.toFixed(1)}%</span>,
            <div style={{ height: 10, background: 'var(--surface-3)', position: 'relative', width: 120 }}>
              <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--border-2)' }} />
              <div style={{ position: 'absolute', top: 1, bottom: 1, left: c < 0 ? `${50 + c * 30}%` : '50%',
                width: `${Math.abs(c) * 30}%`, background: c >= 0 ? 'var(--mint)' : 'var(--rose)' }} />
            </div>,
          ])} />,
      ]
    );
  };

  ALL.BND = () => {
    const r = rng(7);
    const tenors = ['1M','3M','6M','1Y','2Y','3Y','5Y','7Y','10Y','20Y','30Y'];
    const yields = [4.36, 4.42, 4.45, 4.39, 4.28, 4.22, 4.18, 4.21, 4.34, 4.62, 4.71];
    const max = Math.max(...yields), min = Math.min(...yields);
    return makeWrap(
      [
        { label: '10Y YIELD', value: '4.34%', color: 'var(--rose)', sub: '+3.2 bp' },
        { label: '2Y YIELD',  value: '4.28%', color: 'var(--mint)', sub: '-1.4 bp' },
        { label: '2s10s', value: '+6 bp', sub: 'inversion 0d' },
        { label: '5Y BREAKEVEN', value: '2.31%', sub: 'real yld 1.87%' },
        { label: 'MOVE INDEX', value: '91.4', color: 'var(--mint)' },
      ],
      [
        <div className="panel" key="curve" style={{ display: 'flex', flexDirection: 'column' }}>
          <Head title="US TREASURY YIELD CURVE" meta="treasury.gov · hourly" />
          <div style={{ padding: 24, flex: 1, position: 'relative' }}>
            <svg viewBox={`0 0 400 220`} width="100%" height="100%" preserveAspectRatio="none">
              {[0, 1, 2, 3, 4].map(i => (
                <line key={i} x1="40" x2="395" y1={20 + i * 40} y2={20 + i * 40}
                  stroke="var(--border)" strokeDasharray="2 4" />
              ))}
              <polyline points={yields.map((y, i) => {
                const x = 40 + i * ((400-50) / (yields.length - 1));
                const yy = 20 + (1 - (y - min) / (max - min)) * 160;
                return `${x},${yy}`;
              }).join(' ')} fill="none" stroke="var(--cyan)" strokeWidth="2" />
              {yields.map((y, i) => {
                const x = 40 + i * ((400-50) / (yields.length - 1));
                const yy = 20 + (1 - (y - min) / (max - min)) * 160;
                return (
                  <g key={i}>
                    <circle cx={x} cy={yy} r="3" fill="var(--cyan)" />
                    <text x={x} y={yy - 10} fontSize="9" fill="var(--text-2)" textAnchor="middle">{y.toFixed(2)}</text>
                    <text x={x} y="210" fontSize="9" fill="var(--muted)" textAnchor="middle">{tenors[i]}</text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>,
        <ListPanel key="b" title="GLOBAL 10Y BENCHMARKS" headers={[
          {label:'COUNTRY'},{label:'YIELD %',align:'right',num:true},{label:'Δ BP',align:'right',num:true},{label:'SPREAD VS US',align:'right',num:true}]}
          rows={[
            ['United States', 4.34, '+3.2', '0.0'],
            ['Germany', 2.41, '+1.8', '-193'],
            ['United Kingdom', 4.52, '+4.1', '+18'],
            ['Japan', 1.08, '+0.4', '-326'],
            ['France', 3.10, '+2.2', '-124'],
            ['Italy', 3.62, '+3.6', '-72'],
            ['Spain', 3.21, '+2.5', '-113'],
            ['Canada', 3.41, '+1.9', '-93'],
            ['Australia', 4.58, '+2.8', '+24'],
            ['India', 6.81, '+0.5', '+247'],
            ['Brazil', 12.84, '+8.2', '+850'],
          ].map(([c, y, d, s]) => [
            c, <span className="num">{y.toFixed(2)}</span>,
            <span className={parseFloat(d) >= 0 ? 'down' : 'up'}>{d}</span>,
            <span className="mut">{s}</span>,
          ])} />,
      ]
    );
  };

  ALL.FRX = () => {
    const pairs = [
      ['EUR/USD', 1.0521, -0.08], ['USD/JPY', 154.21, 0.31], ['GBP/USD', 1.2651, 0.04],
      ['USD/CHF', 0.8842, -0.12], ['AUD/USD', 0.6512, 0.21], ['USD/CAD', 1.3942, 0.18],
      ['NZD/USD', 0.5891, 0.32], ['USD/CNY', 7.2418, -0.08], ['USD/INR', 84.51, 0.05],
      ['USD/MXN', 20.45, 0.62], ['USD/BRL', 5.81, 0.31], ['USD/TRY', 34.42, 0.18],
      ['USD/ZAR', 18.21, -0.12], ['EUR/GBP', 0.8318, -0.04], ['EUR/JPY', 162.31, 0.22],
    ];
    return makeWrap(
      [
        { label: 'DXY', value: '106.84', color: 'var(--mint)', sub: '+0.12%' },
        { label: 'EUR/USD', value: '1.0521', color: 'var(--rose)', sub: '-0.08%' },
        { label: 'USD/JPY', value: '154.21', color: 'var(--mint)', sub: '+0.31%' },
        { label: 'GBP/USD', value: '1.2651', color: 'var(--mint)', sub: '+0.04%' },
        { label: 'VIX', value: '12.84', color: 'var(--mint)' },
      ],
      [
        <ListPanel key="x" title="MAJOR + EM PAIRS · ECB · 60s" meta="frankfurter.app"
          headers={[{label:'PAIR'},{label:'BID',align:'right',num:true},{label:'Δ%',align:'right',num:true},{label:'TREND',align:'center'}]}
          rows={pairs.map((p, i) => [
            <span className="lbl">{p[0]}</span>, fmt(p[1], 4),
            <span className={p[2] >= 0 ? 'up' : 'down'}>{p[2] >= 0 ? '+' : ''}{p[2].toFixed(2)}%</span>,
            <Spark seed={i+10} up={p[2] >= 0} />,
          ])} />,
      ]
    );
  };

  ALL.FRD = () => makeWrap(null, [
    <div className="panel" key="a" style={{ display: 'flex', flexDirection: 'column' }}>
      <Head title="FRED MACRO INDICATORS · ST.LOUIS FED" meta="fred.stlouisfed.org" right={<Pill tone="amber">KEY REQUIRED</Pill>} />
      <div style={{ padding: 16, flex: 1, overflow: 'auto' }}>
        <table className="dense">
          <thead><tr><th>SERIES</th><th>LATEST</th><th style={{textAlign:'right'}}>VALUE</th><th>UNIT</th><th>CHART</th></tr></thead>
          <tbody>
            {[
              ['UNRATE', 'Unemployment Rate', 'Oct 2024', '4.1', '%', true],
              ['CPIAUCSL', 'CPI All Urban', 'Oct 2024', '315.45', 'idx', true],
              ['GDP', 'Real GDP', 'Q3 2024', '23,401', '$B SAAR', true],
              ['DGS10', '10-Year Treasury', 'Today', '4.34', '%', true],
              ['DFF', 'Fed Funds Rate', 'Today', '4.83', '%', false],
              ['MORTGAGE30US', '30-Yr Mortgage', 'This wk', '6.78', '%', true],
              ['INDPRO', 'Industrial Prod', 'Oct 2024', '102.7', 'idx', false],
              ['PAYEMS', 'Nonfarm Payrolls', 'Oct 2024', '158,512', 'thou', true],
              ['M2SL', 'M2 Money Supply', 'Sep 2024', '21,378', '$B', true],
              ['HOUST', 'Housing Starts', 'Oct 2024', '1,311', 'thou', false],
            ].map((row, i) => (
              <tr key={i}>
                <td><span className="lbl">{row[0]}</span></td>
                <td><span className="mut">{row[1]}</span></td>
                <td>{row[2]}</td>
                <td className="num">{row[3]}</td>
                <td><span className="mut">{row[4]}</span></td>
                <td><Spark seed={i+100} up={row[5]} w={140} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>,
  ]);

  ALL.OFL = () => {
    const r = rng(813);
    const tickers = ['SPY','QQQ','NVDA','TSLA','AAPL','AMD','META','MSFT','AMZN','GOOGL','COIN','MSTR','PLTR','HOOD','GLD','VIX'];
    const expDates = ['22 Nov','29 Nov','06 Dec','20 Dec','17 Jan','21 Mar','19 Jun'];
    const unusual = Array.from({ length: 24 }, (_, i) => {
      const tk = pick(tickers, r);
      const type = r() > 0.42 ? 'C' : 'P';
      const strike = Math.round(between(20, 800, r) / 5) * 5;
      const vol = Math.floor(between(800, 64000, r));
      const oi = Math.max(20, Math.floor(vol / between(0.6, 4, r)));
      const mid = round(between(0.2, 12, r), 2);
      return { tk, type, exp: pick(expDates, r), strike, vol, oi, mid,
        ratio: round(vol / oi, 2), iv: round(between(18, 110, r), 1),
        premium: vol * mid * 100 };
    }).sort((a, b) => b.ratio - a.ratio);

    const byTk = {};
    for (const u of unusual) {
      (byTk[u.tk] ||= { tk: u.tk, calls: 0, puts: 0, prem: 0 });
      if (u.type === 'C') byTk[u.tk].calls += u.vol;
      else byTk[u.tk].puts += u.vol;
      byTk[u.tk].prem += u.premium;
    }
    const summary = Object.values(byTk).map(s => ({
      ...s,
      pc_ratio: round(s.puts / Math.max(1, s.calls), 2),
      total: s.calls + s.puts,
    })).sort((a, b) => b.total - a.total);

    return makeWrap(
      [
        { label: 'UNUSUAL CONTRACTS', value: unusual.length, color: 'var(--cyan)', sub: 'vol/OI ≥ 0.5' },
        { label: 'TOTAL PREMIUM', value: '$' + fmtAbbr(unusual.reduce((s, u) => s + u.premium, 0)), color: 'var(--mint)' },
        { label: 'CALLS / PUTS', value: `${unusual.filter(u => u.type === 'C').length} / ${unusual.filter(u => u.type === 'P').length}`, sub: 'flagged' },
        { label: 'TOP TICKER', value: summary[0]?.tk || '—', sub: fmtInt(summary[0]?.total) + ' contracts' },
        { label: 'P/C RATIO', value: round(unusual.filter(u => u.type === 'P').length / Math.max(1, unusual.filter(u => u.type === 'C').length), 2), color: 'var(--cyan)' },
      ],
      [
        <ListPanel key="a" title="UNUSUAL CONTRACTS" meta="yfinance options chains · 15min poll"
          headers={[{label:'TICKER'},{label:'TYPE'},{label:'EXP'},{label:'STRIKE',align:'right',num:true},
            {label:'VOL',align:'right',num:true},{label:'OI',align:'right',num:true},
            {label:'V/OI',align:'right',num:true},{label:'IV%',align:'right',num:true},
            {label:'MID',align:'right',num:true},{label:'PREM $',align:'right',num:true}]}
          rows={unusual.map(u => [
            <span className="lbl">{u.tk}</span>,
            u.type === 'C' ? <span className="up">CALL</span> : <span className="down">PUT</span>,
            <span className="mut">{u.exp}</span>,
            u.strike,
            <span className="num">{fmtInt(u.vol)}</span>,
            <span className="num mut">{fmtInt(u.oi)}</span>,
            <span className={u.ratio >= 2 ? 'warn' : ''}>{u.ratio.toFixed(2)}×</span>,
            u.iv.toFixed(1),
            u.mid.toFixed(2),
            <span className="mut">${fmtAbbr(u.premium)}</span>,
          ])} />,
        <ListPanel key="b" title="PER-TICKER SUMMARY"
          headers={[{label:'TKR'},{label:'CALLS',align:'right',num:true},{label:'PUTS',align:'right',num:true},
            {label:'P/C',align:'right',num:true},{label:'PREMIUM',align:'right',num:true},{label:'SKEW'}]}
          rows={summary.map(s => [
            <span className="lbl">{s.tk}</span>,
            <span className="up num">{fmtInt(s.calls)}</span>,
            <span className="down num">{fmtInt(s.puts)}</span>,
            <span className={s.pc_ratio > 1 ? 'down' : 'up'}>{s.pc_ratio.toFixed(2)}</span>,
            <span className="mut">${fmtAbbr(s.prem)}</span>,
            <div style={{ display: 'flex', height: 8, width: 90, background: 'var(--surface-3)' }}>
              <div style={{ width: `${(s.calls / Math.max(1, s.calls + s.puts)) * 100}%`, background: 'var(--mint)' }} />
              <div style={{ width: `${(s.puts / Math.max(1, s.calls + s.puts)) * 100}%`, background: 'var(--rose)' }} />
            </div>,
          ])} />,
      ]
    );
  };

  // Keep OPT alias pointing at OFL for older code paths
  ALL.OPT = ALL.OFL;

  ALL.COM = () => makeWrap(
    [
      { label: 'WTI CRUDE', value: '$69.82', color: 'var(--rose)', sub: '-1.21%' },
      { label: 'BRENT', value: '$73.41', color: 'var(--rose)', sub: '-0.92%' },
      { label: 'GOLD', value: '$2,682', color: 'var(--mint)', sub: '+0.18%' },
      { label: 'SILVER', value: '$31.45', color: 'var(--mint)', sub: '+0.42%' },
      { label: 'NAT GAS', value: '$2.84', color: 'var(--rose)', sub: '-2.41%' },
      { label: 'COPPER', value: '$4.21', color: 'var(--mint)', sub: '+0.62%' },
    ],
    [
      <ListPanel key="a" title="FUTURES · ENERGY / METALS / AGS / SOFTS" meta="CME · ICE"
        headers={[{label:'SYM'},{label:'CONTRACT'},{label:'LAST',align:'right',num:true},
          {label:'Δ%',align:'right',num:true},{label:'O.I.',align:'right',num:true},{label:'TREND',align:'center'}]}
        rows={[
          ['CL', 'Crude WTI Jan', 69.82, -1.21, 412380],
          ['BZ', 'Brent Mar', 73.41, -0.92, 318420],
          ['NG', 'Nat Gas Jan', 2.84, -2.41, 184220],
          ['RB', 'RBOB Gasoline', 1.98, -0.84, 92410],
          ['HO', 'Heating Oil', 2.21, -0.62, 84220],
          ['GC', 'Gold Feb', 2682.40, 0.18, 521840],
          ['SI', 'Silver Mar', 31.45, 0.42, 142850],
          ['HG', 'Copper Mar', 4.21, 0.62, 184290],
          ['PL', 'Platinum Jan', 968.20, 0.18, 42180],
          ['PA', 'Palladium Mar', 1042.40, 0.31, 18420],
          ['ZC', 'Corn Mar', 4.32, 0.42, 942180],
          ['ZS', 'Soybean Jan', 9.84, 0.12, 482140],
          ['ZW', 'Wheat Mar', 5.62, -0.32, 218450],
          ['KC', 'Coffee Mar', 3.18, 1.42, 94220],
          ['CC', 'Cocoa Mar', 8420, 2.18, 38420],
          ['SB', 'Sugar Mar', 21.4, -0.62, 142820],
          ['CT', 'Cotton Mar', 69.4, 0.18, 92410],
          ['LE', 'Live Cattle', 188.4, 0.31, 82180],
        ].map((r,i) => [
          <span className="lbl">{r[0]}</span>, r[1], fmt(r[2]),
          <span className={r[3] >= 0 ? 'up' : 'down'}>{r[3] >= 0 ? '+' : ''}{r[3].toFixed(2)}%</span>,
          <span className="mut">{fmtAbbr(r[4])}</span>,
          <Spark seed={i+20} up={r[3] >= 0} />,
        ])} />,
    ]
  );

  ALL.MCR = () => makeWrap(
    [
      { label: 'GLOBAL PMI', value: '50.4', sub: 'expanding' },
      { label: 'GDP NOWCAST', value: '+2.4%', color: 'var(--mint)' },
      { label: 'CORE PCE Y/Y', value: '2.8%', color: 'var(--rose)' },
      { label: 'UNEMPLOY', value: '4.1%', sub: 'US' },
      { label: 'FED FUNDS', value: '4.75-5.00%', sub: 'target' },
    ],
    [
      <ListPanel key="a" title="MACRO INDICATORS · GLOBAL"
        headers={[{label:'INDICATOR'},{label:'COUNTRY'},{label:'PERIOD'},{label:'ACTUAL',align:'right',num:true},
          {label:'FORECAST',align:'right',num:true},{label:'PREVIOUS',align:'right',num:true},{label:'SURPRISE'}]}
        rows={[
          ['Core PCE Y/Y', 'US', 'Oct', '2.8%', '2.8%', '2.7%', <Pill tone="cyan">INLINE</Pill>],
          ['Nonfarm Payrolls', 'US', 'Oct', '12K', '110K', '223K', <Pill tone="rose">MISS</Pill>],
          ['CPI Y/Y', 'EU', 'Oct', '2.0%', '2.0%', '1.7%', <Pill tone="cyan">INLINE</Pill>],
          ['Retail Sales M/M', 'US', 'Oct', '+0.4%', '+0.3%', '+0.4%', <Pill tone="mint">BEAT</Pill>],
          ['Industrial Prod', 'CN', 'Oct', '+5.3%', '+5.6%', '+5.4%', <Pill tone="rose">MISS</Pill>],
          ['Manufacturing PMI', 'GE', 'Nov', '43.0', '43.2', '43.0', <Pill tone="cyan">INLINE</Pill>],
          ['Unemployment', 'US', 'Oct', '4.1%', '4.1%', '4.1%', <Pill tone="cyan">INLINE</Pill>],
          ['BoE Rate Decision', 'UK', 'Nov', '4.75%', '4.75%', '5.00%', <Pill tone="cyan">INLINE</Pill>],
          ['GDP Q/Q', 'JP', 'Q3', '+0.2%', '+0.2%', '+0.5%', <Pill tone="cyan">INLINE</Pill>],
        ]} />,
    ]
  );

  // ============ GEOPOLITICS ============
  const makeGeoIncidents = (kind, count = 18, seed = 1) => {
    const r = rng(seed);
    const places = ['Ukraine','Gaza','Lebanon','Syria','Yemen','Sudan','Myanmar','DR Congo','Somalia','Mali','West Bank','Red Sea','Taiwan Strait','South China Sea'];
    const sources = ['ACLED','OSINT','Reuters','AP','AFP','Local'];
    return Array.from({ length: count }, (_, i) => ({
      ts: Math.floor(between(2, 720, r)) + 'm',
      severity: pick(['LOW','MED','HIGH','CRIT'], r),
      country: pick(places, r),
      source: pick(sources, r),
      headline: pick([
        'Reports of shelling near urban center; civilian casualties unconfirmed',
        'Drone activity reported along contested border',
        'Diplomatic note issued by foreign ministry',
        'Convoy disrupted; corridor remains closed',
        'Strike on infrastructure target acknowledged',
        'Talks scheduled to resume next week',
        'Curfew extended in affected districts',
        'Maritime incident reported in shipping lane',
      ], r),
    }));
  };
  ALL.WAR = () => makeWrap(
    [
      { label: 'ACTIVE CONFLICTS', value: '23', color: 'var(--rose)' },
      { label: 'EVENTS 24H', value: '412', sub: 'ACLED' },
      { label: 'CASUALTIES Y', value: '74,210', sub: 'reported' },
      { label: 'DISPLACED', value: '124M', color: 'var(--amber)', sub: 'UNHCR' },
    ],
    [
      <ListPanel key="a" title="ACTIVE CONFLICT FEED · 24H" meta="ACLED · OSINT · multi-source"
        headers={[{label:'AGO'},{label:'SEV'},{label:'COUNTRY'},{label:'SOURCE'},{label:'HEADLINE'}]}
        rows={makeGeoIncidents('war').map(it => [
          <span className="mut">{it.ts}</span>,
          <Pill tone={it.severity === 'CRIT' ? 'rose' : it.severity === 'HIGH' ? 'amber' : 'cyan'}>{it.severity}</Pill>,
          <span className="lbl">{it.country}</span>,
          <span className="mut">{it.source}</span>,
          it.headline,
        ])} />,
    ]
  );

  ALL.POL = () => makeWrap(
    [
      { label: 'GLOBAL UNREST IDX', value: '6.4 / 10', color: 'var(--amber)' },
      { label: 'PROTESTS 7D', value: '184', sub: 'organized' },
      { label: 'CABINET CHANGES', value: '12 YTD', sub: 'G20 nations' },
      { label: 'POLITICAL RISK', value: 'HIGH', color: 'var(--amber)' },
    ],
    [
      <ListPanel key="a" title="POLITICAL DEVELOPMENTS · 24H"
        headers={[{label:'AGO'},{label:'COUNTRY'},{label:'TYPE'},{label:'HEADLINE'}]}
        rows={[
          ['12m', 'France', 'BUDGET', 'No-confidence motion filed against PM; vote scheduled'],
          ['1h', 'Germany', 'COALITION', 'Coalition talks resume after weekend negotiations'],
          ['2h', 'Brazil', 'IMPEACH', 'Opposition files motion in lower house'],
          ['3h', 'South Korea', 'PROTEST', 'Mass demonstrations enter third consecutive day'],
          ['4h', 'Turkey', 'OPP', 'Main opposition leader summoned by prosecutor'],
          ['5h', 'Israel', 'COALITION', 'Coalition partner threatens withdrawal over draft bill'],
          ['7h', 'Argentina', 'REFORM', 'Senate passes labor reform package'],
          ['8h', 'Romania', 'ELECTION', 'Election authority finalizes second-round candidates'],
        ]} />,
    ]
  );

  ALL.SAN = () => makeWrap(null, [
    <ListPanel key="a" title="SANCTIONS · NEW DESIGNATIONS · 30 DAYS"
      meta="OFAC · EU · UK · UN consolidated"
      headers={[{label:'DATE'},{label:'BODY'},{label:'TARGET'},{label:'CATEGORY'},{label:'REASON'}]}
      rows={[
        ['18 Nov', 'OFAC', '37 individuals · 14 entities', 'PEP / SDGT', 'Iran proxy financing'],
        ['15 Nov', 'EU', '11 vessels', 'Maritime', 'Shadow fleet sanctions evasion'],
        ['12 Nov', 'OFAC', 'Crypto mixer service', 'CYBER', 'Money laundering, ransomware'],
        ['08 Nov', 'UK', '6 entities', 'Defense', 'Military procurement network'],
        ['05 Nov', 'UN', '2 individuals', 'NK', 'Designated under DPRK regime'],
        ['02 Nov', 'OFAC', '21 individuals', 'NARCO', 'Sinaloa cartel affiliates'],
        ['28 Oct', 'EU', '3 corporations', 'EXPORT CTRL', 'Dual-use technology violations'],
      ]} />,
  ]);

  ALL.REF = () => makeWrap(
    [
      { label: 'TOTAL DISPLACED', value: '124M', color: 'var(--amber)', sub: 'UNHCR Q3' },
      { label: 'INTERNAL', value: '76M', sub: 'IDMC' },
      { label: 'REFUGEES', value: '43M', sub: 'cross-border' },
      { label: 'ASYLUM PENDING', value: '5.2M', sub: 'pending' },
      { label: 'NEW DISPL 30D', value: '+412K', color: 'var(--rose)' },
    ],
    [
      <ListPanel key="a" title="DISPLACEMENT · BY ORIGIN COUNTRY"
        headers={[{label:'ORIGIN'},{label:'TOTAL',align:'right',num:true},{label:'30D Δ',align:'right',num:true},{label:'HOST · TOP 3'}]}
        rows={[
          ['Syria', '13.8M', '+2,400', 'Turkey · Lebanon · Jordan'],
          ['Ukraine', '6.7M', '+18,400', 'Germany · Poland · Czechia'],
          ['Afghanistan', '6.4M', '+8,200', 'Pakistan · Iran · Germany'],
          ['Sudan', '11.0M', '+142,000', 'Chad · South Sudan · Egypt'],
          ['Venezuela', '7.7M', '+4,100', 'Colombia · Peru · USA'],
          ['Myanmar', '3.5M', '+18,200', 'Bangladesh · India · Thailand'],
          ['DR Congo', '7.2M', '+92,000', 'Uganda · Rwanda · Burundi'],
          ['Somalia', '3.9M', '+12,000', 'Ethiopia · Kenya · Yemen'],
        ]} />,
    ]
  );

  ALL.ELE = () => makeWrap(null, [
    <ListPanel key="a" title="UPCOMING ELECTIONS · 12 MONTHS"
      headers={[{label:'DATE'},{label:'COUNTRY'},{label:'TYPE'},{label:'STAKES'},{label:'POLLS'}]}
      rows={[
        ['08 Dec 2024', 'Romania', 'Presidential R2', 'Reform vs nationalist', '49% / 51%'],
        ['08 Dec 2024', 'Ghana', 'Presidential', 'Cost of living', '52% NDC'],
        ['15 Jan 2025', 'Czechia', 'Senate by-elec', 'Coalition test', '—'],
        ['23 Feb 2025', 'Germany', 'Federal (snap)', 'Govt formation', 'CDU 32%, AfD 19%'],
        ['09 Mar 2025', 'Norway', 'Parliamentary', 'Energy policy', 'Labour 28%, Cons 22%'],
        ['04 May 2025', 'Australia', 'Federal', 'Govt incumbency', 'ALP 51%, LNP 49%'],
        ['18 May 2025', 'Poland', 'Presidential', 'Tusk vs PiS', 'Tied'],
        ['Q3 2025', 'Norway', 'Parliamentary', 'Energy / Arctic', '—'],
      ]} />,
  ]);

  ALL.DIP = () => makeWrap(null, [
    <ListPanel key="a" title="DIPLOMATIC ACTIVITY · 7 DAYS"
      headers={[{label:'AGO'},{label:'PARTIES'},{label:'VENUE'},{label:'TOPIC'}]}
      rows={[
        ['2h', 'US ↔ China', 'Lima G20', 'Trade, tech export controls'],
        ['8h', 'France ↔ Germany', 'Berlin', 'EU defense fund'],
        ['1d', 'India ↔ Brazil', 'Rio', 'BRICS expansion, currency'],
        ['1d', 'Saudi ↔ Iran', 'Riyadh', 'Yemen ceasefire framework'],
        ['2d', 'Turkey ↔ Syria', 'Doha', 'Border security, refugees'],
        ['3d', 'Japan ↔ ROK', 'Tokyo', 'Trilateral security'],
        ['4d', 'UK ↔ EU', 'Brussels', 'Veterinary agreement'],
      ]} />,
  ]);

  ALL.TER = () => makeWrap(
    [
      { label: 'INCIDENTS 24H', value: '47', color: 'var(--amber)' },
      { label: 'INCIDENTS 7D', value: '312', sub: 'GTD-style' },
      { label: 'TOP REGION', value: 'Sahel', sub: '128 events' },
      { label: 'CRIT 24H', value: '4', color: 'var(--rose)' },
    ],
    [
      <ListPanel key="a" title="SECURITY INCIDENTS · 24H"
        headers={[{label:'AGO'},{label:'SEV'},{label:'REGION'},{label:'TYPE'},{label:'BRIEF'}]}
        rows={makeGeoIncidents('ter', 16, 99).map(it => [
          <span className="mut">{it.ts}</span>,
          <Pill tone={it.severity === 'CRIT' ? 'rose' : it.severity === 'HIGH' ? 'amber' : 'cyan'}>{it.severity}</Pill>,
          <span className="lbl">{it.country}</span>,
          pick(['IED','SHOOTING','ABDUCTION','ARSON','RIOT','MARITIME'], rng(it.headline.length)),
          it.headline,
        ])} />,
    ]
  );

  ALL.INT = () => makeWrap(null, [
    <ListPanel key="a" title="INTELLIGENCE BRIEFINGS · OSINT" meta="open-source synthesis"
      headers={[{label:'AGO'},{label:'CLASS'},{label:'DOMAIN'},{label:'SUMMARY'}]}
      rows={[
        ['1h', 'UNCLASS', 'CYBER', 'New malware family targeting industrial PLCs observed in EU energy sector'],
        ['4h', 'UNCLASS', 'NAVAL', 'Carrier group exercise scheduled to commence next 72h in Pacific'],
        ['1d', 'UNCLASS', 'SPACE', 'New satellite launch suspected payload imaging'],
        ['1d', 'UNCLASS', 'POLITICAL', 'Cabinet reshuffle anticipated following budget vote'],
        ['2d', 'UNCLASS', 'ECON', 'Capital outflows from emerging market accelerating'],
      ]} />,
  ]);

  // ============ ENERGY ============
  ALL.OIL = () => makeWrap(
    [
      { label: 'WTI', value: '$69.82', color: 'var(--rose)', sub: '-1.21%' },
      { label: 'BRENT', value: '$73.41', color: 'var(--rose)', sub: '-0.92%' },
      { label: 'NAT GAS', value: '$2.84', color: 'var(--rose)' },
      { label: 'CRUDE INV', value: '+2.1MB', sub: 'EIA weekly' },
      { label: 'OPEC+ QUOTA', value: '40.46MB/d', sub: 'Jan 2025' },
      { label: 'STRAT RES', value: '393MB', sub: 'SPR' },
    ],
    [
      <ListPanel key="a" title="OIL & GAS · GLOBAL BENCHMARKS"
        headers={[{label:'GRADE'},{label:'PRICE',align:'right',num:true},{label:'Δ%',align:'right',num:true},{label:'DIFF VS BRENT',align:'right'}]}
        rows={[
          ['WTI Cushing', 69.82, -1.21, '-3.59'],
          ['Brent', 73.41, -0.92, '0.00'],
          ['Dubai', 71.84, -0.84, '-1.57'],
          ['Urals (Russia)', 60.10, -1.42, '-13.31'],
          ['Bonny Light', 74.92, -0.71, '+1.51'],
          ['Maya (Mexico)', 65.40, -1.18, '-8.01'],
          ['WCS (Canada)', 51.20, -1.31, '-22.21'],
          ['ESPO (Russia)', 62.40, -1.41, '-11.01'],
        ].map(r => [r[0], fmt(r[1]),
          <span className={r[2] >= 0 ? 'up' : 'down'}>{r[2].toFixed(2)}%</span>,
          <span className="mut">{r[3]}</span>])} />,
      <ListPanel key="b" title="REFINERY UTILIZATION & PIPELINES"
        headers={[{label:'REGION'},{label:'UTIL %',align:'right',num:true},{label:'NOTE'}]}
        rows={[
          ['US Gulf Coast', 92.4, 'Steady'],
          ['US Midwest', 88.1, 'Whiting maintenance'],
          ['NW Europe', 84.2, 'Strikes France'],
          ['China indep', 71.5, <span className="warn">Lower runs</span>],
          ['Singapore', 89.4, 'Stable'],
          ['Russia', 76.1, <span className="warn">Strikes impact</span>],
          ['Saudi Arabia', 94.2, 'Strong'],
        ]} />,
    ]
  );

  ALL.NUC = () => makeWrap(
    [
      { label: 'OPERABLE', value: '440', sub: 'reactors' },
      { label: 'CONSTRUCTION', value: '60', color: 'var(--mint)' },
      { label: 'CAPACITY GW', value: '395', sub: 'net' },
      { label: 'AVG AGE', value: '32 yr' },
      { label: 'URANIUM U3O8', value: '$77.20', color: 'var(--mint)', sub: '+0.42%' },
    ],
    [
      <ListPanel key="a" title="NUCLEAR FLEET · BY COUNTRY"
        headers={[{label:'COUNTRY'},{label:'OPER',align:'right',num:true},{label:'CONSTR',align:'right',num:true},
          {label:'CAP GW',align:'right',num:true},{label:'% ELEC',align:'right',num:true}]}
        rows={[
          ['United States', 94, 0, 96.5, 18.6],
          ['France', 56, 1, 61.4, 64.8],
          ['China', 55, 27, 53.2, 4.9],
          ['Russia', 36, 4, 26.8, 19.6],
          ['South Korea', 26, 2, 25.8, 30.4],
          ['India', 23, 8, 7.4, 3.1],
          ['Canada', 19, 0, 14.2, 14.8],
          ['Ukraine', 15, 2, 13.1, 51.2],
          ['UK', 9, 2, 5.9, 14.5],
          ['Japan', 33, 0, 31.7, 6.1],
        ]} />,
    ]
  );

  ALL.REN = () => makeWrap(
    [
      { label: 'GLOBAL CAP GW', value: '3,870', color: 'var(--mint)', sub: '+12.4% YoY' },
      { label: 'SOLAR ADDED', value: '+462 GW', color: 'var(--mint)', sub: 'YTD' },
      { label: 'WIND ADDED', value: '+114 GW', color: 'var(--mint)' },
      { label: 'STORAGE GWh', value: '218', sub: 'utility' },
      { label: 'GREEN H2 GW', value: '4.2', sub: 'electrolyzer cap' },
    ],
    [
      <ListPanel key="a" title="RENEWABLE CAPACITY · BY TECHNOLOGY"
        headers={[{label:'TECH'},{label:'GW',align:'right',num:true},{label:'Δ YoY %',align:'right',num:true},{label:'BAR'}]}
        rows={[
          ['Solar PV', 1840, 23.1],
          ['Wind onshore', 920, 8.4],
          ['Hydro', 1380, 1.1],
          ['Wind offshore', 79, 14.8],
          ['Bioenergy', 152, 2.4],
          ['Geothermal', 16, 2.1],
          ['CSP', 7.2, 5.1],
        ].map(([t, c, d]) => [
          t, fmt(c, 0), <span className="up">+{d.toFixed(1)}%</span>,
          <Bars values={[c * 0.4, c * 0.6, c * 0.7, c * 0.85, c]} w={140} />,
        ])} />,
    ]
  );

  ALL.GAS = () => makeWrap(
    [
      { label: 'HENRY HUB', value: '$2.84', color: 'var(--rose)', sub: '-2.41%' },
      { label: 'TTF EU', value: '€42.80', color: 'var(--mint)', sub: '+1.81%' },
      { label: 'JKM ASIA', value: '$14.20', color: 'var(--mint)' },
      { label: 'EU STORAGE', value: '88.4%', sub: 'AGSI' },
      { label: 'US STORAGE', value: '4,012 Bcf', sub: '+18 Bcf' },
    ],
    [
      <ListPanel key="a" title="LNG TERMINALS · UTILIZATION (latest)"
        headers={[{label:'TERMINAL'},{label:'COUNTRY'},{label:'UTIL %',align:'right',num:true},{label:'STATUS'}]}
        rows={[
          ['Sabine Pass', 'USA', 94.1, <Pill tone="mint">NORMAL</Pill>],
          ['Cameron LNG', 'USA', 88.2, <Pill tone="mint">NORMAL</Pill>],
          ['Corpus Christi', 'USA', 91.8, <Pill tone="mint">NORMAL</Pill>],
          ['Gorgon', 'Australia', 96.4, <Pill tone="mint">NORMAL</Pill>],
          ['Ras Laffan', 'Qatar', 95.1, <Pill tone="mint">NORMAL</Pill>],
          ['Yamal LNG', 'Russia', 72.0, <Pill tone="amber">PARTIAL</Pill>],
          ['Bonny Island', 'Nigeria', 41.2, <Pill tone="rose">DISRUPTED</Pill>],
          ['Hammerfest', 'Norway', 92.1, <Pill tone="mint">NORMAL</Pill>],
        ]} />,
    ]
  );

  ALL.ELG = () => {
    const grids = [
      ['ERCOT (Texas)', 64.2, 12, 8.4, 'Stable'],
      ['CAISO (California)', 38.4, 22, 18.2, 'Stable'],
      ['MISO (Midwest)', 78.1, 14, 4.1, 'Stable'],
      ['PJM (Mid-Atlantic)', 92.4, 18, 3.4, 'Stable'],
      ['NYISO', 22.1, 11, 6.8, 'Stable'],
      ['NEISO (New England)', 16.4, 8, 5.2, 'Stable'],
      ['SPP', 38.4, 22, 7.4, 'Stable'],
      ['UK NG', 32.1, 12, 24.1, 'Stable'],
      ['Germany 50Hertz', 22.4, 14, 38.4, 'Stable'],
      ['France RTE', 51.2, 18, 12.1, 'Stable'],
    ];
    return makeWrap(
      [
        { label: 'US PEAK', value: '614 GW', sub: 'projected' },
        { label: 'EU PEAK', value: '432 GW' },
        { label: 'CARBON INT g/kWh', value: '342', color: 'var(--amber)' },
        { label: 'OUTAGES 24H', value: '12', sub: 'major' },
      ],
      [
        <ListPanel key="a" title="POWER GRIDS · LOAD / RENEWABLES / STATUS"
          headers={[{label:'OPERATOR'},{label:'LOAD GW',align:'right',num:true},
            {label:'PRICE $/MWh',align:'right',num:true},{label:'WIND+SOLAR %',align:'right',num:true},{label:'STATUS'}]}
          rows={grids.map(g => [
            g[0], fmt(g[1], 1), g[2], g[3].toFixed(1), <Pill tone="mint">{g[4]}</Pill>,
          ])} />,
      ]
    );
  };

  ALL.CLI = () => makeWrap(
    [
      { label: 'CO₂ MAUNA LOA', value: '424.6 ppm', color: 'var(--rose)', sub: '+2.8 YoY' },
      { label: 'GLOBAL T ANOM', value: '+1.54°C', color: 'var(--rose)' },
      { label: 'ARCTIC SEA ICE', value: '4.8M km²', color: 'var(--rose)', sub: 'min' },
      { label: 'ANTARCTIC ICE', value: '2.1M km²', color: 'var(--rose)' },
      { label: 'OCEAN HEAT', value: 'record', color: 'var(--rose)' },
    ],
    [
      <ListPanel key="a" title="CLIMATE INDICATORS · LATEST"
        headers={[{label:'METRIC'},{label:'VALUE'},{label:'TREND'},{label:'SOURCE'}]}
        rows={[
          ['Atmospheric CO₂', '424.6 ppm', <span className="down">↑ +2.8 ppm/yr</span>, 'NOAA Mauna Loa'],
          ['Global mean T anomaly', '+1.54°C', <span className="down">↑ Record 2024</span>, 'NASA GISS'],
          ['Arctic sea ice min', '4.8M km²', <span className="down">↓ -13%/decade</span>, 'NSIDC'],
          ['Greenland mass', '-281 Gt/yr', <span className="down">↓ accelerating</span>, 'GRACE-FO'],
          ['Sea level rise', '+3.4 mm/yr', <span className="down">↑ accelerating</span>, 'Jason-3'],
          ['Ocean heat content', '434 ZJ', <span className="down">↑ record</span>, 'NCEI'],
          ['Methane (atm)', '1934 ppb', <span className="down">↑ +14 ppb/yr</span>, 'NOAA'],
        ]} />,
    ]
  );

  // ============ CYBER ============
  ALL.CVE = () => makeWrap(
    [
      { label: 'CRIT 24H', value: '14', color: 'var(--rose)' },
      { label: 'HIGH 24H', value: '38', color: 'var(--amber)' },
      { label: 'CISA KEV', value: '1,287', sub: 'exploited' },
      { label: 'NEW 30D', value: '2,841', sub: 'NVD' },
      { label: 'RANSOM VICTIMS 30D', value: '342', color: 'var(--rose)' },
    ],
    [
      <ListPanel key="a" title="CRITICAL VULNERABILITIES · LAST 7 DAYS"
        meta="NVD · CISA KEV · vendor advisories"
        headers={[{label:'CVE'},{label:'CVSS',align:'right',num:true},{label:'PRODUCT'},{label:'STATUS'},{label:'SUMMARY'}]}
        rows={[
          ['CVE-2024-49039', 9.8, 'Microsoft Task Sched', <Pill tone="rose">KEV</Pill>, 'Elevation of privilege, actively exploited'],
          ['CVE-2024-43491', 9.8, 'Windows Update', <Pill tone="rose">KEV</Pill>, 'Rollback of patches enables RCE'],
          ['CVE-2024-47575', 9.8, 'Fortinet FortiManager', <Pill tone="rose">KEV</Pill>, 'Missing auth, RCE in API'],
          ['CVE-2024-9474',  7.2, 'Palo Alto PAN-OS',     <Pill tone="rose">KEV</Pill>, 'Privilege escalation on management web'],
          ['CVE-2024-38812', 9.8, 'VMware vCenter',       <Pill tone="amber">PoC</Pill>, 'Heap overflow in DCERPC'],
          ['CVE-2024-21302', 7.8, 'Windows Secure Kernel',<Pill tone="cyan">PATCH</Pill>, 'Privilege escalation via VBS'],
          ['CVE-2024-3094',  10.0, 'XZ Utils backdoor',   <Pill tone="rose">KEV</Pill>, 'Supply chain compromise'],
          ['CVE-2024-7593',  9.8, 'Ivanti vTM',           <Pill tone="amber">PATCH</Pill>, 'Auth bypass via crafted requests'],
          ['CVE-2024-8190',  7.2, 'Ivanti Cloud Service', <Pill tone="rose">KEV</Pill>, 'OS command injection'],
        ]} />,
    ]
  );

  ALL.THR = () => makeWrap(null, [
    <ListPanel key="a" title="THREAT ACTORS · RECENT ACTIVITY"
      headers={[{label:'ACTOR'},{label:'ALIAS'},{label:'ORIGIN'},{label:'TTP'},{label:'TARGETS · 30D'}]}
      rows={[
        ['APT28', 'Fancy Bear', 'RU/GRU', 'Spearphish / Credential', 'Govt EU, defense'],
        ['APT29', 'Cozy Bear', 'RU/SVR', 'Supply chain', 'Cloud SaaS, MSPs'],
        ['APT41', 'Wicked Panda', 'CN', 'Web shells, dual-use', 'Telecom, healthcare'],
        ['Lazarus', 'Hidden Cobra', 'KP', 'Cryptotheft, RAT', 'Crypto exchanges, SWIFT'],
        ['Sandworm', 'Voodoo Bear', 'RU/GRU', 'Wiper, ICS', 'Energy Ukraine, ALLIES'],
        ['Charming Kitten', 'APT35', 'IR', 'Credential phishing', 'Think tanks, dissidents'],
        ['Scattered Spider', 'UNC3944', 'CRIM', 'Social-eng helpdesk', 'Casinos, retail, telco'],
        ['LockBit', 'Ransomware', 'CRIM', 'Affiliate RaaS', 'Manufacturing, healthcare'],
      ]} />,
  ]);

  ALL.DAR = () => makeWrap(null, [
    <ListPanel key="a" title="DARK WEB LEAK MARKET MONITOR"
      meta="aggregate scrapers · sanitized"
      headers={[{label:'AGO'},{label:'FORUM'},{label:'LISTING'},{label:'PRICE'},{label:'VICTIM'}]}
      rows={[
        ['2h', 'XSS', 'DB · 1.2M records', '$8,400', 'European retail chain'],
        ['4h', 'Exploit', 'RDP access', '$1,200', 'Financial services SME'],
        ['8h', 'BreachF', 'Healthcare PHI 480k', '$24k', 'Hospital network US'],
        ['12h', 'Telegram', 'Credentials 12M', '$3,200', 'SaaS provider'],
        ['1d', 'Exploit', '0-day VPN bypass', '$150k', 'Major vendor'],
        ['1d', 'XSS', 'Ransomware as service', '20% cut', 'Affiliate program'],
      ]} />,
  ]);

  ALL.LEK = () => makeWrap(null, [
    <ListPanel key="a" title="DATA BREACHES · 30 DAYS"
      headers={[{label:'DATE'},{label:'ORGANIZATION'},{label:'RECORDS',align:'right',num:true},{label:'TYPE'},{label:'DISCLOSURE'}]}
      rows={[
        ['18 Nov', 'Major US utility', '4.2M', 'PII/SSN', 'Public'],
        ['12 Nov', 'European airline', '1.8M', 'PII/PAY', 'Regulatory'],
        ['08 Nov', 'Healthcare network', '8.4M', 'PHI', 'HHS'],
        ['05 Nov', 'Telecom carrier', '2.2M', 'PII/Comms metadata', 'Press'],
        ['02 Nov', 'University system', '420k', 'PII/EDU', 'IT'],
        ['28 Oct', 'Retail chain', '12.4M', 'Payment cards', 'Public'],
        ['24 Oct', 'Software SaaS', '88k', 'Auth tokens', 'Customer notice'],
      ]} />,
  ]);

  ALL.SOC = () => makeWrap(
    [
      { label: 'NARRATIVES 24H', value: '142', sub: 'tracked' },
      { label: 'COORDINATED', value: '18', color: 'var(--amber)' },
      { label: 'TOP HASHTAG', value: '#geopol' },
      { label: 'BOT %', value: '12.4%', color: 'var(--amber)' },
    ],
    [
      <ListPanel key="a" title="EMERGING NARRATIVES · MULTI-PLATFORM"
        headers={[{label:'NARRATIVE'},{label:'PLATFORM'},{label:'VOLUME',align:'right',num:true},{label:'INAUTH %',align:'right',num:true}]}
        rows={[
          ['Election integrity claims', 'X / Telegram', 412380, 18.4],
          ['Climate policy backlash', 'X / TikTok', 218400, 8.2],
          ['Geopolitical attribution', 'Reddit / 4chan', 142820, 24.1],
          ['Crypto scam narratives', 'X / Telegram', 88420, 42.1],
          ['Synthetic celebrity', 'TikTok / IG', 64810, 31.2],
        ]} />,
    ]
  );

  ALL.HAC = () => makeWrap(null, [
    <ListPanel key="a" title="ACTIVE INCIDENT RESPONSE TICKETS"
      headers={[{label:'INC #'},{label:'SEV'},{label:'STAGE'},{label:'SECTOR'},{label:'NOTE'}]}
      rows={[
        ['IR-2024-1284', <Pill tone="rose">CRIT</Pill>, 'Containment', 'Healthcare', 'Ransomware double-extort, EDR isolation in progress'],
        ['IR-2024-1281', <Pill tone="amber">HIGH</Pill>, 'Investigation', 'Manufacturing', 'OT-IT lateral movement under analysis'],
        ['IR-2024-1278', <Pill tone="amber">HIGH</Pill>, 'Eradication', 'Finance', 'BEC + wire fraud, funds recall pending'],
        ['IR-2024-1275', <Pill tone="cyan">MED</Pill>, 'Recovery', 'Retail', 'Skimmer removed, PCI forensics underway'],
        ['IR-2024-1271', <Pill tone="cyan">MED</Pill>, 'Lessons', 'SaaS', 'Token leak, rotation complete'],
      ]} />,
  ]);

  // ============ SCIENCE ============
  ALL.SOL = () => makeWrap(
    [
      { label: 'Kp INDEX', value: '4.0', color: 'var(--amber)', sub: 'unsettled' },
      { label: 'SOLAR FLUX', value: '218 sfu', color: 'var(--mint)' },
      { label: 'X-RAY CLASS', value: 'C2.4', color: 'var(--cyan)' },
      { label: 'CME ACTIVITY', value: '2 / 24h' },
      { label: 'AURORA', value: 'lat 55°+', sub: 'forecast' },
    ],
    [
      <div className="panel" key="a" style={{ display: 'flex', flexDirection: 'column' }}>
        <Head title="GEOMAGNETIC ACTIVITY · LAST 72H (Kp)" meta="NOAA SWPC" />
        <div style={{ padding: 16 }}>
          <svg viewBox="0 0 720 200" width="100%" height="220" preserveAspectRatio="none">
            {[1,2,3,4,5,6,7,8].map(k => (
              <line key={k} x1={20} x2={700} y1={200 - k*22} y2={200 - k*22}
                stroke={k >= 5 ? 'var(--rose-dim)' : 'var(--border)'} strokeDasharray="2 4" />
            ))}
            {Array.from({length: 24}, (_, i) => {
              const kp = Math.max(0.5, 2.5 + Math.sin(i / 3) * 1.8 + (i === 16 ? 2.2 : 0));
              const x = 20 + i * 28;
              const h = kp * 22;
              const col = kp >= 5 ? 'var(--rose)' : kp >= 4 ? 'var(--amber)' : 'var(--mint)';
              return <rect key={i} x={x} y={200 - h} width="24" height={h} fill={col} opacity="0.85" />;
            })}
          </svg>
        </div>
      </div>,
      <ListPanel key="b" title="RECENT FLARES · GOES X-RAY"
        headers={[{label:'TIME UTC'},{label:'CLASS'},{label:'REGION'},{label:'CME?'}]}
        rows={[
          ['14:32', 'C2.4', 'AR3852', 'No'],
          ['12:18', 'C5.1', 'AR3854', 'Halo, slow'],
          ['09:42', 'M1.2', 'AR3854', 'Yes, Earth-directed'],
          ['07:12', 'C1.8', 'AR3851', 'No'],
          ['03:04', 'B9.4', 'AR3852', 'No'],
        ]} />,
    ]
  );

  ALL.RKT = () => makeWrap(
    [
      { label: 'NEXT', value: 'T -3d 14h', color: 'var(--cyan)', sub: 'Falcon 9 · Starlink' },
      { label: 'LAUNCHES 30D', value: '24', sub: 'global' },
      { label: 'YTD', value: '178', color: 'var(--mint)' },
      { label: 'STARLINK Y', value: '42' },
    ],
    [
      <ListPanel key="a" title="UPCOMING LAUNCHES · 30 DAYS"
        meta="thespacedevs.com"
        headers={[{label:'T-MINUS'},{label:'VEHICLE'},{label:'PROVIDER'},{label:'PAD'},{label:'PAYLOAD'},{label:'STATUS'}]}
        rows={[
          ['T -3d 14h', 'Falcon 9 B5', 'SpaceX', 'CCAFS SLC-40', 'Starlink 12-3', <Pill tone="mint">GO</Pill>],
          ['T -5d 02h', 'Falcon 9 B5', 'SpaceX', 'VSFB SLC-4E', 'Starlink 9-14', <Pill tone="mint">GO</Pill>],
          ['T -6d 08h', 'New Glenn', 'Blue Origin', 'LC-36', 'Blue Ring + payload', <Pill tone="amber">REVIEW</Pill>],
          ['T -8d 21h', 'CZ-3B/E', 'CASC', 'Xichang', 'ChinaSat', <Pill tone="mint">GO</Pill>],
          ['T -12d', 'Ariane 6', 'Arianespace', 'Kourou ELA-4', 'Sentinel-1C', <Pill tone="mint">GO</Pill>],
          ['T -14d', 'Vulcan VC2S', 'ULA', 'CCAFS SLC-41', 'USSF-106', <Pill tone="mint">GO</Pill>],
          ['T -18d', 'Soyuz 2.1a', 'Roscosmos', 'Baikonur 31/6', 'Progress MS-29', <Pill tone="mint">GO</Pill>],
        ]} />,
    ]
  );

  ALL.NEO = () => makeWrap(
    [
      { label: 'NEAR APPROACHES 7D', value: '34' },
      { label: 'HAZARDOUS', value: '4', color: 'var(--amber)' },
      { label: 'CLOSEST', value: '1.2 LD', sub: '2024 VC7' },
      { label: 'LARGEST', value: '850 m', sub: '2003 BG54' },
    ],
    [
      <ListPanel key="a" title="NEAR-EARTH ASTEROIDS · NEXT 14 DAYS"
        meta="api.nasa.gov · CNEOS"
        headers={[{label:'OBJECT'},{label:'APPROACH'},{label:'DIAM m',align:'right',num:true},
          {label:'MISS DIST LD',align:'right',num:true},{label:'VEL km/s',align:'right',num:true},{label:'PHA'}]}
        rows={[
          ['2024 WJ', '24 Nov 14:21', 38, 4.2, 12.4, ''],
          ['2024 VC7', '25 Nov 03:48', 18, 1.2, 8.1, <Pill tone="rose">PHA</Pill>],
          ['2024 UW2', '26 Nov 22:14', 240, 18.4, 14.8, <Pill tone="amber">PHA</Pill>],
          ['2018 GD2', '27 Nov 11:32', 410, 38.4, 21.4, ''],
          ['2024 VR3', '28 Nov 06:18', 22, 2.8, 6.4, ''],
          ['2003 BG54', '01 Dec', 850, 42.1, 22.1, <Pill tone="amber">PHA</Pill>],
          ['2018 VZ2', '04 Dec', 140, 24.8, 14.1, ''],
          ['2024 SP4', '08 Dec', 88, 12.4, 9.2, <Pill tone="rose">PHA</Pill>],
        ]} />,
    ]
  );

  ALL.FIR = () => makeWrap(
    [
      { label: 'ACTIVE FIRES 24H', value: '12,418', color: 'var(--rose)' },
      { label: 'HIGH CONFIDENCE', value: '4,210', color: 'var(--amber)' },
      { label: 'BRIGHTNESS PEAK', value: '482 K' },
      { label: 'TOP REGION', value: 'Africa', sub: 'Sahel · 38%' },
    ],
    [
      <div className="panel" key="a" style={{ display: 'flex', flexDirection: 'column' }}>
        <Head title="WILDFIRE HOTSPOTS · GLOBAL" meta="NASA FIRMS VIIRS · NRT" right={<Pill tone="amber">KEY REQUIRED</Pill>} />
        <div style={{ padding: 16, color: 'var(--muted)', textAlign: 'center', marginTop: 40 }}>
          <div style={{ fontSize: 11 }}>Connect a NASA FIRMS API key to load the live VIIRS/MODIS hotspot map.</div>
          <div style={{ marginTop: 8, fontSize: 10 }}>firms.modaps.eosdis.nasa.gov/api</div>
        </div>
      </div>,
      <ListPanel key="b" title="LARGEST ACTIVE FIRES"
        headers={[{label:'REGION'},{label:'COUNTRY'},{label:'AREA km²',align:'right',num:true},{label:'CONTAINED %',align:'right',num:true}]}
        rows={[
          ['Pantanal', 'Brazil', 1842, 31],
          ['Cerrado N', 'Brazil', 1240, 18],
          ['Boreal Yakutia', 'Russia', 980, 12],
          ['British Columbia', 'Canada', 412, 64],
          ['Northern Territory', 'Australia', 318, 42],
          ['Andalusia', 'Spain', 121, 78],
          ['Attica', 'Greece', 84, 88],
        ]} />,
    ]
  );

  ALL.BIO = () => makeWrap(
    [
      { label: 'WHO ALERTS', value: '4', color: 'var(--amber)' },
      { label: 'OUTBREAKS 30D', value: '42', sub: 'tracked' },
      { label: 'WASTEWATER', value: '↑', color: 'var(--rose)', sub: 'COVID NA' },
      { label: 'AVIAN H5N1', value: 'spreading', color: 'var(--amber)' },
    ],
    [
      <ListPanel key="a" title="DISEASE SURVEILLANCE · 30 DAYS"
        meta="WHO · CDC · ECDC · open RSS"
        headers={[{label:'PATHOGEN'},{label:'COUNTRY'},{label:'CASES',align:'right',num:true},{label:'TREND'},{label:'STATUS'}]}
        rows={[
          ['Mpox clade Ib', 'DR Congo', 8412, <span className="down">↑</span>, <Pill tone="rose">PHEIC</Pill>],
          ['H5N1 (dairy)', 'USA', 412, <span className="down">↑</span>, <Pill tone="amber">WATCH</Pill>],
          ['Dengue', 'Brazil', '6.2M', <span className="up">→</span>, <Pill tone="amber">ENDEMIC</Pill>],
          ['Cholera', 'Sudan', 28400, <span className="down">↑</span>, <Pill tone="rose">EPIDEMIC</Pill>],
          ['Marburg', 'Rwanda', 64, <span className="up">↓</span>, <Pill tone="amber">OUTBREAK</Pill>],
          ['Polio (WPV1)', 'Pakistan', 51, <span className="down">↑</span>, <Pill tone="rose">PHEIC</Pill>],
          ['COVID-19', 'Global', 'wastewater', <span className="down">↑</span>, <Pill tone="cyan">SURV</Pill>],
        ]} />,
    ]
  );

  ALL.OCN = () => makeWrap(
    [
      { label: 'SST GLOBAL', value: '21.42°C', color: 'var(--rose)', sub: 'record' },
      { label: 'ENSO', value: 'La Niña', color: 'var(--cyan)' },
      { label: 'ATLANTIC MDR', value: '+0.84°C', color: 'var(--rose)' },
      { label: 'ACTIVE STORMS', value: '0', sub: 'tropical' },
      { label: 'CORAL DHW max', value: '14', color: 'var(--rose)' },
    ],
    [
      <ListPanel key="a" title="OCEAN BUOYS · SELECTED"
        headers={[{label:'STATION'},{label:'LAT'},{label:'LON'},{label:'SST °C',align:'right',num:true},{label:'WAVE m',align:'right',num:true},{label:'WIND kt',align:'right',num:true}]}
        rows={[
          ['41001 NC', '34.7N', '72.6W', 21.4, 2.4, 14],
          ['41002 SC', '32.4N', '75.4W', 22.1, 2.1, 12],
          ['51000 HI', '23.5N', '154.0W', 26.2, 1.8, 18],
          ['46006 OR', '40.8N', '137.5W', 14.2, 3.2, 22],
          ['62029 UK', '49.2N', '07.9W', 13.4, 4.1, 28],
          ['41044 PR', '21.6N', '58.6W', 27.8, 1.4, 11],
        ]} />,
    ]
  );

  // ============ DEMOG ============
  ALL.POP = () => makeWrap(
    [
      { label: 'WORLD POP', value: '8.18B', color: 'var(--mint)', sub: '+0.88% YoY' },
      { label: 'BIRTHS/SEC', value: '4.3' },
      { label: 'DEATHS/SEC', value: '2.0' },
      { label: 'NET +/SEC', value: '+2.3', color: 'var(--mint)' },
    ],
    [
      <ListPanel key="a" title="POPULATION · TOP 20 COUNTRIES"
        headers={[{label:'COUNTRY'},{label:'POP',align:'right',num:true},{label:'% WORLD',align:'right',num:true},{label:'GROWTH %',align:'right',num:true},{label:'MED AGE',align:'right',num:true}]}
        rows={[
          ['India', '1.450B', 17.7, 0.81, 28],
          ['China', '1.413B', 17.3, -0.10, 39],
          ['United States', '342M', 4.2, 0.50, 39],
          ['Indonesia', '281M', 3.4, 0.74, 30],
          ['Pakistan', '241M', 2.9, 1.91, 22],
          ['Nigeria', '230M', 2.8, 2.10, 18],
          ['Brazil', '217M', 2.7, 0.42, 33],
          ['Bangladesh', '173M', 2.1, 0.99, 27],
          ['Russia', '143M', 1.8, -0.21, 39],
          ['Mexico', '131M', 1.6, 0.91, 30],
        ]} />,
    ]
  );

  ALL.MIG = () => makeWrap(null, [
    <ListPanel key="a" title="INTERNATIONAL MIGRATION · TOP CORRIDORS"
      meta="UN DESA · stocks"
      headers={[{label:'CORRIDOR'},{label:'STOCK',align:'right',num:true},{label:'RECENT FLOW',align:'right',num:true}]}
      rows={[
        ['Mexico → USA', '11.0M', '+184k'],
        ['India → UAE', '3.4M', '+22k'],
        ['Syria → Turkey', '3.5M', '-12k'],
        ['Ukraine → EU', '6.7M', '+18k'],
        ['Philippines → USA', '2.0M', '+8k'],
        ['Venezuela → Colombia', '2.8M', '+4k'],
        ['China → USA', '2.5M', '+12k'],
        ['Bangladesh → Saudi', '2.2M', '+18k'],
      ]} />,
  ]);

  ALL.URB = () => makeWrap(
    [
      { label: 'URBAN %', value: '57.4%', color: 'var(--mint)', sub: 'world' },
      { label: 'MEGACITIES 10M+', value: '34' },
      { label: 'FASTEST GROWTH', value: 'Lagos', sub: '+3.8%/yr' },
      { label: 'HIGHEST DENSITY', value: 'Manila', sub: '46k/km²' },
    ],
    [
      <ListPanel key="a" title="MEGACITIES · LARGEST URBAN AGGLOMERATIONS"
        headers={[{label:'CITY'},{label:'COUNTRY'},{label:'POP',align:'right',num:true},{label:'GROWTH %',align:'right',num:true}]}
        rows={[
          ['Tokyo', 'Japan', '37.4M', -0.20],
          ['Delhi', 'India', '33.8M', 2.41],
          ['Shanghai', 'China', '29.2M', 1.84],
          ['Dhaka', 'Bangladesh', '23.2M', 2.81],
          ['São Paulo', 'Brazil', '22.6M', 0.84],
          ['Cairo', 'Egypt', '22.6M', 1.94],
          ['Mexico City', 'Mexico', '22.2M', 0.41],
          ['Beijing', 'China', '21.8M', 0.81],
          ['Mumbai', 'India', '21.7M', 1.12],
          ['Osaka', 'Japan', '19.0M', -0.31],
          ['Lagos', 'Nigeria', '15.8M', 3.84],
        ]} />,
    ]
  );

  ALL.LBR = () => makeWrap(
    [
      { label: 'GLOBAL UNEMP', value: '5.1%', color: 'var(--mint)' },
      { label: 'US JOBLESS CLAIMS', value: '218k', color: 'var(--mint)' },
      { label: 'EU UNEMP', value: '6.3%', sub: 'EA20' },
      { label: 'YOUTH UNEMP', value: '13.4%', color: 'var(--amber)' },
    ],
    [
      <ListPanel key="a" title="LABOR MARKET · BY COUNTRY"
        headers={[{label:'COUNTRY'},{label:'UNEMP %',align:'right',num:true},{label:'PARTICIPATION %',align:'right',num:true},{label:'WAGE GROWTH Y/Y',align:'right',num:true}]}
        rows={[
          ['United States', 4.1, 62.6, 3.9],
          ['UK', 4.3, 63.2, 5.4],
          ['Germany', 3.5, 62.4, 5.8],
          ['France', 7.4, 56.4, 3.2],
          ['Japan', 2.5, 63.1, 2.1],
          ['Spain', 11.2, 59.4, 4.1],
          ['Italy', 6.2, 51.4, 4.4],
          ['Canada', 6.5, 65.4, 4.2],
        ].map(r => [
          r[0], r[1].toFixed(1), r[2].toFixed(1), <span className="up">+{r[3].toFixed(1)}%</span>,
        ])} />,
    ]
  );

  ALL.HLT = () => makeWrap(
    [
      { label: 'LIFE EXP WORLD', value: '73.4 yr' },
      { label: 'INFANT MORT', value: '27/1k', color: 'var(--mint)', sub: '↓ trend' },
      { label: 'VACC COVERAGE', value: '83%', sub: 'DTP3' },
      { label: 'HC SPEND %GDP US', value: '17.4%' },
    ],
    [
      <ListPanel key="a" title="HEALTH INDICATORS · WHO + WORLD BANK"
        headers={[{label:'INDICATOR'},{label:'GLOBAL'},{label:'OECD'},{label:'SSA'},{label:'TREND'}]}
        rows={[
          ['Life expectancy', '73.4', '81.2', '62.4', <span className="up">↑</span>],
          ['Maternal mortality (per 100k)', '223', '12', '545', <span className="up">↓</span>],
          ['Tuberculosis incidence', '127', '8', '212', <span className="up">↓</span>],
          ['DTP3 coverage %', '83', '95', '74', <span className="up">↑</span>],
          ['Physicians per 1k', '1.7', '3.6', '0.3', <span className="up">↑</span>],
          ['Out-of-pocket %', '18%', '13%', '34%', <span className="mut">→</span>],
        ]} />,
    ]
  );

  ALL.EDU = () => makeWrap(
    [
      { label: 'GLOBAL LITERACY', value: '87%', color: 'var(--mint)' },
      { label: 'TERTIARY ENROLL', value: '42%', sub: 'gross' },
      { label: 'OUT-OF-SCHOOL', value: '244M', color: 'var(--amber)' },
      { label: 'STEM GRADUATES', value: 'CN > IN > US' },
    ],
    [
      <ListPanel key="a" title="EDUCATION OUTCOMES · PISA / WORLD BANK"
        headers={[{label:'COUNTRY'},{label:'PISA SCI',align:'right',num:true},{label:'PISA MATH',align:'right',num:true},{label:'TERTIARY %',align:'right',num:true},{label:'SPEND %GDP',align:'right',num:true}]}
        rows={[
          ['Singapore', 561, 575, 84, 2.8],
          ['Japan', 547, 536, 65, 3.4],
          ['Estonia', 526, 510, 72, 5.4],
          ['Finland', 511, 484, 76, 5.6],
          ['Canada', 515, 497, 78, 5.1],
          ['Germany', 492, 475, 65, 4.6],
          ['USA', 499, 465, 88, 6.1],
          ['UK', 500, 489, 68, 5.3],
          ['France', 487, 474, 65, 5.4],
        ]} />,
    ]
  );

  // ============ TECH ============
  ALL.AI = () => makeWrap(
    [
      { label: 'GLOBAL AI MKT', value: '$305B', color: 'var(--mint)', sub: '+38% YoY' },
      { label: 'TRAINING COMPUTE', value: '+150% YoY', color: 'var(--mint)' },
      { label: 'FRONTIER FLOPS', value: '~2e26', sub: 'top model' },
      { label: 'CHIP DEMAND', value: '↑↑', color: 'var(--mint)' },
    ],
    [
      <ListPanel key="a" title="MODEL RELEASES & BENCHMARKS · 90 DAYS"
        headers={[{label:'MODEL'},{label:'LAB'},{label:'RELEASE'},{label:'MMLU',align:'right',num:true},{label:'GPQA',align:'right',num:true},{label:'HUMANEVAL',align:'right',num:true}]}
        rows={[
          ['Frontier-A', 'Lab Alpha', 'Oct', 92.1, 71.4, 92.4],
          ['Open-Pro', 'Lab Bravo', 'Sep', 84.2, 62.1, 84.1],
          ['Vision-L', 'Lab Charlie', 'Oct', 88.4, 65.2, 86.4],
          ['Code-Forge', 'Lab Delta', 'Nov', 81.4, 58.2, 94.8],
          ['Open-7B', 'Community', 'Aug', 72.4, 38.2, 68.4],
        ]} />,
    ]
  );

  ALL.CLD = () => makeWrap(
    [
      { label: 'GLOBAL CLOUD', value: '$679B', color: 'var(--mint)', sub: '2024' },
      { label: 'AWS YoY', value: '+19%', color: 'var(--mint)' },
      { label: 'AZURE YoY', value: '+33%', color: 'var(--mint)' },
      { label: 'GCP YoY', value: '+35%', color: 'var(--mint)' },
    ],
    [
      <ListPanel key="a" title="CLOUD PROVIDER STATUS · INFRASTRUCTURE"
        headers={[{label:'PROVIDER'},{label:'REGIONS',align:'right',num:true},{label:'INCIDENTS 7D',align:'right',num:true},{label:'UPTIME 30D',align:'right',num:true},{label:'STATUS'}]}
        rows={[
          ['AWS', 33, 4, 99.96, <Pill tone="mint">NORMAL</Pill>],
          ['Azure', 64, 6, 99.92, <Pill tone="amber">DEGRADED</Pill>],
          ['GCP', 40, 3, 99.97, <Pill tone="mint">NORMAL</Pill>],
          ['Oracle', 50, 2, 99.95, <Pill tone="mint">NORMAL</Pill>],
          ['Alibaba', 31, 5, 99.91, <Pill tone="mint">NORMAL</Pill>],
          ['Tencent', 26, 4, 99.93, <Pill tone="mint">NORMAL</Pill>],
          ['Cloudflare', '275 PoP', 1, 99.99, <Pill tone="mint">NORMAL</Pill>],
        ]} />,
    ]
  );

  ALL.SEM = () => makeWrap(
    [
      { label: 'SOX INDEX', value: '4,841', color: 'var(--mint)', sub: '+1.42%' },
      { label: 'NVDA', value: '$141.21', color: 'var(--mint)', sub: '+2.18%' },
      { label: 'DRAM SPOT', value: '$1.42/Gb', color: 'var(--rose)' },
      { label: 'WAFER STARTS', value: '~3.5M/mo', sub: 'global' },
      { label: 'FAB CAPEX 2024', value: '$185B', sub: 'industry' },
    ],
    [
      <ListPanel key="a" title="LEADING-EDGE FAB BUILD-OUT"
        headers={[{label:'COMPANY'},{label:'NODE'},{label:'SITE'},{label:'CAPEX'},{label:'STATUS'}]}
        rows={[
          ['TSMC', 'N2', 'Hsinchu Fab 20', '$32B', <Pill tone="mint">RAMP 2025</Pill>],
          ['TSMC', 'N4', 'Phoenix AZ', '$40B', <Pill tone="mint">PROD</Pill>],
          ['Samsung', 'GAA 2nm', 'Pyeongtaek', '$22B', <Pill tone="cyan">QUAL</Pill>],
          ['Samsung', '4nm', 'Taylor TX', '$17B', <Pill tone="amber">DELAYED</Pill>],
          ['Intel', 'Intel 18A', 'Arizona Fab 52', '$25B', <Pill tone="cyan">QUAL</Pill>],
          ['Intel', 'Intel 18A', 'Germany', '$33B', <Pill tone="amber">PAUSED</Pill>],
          ['SMIC', '7nm equiv', 'Shanghai', '~$8B', <Pill tone="mint">PROD</Pill>],
        ]} />,
    ]
  );

  ALL.ROB = () => makeWrap(null, [
    <ListPanel key="a" title="ROBOTICS & AUTOMATION · INDUSTRIAL"
      headers={[{label:'COUNTRY'},{label:'ROBOT DENSITY',align:'right',num:true},{label:'NEW INSTALL Y',align:'right',num:true},{label:'MFG SHARE'}]}
      rows={[
        ['South Korea', 1012, 32400, 'Heavy auto'],
        ['Singapore', 770, 8200, 'Electronics'],
        ['China', 470, 290000, 'Auto · electronics'],
        ['Germany', 415, 28400, 'Auto'],
        ['Japan', 397, 52000, 'Electronics · auto'],
        ['USA', 295, 44000, 'Auto · logistics'],
        ['Taiwan', 280, 9800, 'Electronics'],
      ].map(r => [r[0], fmt(r[1], 0), fmt(r[2], 0), r[3]])} />,
  ]);

  ALL.QNT = () => makeWrap(null, [
    <ListPanel key="a" title="QUANTUM COMPUTING · PROCESSORS"
      headers={[{label:'PROVIDER'},{label:'PROCESSOR'},{label:'QUBITS',align:'right',num:true},{label:'GATE FID %',align:'right',num:true},{label:'TYPE'}]}
      rows={[
        ['IBM', 'Heron R2', 156, 99.7, 'Superconducting'],
        ['IBM', 'Condor', 1121, 99.0, 'Superconducting'],
        ['Google', 'Willow', 105, 99.85, 'Superconducting'],
        ['Quantinuum', 'H2-1', 56, 99.8, 'Trapped-ion'],
        ['IonQ', 'Forte', 35, 99.6, 'Trapped-ion'],
        ['Rigetti', 'Ankaa-3', 84, 98.5, 'Superconducting'],
        ['Atom Computing', 'Phoenix', 1180, 99.4, 'Neutral atom'],
        ['PsiQuantum', '-', '~1M planned', '-', 'Photonic'],
      ]} />,
  ]);

  ALL.PAT = () => makeWrap(
    [
      { label: 'WORLD PATENTS Y', value: '~3.5M' },
      { label: 'TOP FILER', value: 'CN', sub: '~50%' },
      { label: 'AI-RELATED', value: '+38% YoY', color: 'var(--mint)' },
    ],
    [
      <ListPanel key="a" title="PATENT FILINGS · BY OFFICE"
        headers={[{label:'OFFICE'},{label:'FILINGS Y',align:'right',num:true},{label:'GROWTH %',align:'right',num:true}]}
        rows={[
          ['CN (CNIPA)', '1,580,000', 5.4],
          ['US (USPTO)', '595,000', 2.1],
          ['JP (JPO)', '290,000', -1.4],
          ['KR (KIPO)', '237,000', 1.8],
          ['EU (EPO)', '199,000', 2.9],
          ['IN', '92,000', 13.2],
          ['DE', '58,000', 0.4],
        ].map(r => [r[0], r[1],
          <span className={r[2] >= 0 ? 'up' : 'down'}>{r[2] >= 0 ? '+' : ''}{r[2].toFixed(1)}%</span>])} />,
    ]
  );

  // ============ SUPPLY ============
  ALL.PRT = () => makeWrap(
    [
      { label: 'GLOBAL PORTS', value: '~5,000' },
      { label: 'TEU 2024', value: '~860M' },
      { label: 'TOP', value: 'Shanghai', sub: '~50M TEU' },
      { label: 'CONGESTION', value: 'MODERATE', color: 'var(--amber)' },
    ],
    [
      <ListPanel key="a" title="MAJOR CONTAINER PORTS · CURRENT STATE"
        headers={[{label:'PORT'},{label:'TEU/Y',align:'right',num:true},{label:'WAIT h',align:'right',num:true},{label:'BERTHED',align:'right',num:true},{label:'STATUS'}]}
        rows={[
          ['Shanghai',     '49.2M', 8,  64, <Pill tone="amber">BUSY</Pill>],
          ['Singapore',    '37.3M', 4,  88, <Pill tone="mint">NORMAL</Pill>],
          ['Ningbo-Z.',    '35.3M', 6,  52, <Pill tone="mint">NORMAL</Pill>],
          ['Shenzhen',     '30.0M', 7,  42, <Pill tone="amber">BUSY</Pill>],
          ['Guangzhou',    '25.4M', 5,  38, <Pill tone="mint">NORMAL</Pill>],
          ['Busan',        '22.8M', 3,  46, <Pill tone="mint">NORMAL</Pill>],
          ['Rotterdam',    '14.5M', 4,  34, <Pill tone="mint">NORMAL</Pill>],
          ['LA / LB',      '17.0M', 12, 28, <Pill tone="amber">BUSY</Pill>],
          ['Antwerp-B.',   '13.5M', 5,  41, <Pill tone="mint">NORMAL</Pill>],
          ['Hamburg',      '7.8M',  6,  18, <Pill tone="mint">NORMAL</Pill>],
        ]} />,
    ]
  );

  ALL.TRD = () => makeWrap(
    [
      { label: 'BDI', value: '1,524', color: 'var(--rose)', sub: '-2.4%' },
      { label: 'WCI', value: '$3,182', color: 'var(--mint)', sub: '+8.1%' },
      { label: 'AIR CARGO RATE', value: '$2.41/kg' },
      { label: 'GLOBAL TRADE', value: '$32T', sub: 'goods + svc' },
    ],
    [
      <ListPanel key="a" title="FREIGHT INDICES & ROUTES"
        headers={[{label:'INDEX / ROUTE'},{label:'LEVEL',align:'right',num:true},{label:'Δ%',align:'right',num:true},{label:'TREND'}]}
        rows={[
          ['Baltic Dry Index', '1,524', -2.4],
          ['Baltic Capesize', '2,310', -3.8],
          ['Baltic Panamax', '1,420', -1.1],
          ['BDTI Tanker', '932', -0.4],
          ['Drewry WCI', '3,182', 8.1],
          ['Shanghai-LA SCFI', '$4,210', 2.4],
          ['Shanghai-Rotterdam', '$3,820', 4.1],
          ['Shanghai-NY', '$5,610', 6.4],
          ['Air Cargo TAC', '$2.41/kg', 1.8],
        ].map((r, i) => [r[0], r[1],
          <span className={r[2] >= 0 ? 'up' : 'down'}>{r[2] >= 0 ? '+' : ''}{r[2].toFixed(1)}%</span>,
          <Spark seed={i+200} up={r[2] >= 0} />])} />,
    ]
  );

  ALL.MFG = () => makeWrap(
    [
      { label: 'GLOBAL PMI', value: '50.4', sub: 'expanding' },
      { label: 'US ISM', value: '48.4', color: 'var(--rose)' },
      { label: 'EU PMI', value: '45.2', color: 'var(--rose)' },
      { label: 'CN CAIXIN', value: '50.3', color: 'var(--mint)' },
      { label: 'IP YoY', value: '+0.4%' },
    ],
    [
      <ListPanel key="a" title="MANUFACTURING PMI · GLOBAL"
        headers={[{label:'COUNTRY'},{label:'PMI',align:'right',num:true},{label:'Δ',align:'right',num:true},{label:'STATUS'}]}
        rows={[
          ['United States', 48.4, -0.7, <Pill tone="rose">CONTR</Pill>],
          ['Eurozone', 45.2, -0.8, <Pill tone="rose">CONTR</Pill>],
          ['Germany', 43.0, 0.0, <Pill tone="rose">CONTR</Pill>],
          ['UK', 49.9, -1.4, <Pill tone="amber">FLAT</Pill>],
          ['Japan', 49.2, -0.5, <Pill tone="amber">FLAT</Pill>],
          ['China Caixin', 50.3, 0.4, <Pill tone="mint">EXPAND</Pill>],
          ['India', 57.5, -0.8, <Pill tone="mint">EXPAND</Pill>],
          ['Mexico', 49.1, -0.4, <Pill tone="amber">FLAT</Pill>],
          ['Brazil', 52.9, 0.2, <Pill tone="mint">EXPAND</Pill>],
        ]} />,
    ]
  );

  ALL.INV = () => makeWrap(null, [
    <ListPanel key="a" title="INVENTORIES · LATEST RELEASES"
      headers={[{label:'CATEGORY'},{label:'COUNTRY'},{label:'PERIOD'},{label:'CHANGE'},{label:'NOTE'}]}
      rows={[
        ['Crude oil', 'US (EIA)', 'Wk 46', '+2.1 MB', 'Above forecast'],
        ['Gasoline', 'US (EIA)', 'Wk 46', '+0.4 MB', 'In line'],
        ['Distillate', 'US (EIA)', 'Wk 46', '-0.1 MB', 'Below forecast'],
        ['Nat gas', 'US (EIA)', 'Wk 46', '+18 Bcf', 'Above forecast'],
        ['Business inv', 'US', 'Sep', '+0.1%', 'Slowing'],
        ['Retail inv', 'US', 'Sep', '+0.2%', 'Slowing'],
        ['Wholesale inv', 'US', 'Sep', '+0.2%', 'Mixed'],
      ]} />,
  ]);

  // ============ LIVE (additional placeholders for the few not reused) ============
  ALL.TRF = () => makeWrap(
    [
      { label: 'MAJOR HUBS', value: '12', sub: 'monitored' },
      { label: 'AVG SPEED', value: '38 km/h' },
      { label: 'INCIDENTS', value: '24' },
      { label: 'WORST', value: 'Lagos', color: 'var(--rose)' },
    ],
    [
      <ListPanel key="a" title="URBAN ROAD TRAFFIC · CURRENT"
        headers={[{label:'CITY'},{label:'CONGESTION %',align:'right',num:true},{label:'AVG SPD km/h',align:'right',num:true},{label:'INCIDENTS',align:'right',num:true},{label:'TREND'}]}
        rows={[
          ['Mexico City', 84, 22, 8, <span className="down">↑</span>],
          ['Lagos', 91, 14, 12, <span className="down">↑</span>],
          ['Istanbul', 76, 28, 4, <span className="mut">→</span>],
          ['Manila', 74, 21, 6, <span className="down">↑</span>],
          ['Bangkok', 71, 26, 5, <span className="mut">→</span>],
          ['Bogotá', 68, 24, 7, <span className="up">↓</span>],
          ['New York', 51, 32, 11, <span className="mut">→</span>],
          ['London', 49, 30, 6, <span className="up">↓</span>],
          ['Los Angeles', 47, 38, 9, <span className="mut">→</span>],
          ['Tokyo', 38, 42, 3, <span className="up">↓</span>],
        ]} />,
    ]
  );

  // Public webcam list — mirrors bloomberg/feeds/cameras.py STATIC_CAMERAS
  const CAMERAS = [
    { id:'wsdot_9701', name:'I-5 NB at Seattle (S Horton St)',     city:'Seattle, WA',         category:'traffic',  url:'https://images.wsdot.wa.gov/nw/009vc09701.jpg' },
    { id:'wsdot_8411', name:'I-5 at Tacoma (S 56th St)',            city:'Tacoma, WA',          category:'traffic',  url:'https://images.wsdot.wa.gov/sw/005vc08411.jpg' },
    { id:'wsdot_8103', name:'SR-99 Tunnel North Portal',            city:'Seattle, WA',         category:'traffic',  url:'https://images.wsdot.wa.gov/nw/099vc08103.jpg' },
    { id:'wsdot_9339', name:'I-90 at Mercer Island',                city:'Mercer Island, WA',   category:'traffic',  url:'https://images.wsdot.wa.gov/ms/090vc09339.jpg' },
    { id:'wsdot_4077', name:'US-2 at Stevens Pass Summit',          city:'Stevens Pass, WA',    category:'mountain', url:'https://images.wsdot.wa.gov/nc/002vc04077.jpg' },
    { id:'wsdot_5175', name:'US-2 at Snoqualmie Pass',              city:'Snoqualmie Pass, WA', category:'mountain', url:'https://images.wsdot.wa.gov/ms/090vc05175.jpg' },
    { id:'noaa_hilo',   name:'NOAA — Hilo, Hawaii',                  city:'Hilo, HI',            category:'weather',  url:'https://www.weather.gov/images/hfo/webcam/hilo_latest.jpg' },
    { id:'noaa_juneau', name:'NOAA — Juneau, Alaska',                city:'Juneau, AK',          category:'weather',  url:'https://www.weather.gov/images/pajk/webcam/juneau_latest.jpg' },
    { id:'usgs_kil1',   name:'USGS — Kilauea Summit (HVO)',          city:'Hawaii Volcanoes NP', category:'science',  url:'https://volcanoes.usgs.gov/vsc/captures/kilauea/2011HVO_overview.jpg' },
    { id:'pdx_appr',    name:'PDX Airport Approach (Troutdale)',    city:'Portland, OR',        category:'aviation', url:'https://weathercams.faa.gov/camera/TROUTDALE/latest.jpg' },
    { id:'sea_appr',    name:'SEA Airport Approach (Renton)',       city:'Seattle, WA',         category:'aviation', url:'https://weathercams.faa.gov/camera/RENTON/latest.jpg' },
    { id:'anc_appr',    name:'ANC Airport Approach',                city:'Anchorage, AK',       category:'aviation', url:'https://weathercams.faa.gov/camera/ANCHORAGE_INT/latest.jpg' },
    { id:'den_appr',    name:'DEN Airport Approach (Watkins)',      city:'Denver, CO',          category:'aviation', url:'https://weathercams.faa.gov/camera/WATKINS/latest.jpg' },
    { id:'cotrip_i70',  name:'I-70 at Vail Pass Summit',            city:'Vail Pass, CO',       category:'traffic',  url:'https://cotrip.org/cameras/I-070D/I-070D-262.00BVAI.jpg' },
    { id:'cotrip_i70e', name:'I-70 Eisenhower Tunnel East Portal',  city:'Dillon, CO',          category:'traffic',  url:'https://cotrip.org/cameras/I-070D/I-070D-216.40ETUN.jpg' },
  ];

  function CameraTile({ cam, bust }) {
    // Try strategies in order: weserv proxy → corsproxy → direct → stable picsum fallback
    const [attempt, setAttempt] = useState(0);
    const [state, setState] = useState('loading');

    const stripped = cam.url.replace(/^https?:\/\//, '');
    const strategies = [
      { key: 'weserv',  url: 'https://images.weserv.nl/?url=' + encodeURIComponent(stripped) + '&n=-1' },
      { key: 'corspx',  url: 'https://corsproxy.io/?' + encodeURIComponent(cam.url) },
      { key: 'direct',  url: cam.url },
    ];
    const curr = strategies[Math.min(attempt, strategies.length - 1)];
    const src = curr.url + (curr.url.includes('?') ? '&' : '?') + 't=' + bust;

    // Reset on new bust (refresh)
    React.useEffect(() => {
      setAttempt(0); setState('loading');
    }, [bust]);

    // Timeout per attempt — bump to next strategy if image stalls
    React.useEffect(() => {
      setState('loading');
      const id = setTimeout(() => {
        setState(s => {
          if (s !== 'loading') return s;
          if (attempt < strategies.length - 1) { setAttempt(a => a + 1); return 'loading'; }
          return 'error';
        });
      }, 6000);
      return () => clearTimeout(id);
    }, [src]);

    const onError = () => {
      if (attempt < strategies.length - 1) setAttempt(a => a + 1);
      else setState('error');
    };
    const onLoad = () => setState('ok');
    return (
      <div style={{ border: '1px solid var(--border-2)', background: 'var(--bg-2)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
        <div style={{ padding: '4px 8px', background: 'var(--surface-2)', fontSize: 10, color: 'var(--cyan)',
          display: 'flex', justifyContent: 'space-between', gap: 8, borderBottom: '1px solid var(--border)' }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cam.name}</span>
          <span className="mut" style={{ flexShrink: 0 }}>{cam.city}</span>
        </div>
        <div style={{ position: 'relative', flex: 1, minHeight: 0, background:
          'repeating-linear-gradient(45deg, var(--surface) 0 6px, var(--surface-2) 6px 12px)' }}>
          <img
            src={src}
            alt={cam.name}
            referrerPolicy="no-referrer"
            loading="lazy"
            onLoad={onLoad}
            onError={onError}
            style={{
              width: '100%', height: '100%', objectFit: 'cover', display: 'block',
              opacity: state === 'ok' ? 1 : 0, transition: 'opacity .2s',
            }} />
          {state !== 'ok' && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
              justifyContent: 'center', flexDirection: 'column', gap: 4,
              color: state === 'error' ? 'var(--rose)' : 'var(--muted)' }}>
              <span style={{ fontSize: 22 }}>{state === 'error' ? '✕' : '○'}</span>
              <span style={{ fontSize: 10, letterSpacing: '.08em' }}>
                {state === 'error' ? 'FEED UNAVAILABLE' : 'LOADING…'}
              </span>
              {state === 'error' && (
                <a href={cam.url} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: 9, color: 'var(--cyan)' }}>open source ↗</a>
              )}
            </div>
          )}
          <div className="blink" style={{ position: 'absolute', top: 6, right: 8,
            color: state === 'ok' ? 'var(--rose)' : 'var(--dim)', fontSize: 9, letterSpacing: '.1em',
            background: 'rgba(0,0,0,.55)', padding: '1px 5px', borderRadius: 2 }}>● LIVE</div>
          <div style={{ position: 'absolute', bottom: 6, left: 8,
            background: 'rgba(0,0,0,.6)', color: 'var(--cyan)', fontSize: 9, letterSpacing: '.1em',
            padding: '1px 5px' }}>{cam.category.toUpperCase()}</div>
        </div>
      </div>
    );
  }

  function CamPanel({ defaultCat }) {
    const cats = ['', 'traffic', 'aviation', 'mountain', 'weather', 'science'];
    const [filter, setFilter] = useState(defaultCat || '');
    const [bust, setBust] = useState(Date.now());
    const filtered = filter ? CAMERAS.filter(c => c.category === filter) : CAMERAS;
    // Auto-refresh every 60s
    React.useEffect(() => {
      const id = setInterval(() => setBust(Date.now()), 60000);
      return () => clearInterval(id);
    }, []);
    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Head title={defaultCat === 'traffic' ? 'TRAFFIC CAMERAS · LIVE' : 'PUBLIC WEBCAMS · LIVE'}
            meta={`${filtered.length} of ${CAMERAS.length} · WSDOT · NOAA · FAA · USGS · CoTrip`}
            right={
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                {cats.map(c => (
                  <button key={c || 'all'}
                    className={`btn ${filter === c ? 'on' : ''}`}
                    onClick={() => setFilter(c)}
                    style={{ textTransform: 'uppercase', fontSize: 10 }}>
                    {c || 'ALL'}
                  </button>
                ))}
                <button className="btn" onClick={() => setBust(Date.now())}
                  style={{ marginLeft: 6 }}>↻ REFRESH</button>
                <span className="pill pill-mint blink" style={{ marginLeft: 4 }}>● LIVE 60s</span>
              </div>
            } />
          <div style={{ flex: 1, padding: 8, overflow: 'auto',
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gridAutoRows: '200px', gap: 8 }}>
            {filtered.map(cam => <CameraTile key={cam.id} cam={cam} bust={bust} />)}
          </div>
        </div>
      </div>
    );
  }

  ALL.CAM = () => <CamPanel defaultCat="" />;
  ALL.TRF = () => <CamPanel defaultCat="traffic" />;

  // SHP/AIR placeholders (supply view — different from live VES/ACR maps)
  ALL.SHP = ({ snap }) => makeWrap(
    [
      { label: 'WORLD FLEET', value: '105,493', sub: 'IMO' },
      { label: 'CONT SHIPS', value: '5,650', sub: '>1k TEU' },
      { label: 'CRUDE TANKERS', value: '2,420' },
      { label: 'NEWBUILDS Q', value: '184', color: 'var(--mint)' },
    ],
    [
      <ListPanel key="a" title="VESSEL FLEET COMPOSITION (top types)"
        headers={[{label:'TYPE'},{label:'COUNT',align:'right',num:true},{label:'AVG AGE',align:'right',num:true},{label:'CAPACITY'}]}
        rows={[
          ['Bulk carriers', '13,420', 11.2, '950 MDWT'],
          ['Container', '5,650', 12.1, '29M TEU'],
          ['Tankers (crude)', '2,420', 11.8, '420 MDWT'],
          ['Tankers (product)', '3,420', 13.4, '180 MDWT'],
          ['LNG', '720', 9.4, '110M cbm'],
          ['LPG', '1,640', 12.8, '38M cbm'],
          ['Vehicle carriers', '770', 13.1, '4.4M CEU'],
          ['Reefer', '610', 18.4, '—'],
          ['General cargo', '14,840', 24.8, '—'],
          ['Passenger / Cruise', '5,860', 22.4, '—'],
        ]} />,
    ]
  );

  ALL.AIR = () => makeWrap(
    [
      { label: 'WORLD FLEET', value: '~28,500', sub: 'passenger jets' },
      { label: 'IN SERVICE', value: '~24,800' },
      { label: 'PARKED', value: '~3,700' },
      { label: 'BACKLOG', value: '15,200', sub: 'firm orders' },
    ],
    [
      <ListPanel key="a" title="COMMERCIAL FLEET · TOP TYPES"
        headers={[{label:'TYPE'},{label:'OEM'},{label:'IN SVC',align:'right',num:true},{label:'BACKLOG',align:'right',num:true}]}
        rows={[
          ['A320 family', 'Airbus', '8,840', '5,120'],
          ['737 NG', 'Boeing', '5,420', '0'],
          ['737 MAX', 'Boeing', '1,580', '4,210'],
          ['A350', 'Airbus', '610', '510'],
          ['777', 'Boeing', '1,310', '410'],
          ['787', 'Boeing', '1,140', '780'],
          ['A330', 'Airbus', '1,440', '320'],
          ['A220', 'Airbus', '410', '530'],
          ['E2 family', 'Embraer', '120', '210'],
        ]} />,
    ]
  );

  // ============ NET — Internet Outages ============
  ALL.NET = () => {
    const r = rng(2024);
    const alertLevels = ['warning','warning','critical','critical','normal'];
    const dsList = ['bgp','active-probing','telescope','google-pld'];
    const places = [
      ['Iran','IR'],['Russia','RU'],['Sudan','SD'],['Myanmar','MM'],['Pakistan','PK'],
      ['Cuba','CU'],['Mali','ML'],['Ethiopia','ET'],['Yemen','YE'],['Venezuela','VE'],
      ['Syria','SY'],['Libya','LY'],['Iraq','IQ'],['Bangladesh','BD'],['Mauritania','MR'],
    ];
    const alerts = Array.from({ length: 14 }, (_, i) => {
      const [name, code] = pick(places, r);
      const level = pick(alertLevels, r);
      const score = level === 'critical' ? round(between(85, 99, r), 1)
                  : level === 'warning'  ? round(between(50, 84, r), 1)
                  : round(between(10, 40, r), 1);
      const hoursAgo = Math.floor(between(1, 23, r));
      return {
        name, code, level, score, source: pick(dsList, r),
        time: `${hoursAgo}h ago`,
        type: pick(['country','region','asn'], r),
      };
    }).sort((a, b) => b.score - a.score);

    const countries = Array.from({ length: 18 }, (_, i) => {
      const [name, code] = pick(places, r);
      const score = round(between(0.4, 0.99, r), 2);
      const normal = round(score + between(-0.05, 0.05, r), 2);
      return {
        name, code, score, normal,
        connectivity: score >= 0.9 ? 'Normal' : score >= 0.7 ? 'Reduced' : 'Degraded',
      };
    });

    const bgp = Array.from({ length: 12 }, (_, i) => ({
      prefix: `${Math.floor(between(1, 223, r))}.${Math.floor(between(0, 255, r))}.${Math.floor(between(0, 255, r))}.0/${pick([16,20,22,24], r)}`,
      type: pick(['announcement','withdrawal','origin-change'], r),
      origin_asn: 'AS' + Math.floor(between(1000, 64500, r)),
      peer: 'AS' + Math.floor(between(1000, 64500, r)),
      mins: Math.floor(between(1, 120, r)) + 'm',
    }));

    const critical = alerts.filter(a => a.level === 'critical').length;
    const degraded = countries.filter(c => c.connectivity !== 'Normal').length;

    return makeWrap(
      [
        { label: 'CRITICAL ALERTS', value: critical, color: 'var(--rose)', sub: 'IODA 24h' },
        { label: 'WARNING', value: alerts.filter(a => a.level === 'warning').length, color: 'var(--amber)' },
        { label: 'COUNTRIES DEGRADED', value: degraded, color: 'var(--amber)', sub: 'of ' + countries.length },
        { label: 'BGP EVENTS 2H', value: bgp.length, sub: 'RIPE NCC' },
        { label: 'WORST', value: alerts[0]?.name || '—', sub: 'score ' + (alerts[0]?.score || 0) },
      ],
      [
        <ListPanel key="a" title="IODA OUTAGE ALERTS · LAST 24H"
          meta="api.ioda.caida.org · BGP + active-probing + telescope"
          headers={[{label:'AGO'},{label:'LEVEL'},{label:'ENTITY'},{label:'TYPE'},
            {label:'SOURCE'},{label:'SCORE',align:'right',num:true}]}
          rows={alerts.map(a => [
            <span className="mut">{a.time}</span>,
            <Pill tone={a.level === 'critical' ? 'rose' : a.level === 'warning' ? 'amber' : 'mint'}>{a.level.toUpperCase()}</Pill>,
            <><span className="lbl">{a.name}</span> <span className="mut">{a.code}</span></>,
            <span className="mut">{a.type}</span>,
            <span className="mut">{a.source}</span>,
            <span className={a.score >= 80 ? 'down' : a.score >= 50 ? 'warn' : ''}>{a.score.toFixed(1)}</span>,
          ])} />,
        <ListPanel key="b" title="COUNTRY-LEVEL CONNECTIVITY"
          meta="signals/raw/country · last 1h"
          headers={[{label:'COUNTRY'},{label:'SCORE',align:'right',num:true},
            {label:'NORMAL',align:'right',num:true},{label:'Δ',align:'right',num:true},{label:'STATUS'}]}
          rows={countries.map(c => {
            const delta = round(c.score - c.normal, 2);
            return [
              <><span className="lbl">{c.name}</span> <span className="mut">{c.code}</span></>,
              <span className={c.score < 0.7 ? 'down' : c.score < 0.9 ? 'warn' : 'up'}>{c.score.toFixed(2)}</span>,
              <span className="mut">{c.normal.toFixed(2)}</span>,
              <span className={delta >= 0 ? 'up' : 'down'}>{delta >= 0 ? '+' : ''}{delta.toFixed(2)}</span>,
              <Pill tone={c.connectivity === 'Degraded' ? 'rose' : c.connectivity === 'Reduced' ? 'amber' : 'mint'}>{c.connectivity}</Pill>,
            ];
          })} />,
      ]
    );
  };

  window.DeltaPlaceholders = ALL;
})();
