// agora-shell.jsx — top-level app, header, tabs, ticker, function-bar, status bar
(function () {
  const { useEffect, useMemo, useRef, useState, useCallback } = React;
  const { snapshot, tickAircraft, tickShips, nudgeQuotes, nudgeCrypto, genSpace, rng, fmt, fmtInt } = window.AgoraData;
  const P = window.AgoraPanels;

  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "theme": "paper",
    "density": "regular",
    "animations": true,
    "mapLabels": true
  }/*EDITMODE-END*/;

  const { CATEGORIES, TAB_NAMES, TAB_TO_CAT } = window.AgoraCats;
  const Pl = window.AgoraPlaceholders;

  // Map a tab code to a "real" panel (existing rich panels reused under new codes)
  function renderTab(code, ctx) {
    const { snap, sel, setSelFor, setSel, setTab } = ctx;
    switch (code) {
      // Reused rich panels
      case 'MKT':  return <P.MarketsPanel snap={snap} />;
      case 'WLD':  return <P.WorldPanel snap={snap} sel={sel.world} setSel={(v) => setSel(s => ({ ...s, world: v }))} />;
      case 'ACR':  return <P.AircraftPanel snap={snap} sel={sel.aircraft} setSel={setSelFor('aircraft')} />;
      case 'VES':  return <P.ShipsPanel snap={snap} sel={sel.ships} setSel={setSelFor('ships')} />;
      case 'SAT':
      case 'ISS':  return <P.SpacePanel snap={snap} />;
      case 'WEA':  return <P.WeatherPanel snap={snap} sel={sel.weather} setSel={setSelFor('weather')} />;
      case 'CLM':  return <P.WeatherPanel snap={snap} sel={sel.weather} setSel={setSelFor('weather')} />;
      case 'EAR':  return <P.QuakesPanel snap={snap} sel={sel.quake} setSel={setSelFor('quake')} />;
      case 'NEWS': return <P.NewsPanel snap={snap} />;
      case 'PKG':  return <P.ParkingPanel snap={snap} sel={sel.parking} setSel={setSelFor('parking')} />;
      case 'CMD':  return <P.CommandPanel snap={snap} onJump={(c) => setTab(c)} />;
      default: {
        const Stub = Pl[code];
        if (Stub) return <Stub snap={snap} />;
        return <NotImplemented code={code} name={TAB_NAMES[code] || code} />;
      }
    }
  }

  function NotImplemented({ code, name }) {
    return (
      <div style={{ padding: 6, height: '100%' }}>
        <div className="panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <div className="panel-head"><span>◆ {code} · {name.toUpperCase()}</span></div>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column', gap: 10, color: 'var(--muted)' }}>
            <div style={{ fontSize: 28, color: 'var(--cyan)' }}>◌</div>
            <div style={{ fontSize: 12, letterSpacing: '.1em' }}>FEED PENDING</div>
            <div className="dim" style={{ fontSize: 10 }}>{code} not yet wired to a data source</div>
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
    const [tab, setTab] = useState('MKT');
    const cat = TAB_TO_CAT[tab] || 'fin';
    const setCat = (newCat) => {
      const c = CATEGORIES.find(x => x.code === newCat);
      if (c) setTab(c.tabs[0]);
    };
    const [snap, setSnap] = useState(() => snapshot(7));
    const [sel, setSel] = useState({});
    const [cmd, setCmd] = useState('');
    const [now, setNow] = useState(new Date());
    const [wsState, setWsState] = useState('connected'); // 'connected' | 'connecting' | 'down'
    const tickRand = useRef(rng(Date.now() & 0xffffff));
    const cmdRef = useRef(null);

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

    // Live tick: nudge quotes every 2s, planes/ships every 3s
    useEffect(() => {
      if (!t.animations) return;
      const id = setInterval(() => {
        setSnap(s => ({
          ...s,
          indices: nudgeQuotes(s.indices, tickRand.current),
          tech:    nudgeQuotes(s.tech, tickRand.current),
          macro:   nudgeQuotes(s.macro, tickRand.current, 0.0008),
          crypto:  nudgeCrypto(s.crypto, tickRand.current),
        }));
      }, 2000);
      return () => clearInterval(id);
    }, [t.animations]);

    useEffect(() => {
      if (!t.animations) return;
      const id = setInterval(() => {
        setSnap(s => ({
          ...s,
          aircraft: tickAircraft(s.aircraft, 3),
          ships:    tickShips(s.ships, 3),
          space:    genSpace(tickRand.current, Date.now()),
        }));
      }, 3000);
      return () => clearInterval(id);
    }, [t.animations]);

    // Random connection flicker (cosmetic)
    useEffect(() => {
      const id = setInterval(() => {
        if (Math.random() < 0.06) {
          setWsState('connecting');
          setTimeout(() => setWsState('connected'), 800);
        }
      }, 7000);
      return () => clearInterval(id);
    }, []);

    // Keyboard
    useEffect(() => {
      const onKey = (e) => {
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
        } else if (e.key === 'r' || e.key === 'R') {
          setSnap(snapshot(Math.floor(Math.random() * 9999)));
        } else if (e.key === 'Escape') {
          setSel({});
        }
      };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }, [tab, cat]);

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
            <span style={{ fontSize: 14, letterSpacing: '.18em', fontWeight: 600 }}>AGORA TERMINAL</span>
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
        </div>

        {/* PANEL */}
        <div style={{ flex: 1, minHeight: 0, background: 'var(--bg)', position: 'relative' }}>
          {renderTab(tab, { snap, sel, setSelFor, setSel, setTab })}
        </div>

        {/* STATUS BAR */}
        <div className="nosel" style={{ height: 24, background: 'var(--surface-2)', borderTop: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', padding: '0 10px', gap: 14, fontSize: 10, letterSpacing: '.05em' }}>
          <span><span className="kbd">F1</span> <span className="mut">HELP</span></span>
          <span><span className="kbd">/</span>  <span className="mut">SEARCH</span></span>
          <span><span className="kbd">R</span>  <span className="mut">REFRESH</span></span>
          <span><span className="kbd">Tab</span> <span className="mut">NEXT</span></span>
          <span><span className="kbd">Esc</span> <span className="mut">CLEAR</span></span>
          <span style={{ flex: 1 }} />
          <span className="mut">ws://localhost:8000/ws</span>
          <span className="up">● LIVE</span>
          <span className="mut">·</span>
          <span><span><span className="mut">CAT</span> <span className="lbl">{(CATEGORIES.find(c => c.code === cat) || {}).label}</span></span></span>
          <span><span className="mut">VESSELS</span> <span className="lbl">{snap.ships.length}</span></span>
          <span><span className="mut">AIRCRAFT</span> <span className="lbl">{snap.aircraft.length}</span></span>
          <span><span className="mut">TICKERS</span> <span className="lbl">{snap.indices.length + snap.tech.length + snap.macro.length + snap.crypto.length}</span></span>
          <span><span className="mut">QUAKES</span> <span className="lbl">{snap.quakes.recent.length + snap.quakes.significant.length}</span></span>
          <span style={{ color: 'var(--muted)', minWidth: 64, textAlign: 'right' }}>guest@agora</span>
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
