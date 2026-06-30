// delta-maps.jsx — Leaflet wrapper components for DELTA Terminal
// Exposes window.DeltaMap (single component used by Aircraft, Ships, Space, Weather, Earthquakes, Parking)

(function () {
  const { useEffect, useRef, useState, useMemo } = React;

  // Canvas-rendered crosshair/triangle markers via Leaflet divIcons
  function planeIcon(p, selected) {
    const size = selected ? 18 : 14;
    const color = selected ? 'var(--cyan)' : (p.on_ground ? 'var(--muted)' : 'var(--mint)');
    const html = `
      <svg width="${size}" height="${size}" viewBox="-12 -12 24 24"
           style="transform: rotate(${p.heading || 0}deg); overflow: visible;">
        <path d="M0 -10 L 4 6 L 0 3 L -4 6 Z" style="fill: ${color}; stroke: ${selected ? 'var(--text)' : 'rgba(0,0,0,0.6)'}; stroke-width: ${selected ? 1.2 : 0.6};" />
      </svg>`;
    return L.divIcon({ html, className: 'delta-plane-icon' + (selected ? ' selected' : ''),
      iconSize: [size, size], iconAnchor: [size/2, size/2] });
  }
  function shipIcon(s, selected) {
    const size = selected ? 14 : 10;
    const palette = { 70: 'var(--cyan)', 80: 'var(--amber)', 60: 'var(--violet)', 30: 'var(--mint)' };
    const color = selected ? 'var(--cyan)' : (palette[s.vessel_type] || 'var(--text-2)');
    const html = `
      <div style="width:${size}px;height:${size}px;background:${color};
        transform: rotate(${s.heading || 0}deg);
        clip-path: polygon(50% 0, 100% 60%, 80% 100%, 20% 100%, 0 60%);
        box-shadow: 0 0 4px rgba(0,0,0,.7);
        border: ${selected ? '1.5px solid var(--text)' : 'none'};"></div>`;
    return L.divIcon({ html, className: 'delta-ship-icon' + (selected ? ' selected' : ''),
      iconSize: [size, size], iconAnchor: [size/2, size/2] });
  }
  function satIcon(name) {
    const html = `
      <div style="text-align:center;">
        <div style="font-size:18px; line-height:1; color: var(--violet); filter: drop-shadow(0 0 6px currentColor);">◈</div>
        <div style="font-size:9px; color:var(--violet); margin-top:2px; letter-spacing:.08em;
                    text-shadow: 0 0 4px var(--bg);">${name}</div>
      </div>`;
    return L.divIcon({ html, className: 'delta-sat-icon', iconSize: [60, 28], iconAnchor: [30, 14] });
  }
  function quakeIcon(q) {
    const r = 4 + q.magnitude * 2.4;
    const col = q.magnitude >= 7 ? 'var(--rose)' :
                q.magnitude >= 6 ? 'var(--amber)' :
                q.magnitude >= 5 ? 'var(--amber)' :
                q.magnitude >= 4 ? 'var(--cyan)' : 'var(--muted)';
    const html = `
      <div style="position:relative;width:${r*2}px;height:${r*2}px;">
        <div style="position:absolute;inset:0;border-radius:50%;border:1.5px solid ${col};
                    background:${col}33;box-shadow: 0 0 ${r*2}px ${col}66;"></div>
        ${q.magnitude >= 6 ? `<div style="position:absolute;inset:-6px;border-radius:50%;
            border:1px solid ${col}; animation: pulse 1.6s infinite;"></div>` : ''}
      </div>`;
    return L.divIcon({ html, className: '', iconSize: [r*2, r*2], iconAnchor: [r, r] });
  }
  function wxIcon(w) {
    const tCol = w.temp_c > 30 ? 'var(--rose)' : w.temp_c < 0 ? 'var(--cyan)' : 'var(--text)';
    const html = `
      <div style="background:var(--surface); border:1px solid var(--border-2);
                  padding:3px 6px; font-family: 'JetBrains Mono', monospace; font-size:10px;
                  white-space:nowrap; color:var(--text); box-shadow: 0 4px 10px rgba(0,0,0,.7);">
        <span style="margin-right:4px;">${w.icon}</span>
        <span style="color:${tCol};">${w.temp_c.toFixed(0)}°C</span>
        <span style="color:var(--muted); margin-left:6px;">${w.city}</span>
      </div>`;
    return L.divIcon({ html, className: '', iconSize: null, iconAnchor: [0, 0] });
  }
  function parkIcon(z) {
    const col = z.status === 'Available' ? 'var(--mint)'
             : z.status === 'Moderate'  ? 'var(--cyan)'
             : z.status === 'Busy'      ? 'var(--amber)' : 'var(--rose)';
    const html = `
      <div style="display:flex; align-items:center; gap:4px;
                  background: var(--surface); border:1px solid ${col};
                  padding: 2px 5px; font-family:'JetBrains Mono', monospace; font-size:10px;
                  color:${col}; white-space:nowrap; box-shadow:0 2px 6px rgba(0,0,0,.7);">
        <span style="font-size:11px;">P</span>
        <span>${z.free ?? '—'}/${z.total ?? '—'}</span>
      </div>`;
    return L.divIcon({ html, className: '', iconSize: null, iconAnchor: [12, 8] });
  }

  // ---------- Main map component ----------
  // Single-layer:  <DeltaMap kind="aircraft" items={planes} selectedId={id} onSelect={fn} />
  // Multi-layer:   <DeltaMap layers={[{kind:'aircraft',items:planes},{kind:'ships',items:ships}]}
  //                  selected={{kind,id}} onSelect={(id,kind)=>...} />
  function DeltaMap({ kind, items, layers, selectedId, selected, onSelect,
                     center = [25, 10], zoom = 2, fitBounds, children }) {
    const containerRef = useRef(null);
    const mapRef = useRef(null);
    const layerRef = useRef(null);
    const overlayRef = useRef(null);
    const markersById = useRef(new Map());
    const trailRef = useRef(null);

    // Normalize: always work with an array of {kind, items}
    const effLayers = useMemo(() =>
      layers && layers.length ? layers : (kind ? [{ kind, items: items || [] }] : []),
      [layers, kind, items]);
    // Selection normalized to { kind, id }
    const sel = selected || (selectedId ? { kind, id: selectedId } : null);

    useEffect(() => {
      if (mapRef.current) return;
      const map = L.map(containerRef.current, {
        center, zoom, minZoom: 2, maxZoom: 11,
        worldCopyJump: true, preferCanvas: true,
        zoomControl: true, attributionControl: true,
        zoomSnap: 0.5, zoomDelta: 0.5, wheelDebounceTime: 30,
        renderer: L.canvas({ padding: 0.6 }),
      });
      // Tile layers — Voyager has distinct land vs water (great for both themes via filters)
      const baseUrl = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png';
      const labelUrl = (light) => light
        ? 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png'
        : 'https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png';
      const isLight = document.documentElement.getAttribute('data-theme') === 'paper';
      let baseLayer = L.tileLayer(baseUrl, {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
      }).addTo(map);
      let labelLayer = L.tileLayer(labelUrl(isLight), {
        maxZoom: 19, attribution: '', subdomains: 'abcd', opacity: isLight ? 0.7 : 0.5,
      }).addTo(map);

      // Graticule (lat/lon grid) — color reads from theme via CSS var
      const gridColor = getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#2d2418';
      const grat = L.layerGroup();
      for (let lat = -60; lat <= 60; lat += 30) {
        L.polyline([[lat, -180], [lat, 180]], { color: gridColor, weight: 0.5, opacity: 0.6, interactive: false }).addTo(grat);
      }
      for (let lon = -180; lon <= 180; lon += 30) {
        L.polyline([[-85, lon], [85, lon]], { color: gridColor, weight: 0.5, opacity: 0.6, interactive: false }).addTo(grat);
      }
      grat.addTo(map);

      layerRef.current = L.layerGroup().addTo(map);
      overlayRef.current = L.layerGroup().addTo(map);
      trailRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;

      // Listen for theme changes — swap label layer only (base is same Voyager)
      const onTweak = (e) => {
        const light = document.documentElement.getAttribute('data-theme') === 'paper';
        if (labelLayer) map.removeLayer(labelLayer);
        labelLayer = L.tileLayer(labelUrl(light), {
          maxZoom: 19, attribution: '', subdomains: 'abcd', opacity: light ? 0.7 : 0.5,
        }).addTo(map);
      };
      window.addEventListener('tweakchange', onTweak);

      // Resize handler
      const ro = new ResizeObserver(() => { mapRef.current && mapRef.current.invalidateSize(); });
      ro.observe(containerRef.current);
      return () => {
        window.removeEventListener('tweakchange', onTweak);
        ro.disconnect(); map.remove(); mapRef.current = null;
      };
    }, []);

    // Rebuild markers on items change (iterates all layers)
    useEffect(() => {
      const map = mapRef.current;
      if (!map || !layerRef.current) return;
      const layer = layerRef.current;
      const prev = markersById.current;
      const nextMap = new Map();

      for (const lyr of effLayers) {
        const lk = lyr.kind;
        for (const item of (lyr.items || [])) {
          const id = idOf(item, lk);
          if (id == null || item.lat == null || item.lon == null) continue;
          const key = lk + '::' + id;
          let m = prev.get(key);
          const ll = [item.lat, item.lon];
          const isSel = !!(sel && sel.kind === lk && sel.id === id);
          if (m) {
            m.setLatLng(ll);
            if (m._sel !== isSel || (lk === 'aircraft' && m._hdg !== item.heading)) {
              m.setIcon(iconFor(lk, item, isSel));
              m._sel = isSel;
              m._hdg = item.heading;
            }
          } else {
            m = L.marker(ll, { icon: iconFor(lk, item, isSel), interactive: true, riseOnHover: true });
            m._sel = isSel;
            m._hdg = item.heading;
            m._kind = lk;
            m.on('click', () => onSelect && onSelect(id, lk));
            const tipText = tooltipFor(lk, item);
            if (tipText) m.bindTooltip(tipText, { className: 'delta-tip', direction: 'top', offset: [0, -8] });
            m.addTo(layer);
          }
          nextMap.set(key, m);
          prev.delete(key);
        }
      }
      // Remove stale
      for (const m of prev.values()) layer.removeLayer(m);
      markersById.current = nextMap;
    }, [effLayers, sel && sel.kind, sel && sel.id]);

    // Fit bounds when changed
    useEffect(() => {
      if (fitBounds && mapRef.current) {
        mapRef.current.fitBounds(fitBounds, { padding: [30, 30] });
      }
    }, [fitBounds && fitBounds.toString()]);

    // Fly to selected
    useEffect(() => {
      if (!mapRef.current || !sel) return;
      const lyr = effLayers.find(l => l.kind === sel.kind);
      const item = lyr && lyr.items.find(i => idOf(i, sel.kind) === sel.id);
      if (!item) return;
      mapRef.current.panTo([item.lat, item.lon], { animate: true });
      // Heading trail for aircraft/ships
      trailRef.current && trailRef.current.clearLayers();
      if ((sel.kind === 'aircraft' || sel.kind === 'ships') && item.heading != null) {
        const rad = (item.heading - 90) * Math.PI / 180;
        const km = sel.kind === 'aircraft' ? 600 : 80;
        const dLat = (km * Math.sin(-rad)) / 111;
        const dLon = (km * Math.cos(rad)) / (111 * Math.max(0.1, Math.cos(item.lat * Math.PI / 180)));
        const accent = getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim() || '#f5a524';
        L.polyline([[item.lat, item.lon], [item.lat + dLat, item.lon + dLon]], {
          color: accent, weight: 1.2, opacity: 0.7, dashArray: '4 4', interactive: false,
        }).addTo(trailRef.current);
        L.circleMarker([item.lat, item.lon], {
          radius: 14, color: accent, fillColor: 'transparent', weight: 1.5, opacity: 0.7,
        }).addTo(trailRef.current);
      }
    }, [sel && sel.id, sel && sel.kind, effLayers]);

    return (
      <div style={{ position: 'relative', width: '100%', height: '100%' }}>
        <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
        {children}
      </div>
    );
  }

  function idOf(item, kind) {
    if (kind === 'aircraft') return item.icao24;
    if (kind === 'ships') return item.mmsi;
    if (kind === 'space') return item.norad_id;
    if (kind === 'weather') return item.city;
    if (kind === 'earthquakes') return item.event_id;
    if (kind === 'parking') return item.zone_id;
    return item.id;
  }
  function iconFor(kind, item, sel) {
    if (kind === 'aircraft') return planeIcon(item, sel);
    if (kind === 'ships')    return shipIcon(item, sel);
    if (kind === 'space')    return satIcon(item.name);
    if (kind === 'weather')  return wxIcon(item);
    if (kind === 'earthquakes') return quakeIcon(item);
    if (kind === 'parking') return parkIcon(item);
  }
  function tooltipFor(kind, item) {
    if (kind === 'aircraft')
      return `${item.callsign}  ${item.type}\n${item.fl}  ${item.speed_kts}kts  ${item.heading_arrow}${item.heading}°`;
    if (kind === 'ships')
      return `${item.name}\n${item.type_name} · ${item.flag} · ${item.speed_kts}kts\n→ ${item.destination}`;
    if (kind === 'space')
      return `${item.name}  ALT ${item.altitude_km}km  VEL ${item.velocity_kms}km/s`;
    if (kind === 'earthquakes')
      return `M${item.magnitude.toFixed(1)}  ${item.place}\nDepth ${item.depth_km}km · ${item.time_ago}`;
    if (kind === 'parking')
      return `${item.name}\n${item.free ?? '—'}/${item.total} · ${item.status} · ${item.occ_pct != null ? item.occ_pct + '%' : '—'}`;
    return null;
  }

  window.DeltaMap = DeltaMap;
})();
