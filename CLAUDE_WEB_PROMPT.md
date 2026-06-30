# Open Bloomberg Terminal — UI Build Brief for Claude

Build a **single-page web application** styled as a professional Bloomberg Terminal clone.
The frontend connects to a local FastAPI backend at `http://localhost:8000`.

---

## What to Build

A dark, dense, information-rich financial terminal dashboard. Think original Bloomberg Terminal:
- Black/dark-navy background, no whitespace wasted
- Monospace font throughout (use `'JetBrains Mono', 'Fira Code', 'Courier New', monospace`)
- Green for positive / up, red for negative / down, cyan/blue for labels
- Scrolling top ticker bar
- 8 tabbed panels (Markets, Aircraft, Ships, Space, Weather, Earthquakes, News, Parking)
- Real-time updates via WebSocket

---

## Color Palette

```
Background:     #0a0e1a   (main bg)
Surface:        #0d1b2a   (panel bg, headers)
Border:         #1e3a5f
Accent blue:    #00aaff   (labels, column headers, active tab)
Accent green:   #00d4aa   (positive, up, live, callsigns)
Accent red:     #ff4466   (negative, down, alerts)
Accent yellow:  #ffaa00   (warnings)
Text primary:   #c8d8e8
Text muted:     #446688
Text dim:       #2a4a6a
```

---

## Typography & Layout

- Font: `'JetBrains Mono', 'Fira Code', monospace` everywhere
- Font size: 12px base, 11px for table rows, 13px bold for values
- No rounded corners (or 2px max radius)
- Thin 1px borders in `#1e3a5f`
- Tables: zebra-striped (`#0c1220` for even rows), no cell padding > 4px 6px

---

## Overall Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  TICKER BAR  (scrolling marquee, #00d4aa text on #0d1b2a bg)       │  h: 28px
├───────────────────────────────────────────────────────────────────-│
│  ◆ OPEN BLOOMBERG TERMINAL          [UTC clock]    [status dots]   │  h: 40px
├────────────────────────────────────────────────────────────────────│
│  [◈ Markets] [✈ Aircraft] [⚓ Ships] [🛰 Space] [🌦 Weather]        │  h: 36px
│  [🌍 Quakes] [📰 News] [🅿 Parking]                                │
├────────────────────────────────────────────────────────────────────│
│                                                                    │
│   (Active tab content — full height, scrollable)                   │
│                                                                    │
├────────────────────────────────────────────────────────────────────│
│  STATUS BAR  Q: quit | R: refresh | 1-8: panels | WS: connected   │  h: 24px
└────────────────────────────────────────────────────────────────────┘
```

---

## Backend API

**Base URL:** `http://localhost:8000`

### REST Endpoints (fetch on tab switch + polling)

| Endpoint | Returns |
|---|---|
| `GET /api/markets` | `{ quotes: {TICKER: Quote}, groups: {GroupName: [tickers]} }` |
| `GET /api/crypto` | `{ ticks: {symbol: CryptoTick} }` |
| `GET /api/aircraft` | `{ total, airborne, planes: [Aircraft], error }` |
| `GET /api/ships` | `{ total, underway, vessels: [Vessel], source, error }` |
| `GET /api/space` | `{ iss, tiangong, notable: [Satellite], starlink_count, active_count }` |
| `GET /api/weather` | `{ cities: {name: Weather} }` |
| `GET /api/earthquakes` | `{ recent: [Quake], significant: [Quake], hourly_count, daily_count, largest_today }` |
| `GET /api/news` | `{ articles: [Article], by_category: {cat: [Article]} }` |
| `GET /api/parking` | `{ zones: [Zone], by_city: {city: [Zone]} }` |
| `GET /api/status` | `{ feeds: {name: bool}, ws_clients: n }` |

### WebSocket

`ws://localhost:8000/ws`

Receives JSON messages: `{ event: string, data: object, ts: number }`

Events: `init`, `markets`, `crypto`, `aircraft`, `ships`, `space`, `earthquakes`

On connect, server immediately sends `init` with current markets + crypto state.
Subscribe to updates — crypto comes in real-time (Binance stream), others every 15-30s.

---

## Data Shapes

### Quote
```ts
{
  ticker: string        // e.g. "^GSPC"
  name: string          // e.g. "S&P 500"
  price: number
  change: number        // absolute change
  change_pct: number    // percentage
  volume: number
  day_high: number
  day_low: number
  arrow: "▲" | "▼"
  color: "green" | "red"
}
```

### CryptoTick
```ts
{
  symbol: string        // e.g. "BTCUSDT"
  name: string          // e.g. "Bitcoin"
  price: number
  change_24h: number
  change_pct_24h: number
  volume_24h: number
  high_24h: number
  low_24h: number
  arrow: "▲" | "▼"
  color: "green" | "red"
}
```

### Aircraft
```ts
{
  icao24: string
  callsign: string
  country: string
  lat: number | null
  lon: number | null
  altitude_ft: number | null
  speed_kts: number | null
  heading: number | null
  heading_arrow: string   // ↑ ↗ → ↘ ↓ ↙ ← ↖
  fl: string              // e.g. "FL350" or "GND"
  on_ground: boolean
  vertical_rate: number | null
}
```

### Vessel
```ts
{
  mmsi: string
  name: string
  callsign: string
  vessel_type: number
  type_name: string       // e.g. "Cargo", "Tanker"
  lat: number | null
  lon: number | null
  speed_kts: number | null
  course: number | null
  heading: number | null
  heading_arrow: string
  nav_status: number
  status_name: string     // e.g. "Under way (engine)"
  destination: string
  flag: string
}
```

### SpaceStation (ISS / Tiangong)
```ts
{
  name: string
  norad_id: number
  lat: number
  lon: number
  altitude_km: number
  altitude_mi: number
  velocity_kms: number
  visibility: string
  ground_track: string    // e.g. "41.23°N 74.01°W"
}
```

### Satellite (TLE object)
```ts
{
  name: string
  norad_id: string
  orbit_type: string      // "LEO" | "MEO" | "GEO" | "HEO"
  inclination: number
  apogee_km: number
  perigee_km: number
  period_min: number
  eccentricity: number
}
```

### Weather
```ts
{
  city: string
  lat: number
  lon: number
  temp_c: number
  temp_f: number
  feels_like_c: number
  humidity: number
  wind_speed_kph: number
  wind_direction_str: string   // "N" | "NE" | "E" | ...
  precipitation_mm: number
  condition: string            // e.g. "Clear", "Rain"
  icon: string                 // emoji: ☀️ ⛅ 🌧 ❄️ ⛈ etc.
  is_day: boolean
}
```

### Earthquake
```ts
{
  event_id: string
  magnitude: number
  magnitude_str: string   // e.g. "M6.2"
  mag_type: string
  place: string
  lat: number
  lon: number
  depth_km: number
  time_utc: string        // ISO 8601
  time_ago: string        // e.g. "12m ago"
  felt: number
  alert: "green"|"yellow"|"orange"|"red"|null
  tsunami: boolean
  sig: number
  severity_color: string  // tailwind-compatible color name
}
```

### Article
```ts
{
  id: string
  source: string          // e.g. "Reuters", "BBC World"
  title: string
  summary: string
  link: string
  published: string | null  // ISO 8601
  time_ago: string
  category: string        // "Top" | "Markets" | "Business" | "Tech" | "Space" | "Aviation" | "Shipping"
}
```

### ParkingZone
```ts
{
  zone_id: string
  city: string            // "New York City" | "San Francisco" | "Chicago"
  location: string
  lat: number | null
  lon: number | null
  total_spaces: number
  available_spaces: number | null
  occupancy_pct: number | null
  rate_per_hour: number | null
  time_limit_min: number | null
  zone_type: string       // "metered" | "garage"
  status: string          // "Available" | "Moderate" | "Busy" | "Full" | "Unknown"
  status_color: string
}
```

---

## Panel Specs

### 1. MARKETS Tab

Split into 4 quadrants:

**Top-left:** Indices & ETFs — columns: `Symbol | Name | Price | Change | High | Low | Volume`
- Tickers: `^GSPC, ^DJI, ^IXIC, ^RUT, ^VIX, ^FTSE, ^N225, ^HSI, SPY, QQQ, IWM, GLD, TLT, HYG, EEM, XLE`

**Top-right:** Crypto (real-time Binance) — columns: `Coin | Price $ | 24h % | 24h $ | High | Low | Volume`
- Flash the row green/red briefly when price updates

**Bottom-left:** Tech equities — columns same as indices
- Tickers: `AAPL, MSFT, NVDA, GOOGL, META, AMZN, TSLA, AMD`

**Bottom-right:** Macro — columns same as indices
- Tickers: `GC=F (Gold), CL=F (Oil), SI=F (Silver), DX-Y.NYB (USD), EURUSD=X, JPY=X`

All price changes: green with ▲ if positive, red with ▼ if negative.

---

### 2. AIRCRAFT Tab

Full-width table. Stat bar above: `✈ Total: N   Airborne: N   On Ground: N   Updated: HH:MM:SS UTC`

Columns: `ICAO | Callsign | Country | Lat | Lon | Altitude ft | Speed kts | Hdg | FL | Status`

- Callsign in `#00d4aa`
- Airborne rows: normal; Ground rows: dimmed
- `FL` column bold when airborne
- Sort by altitude descending by default
- Clicking a column header sorts by that column

---

### 3. SHIPS Tab

Full-width table. Stat bar above: `⚓ Vessels: N   Under Way: N   Source: XXX`

If `error` is set, show a yellow warning with instructions.

Columns: `MMSI | Name | Flag | Type | Lat | Lon | Speed kts | Course | Status`

- Name in `#00d4aa`
- Under-way rows brighter, moored/anchored rows dimmed
- Sort by speed descending

---

### 4. SPACE Tab

**Top half:** Two side-by-side stat cards for ISS and Tiangong:
```
┌─ ISS ─────────────────────────────────┐
│ Lat: 41.23°N   Lon: 74.01°W           │
│ Alt: 408.3 km  (253.6 mi)             │
│ Vel: 7.66 km/s  (17,137 mph)          │
│ Visibility: daylight                  │
│ Updated: 14:32:01 UTC                 │
└───────────────────────────────────────┘
```

**Bottom half:** Split table — left: "Visually Tracked Objects" from CelesTrak, right: "Starlink Fleet"

Columns: `Name | NORAD | Orbit | Inc° | Apogee km | Perigee km | Period min`

Orbit type color-coded: LEO=cyan, MEO=blue, GEO=green, HEO=yellow

---

### 5. WEATHER Tab

Full-width table of 15 world cities.

Columns: `City | Icon+Condition | Temp °C | Feels °C | Temp °F | Humidity | Wind km/h | Direction | Precip mm`

- Temp color: red if >35°C or <-10°C
- High humidity (>80%) in cyan
- High wind (>50 km/h) in orange
- Precipitation >0 in cyan

---

### 6. EARTHQUAKES Tab

Stats bar: `Last hour: N   Today: N   Largest today: M6.2 — Place Name`

**Top section:** "Significant Earthquakes (30 days)" table
**Bottom section:** "Last Hour" table

Columns: `Magnitude | Location | Depth km | Lat | Lon | When | Tsunami | Alert | Felt`

Magnitude color: `≥7.0`=red bold, `≥6.0`=orange, `≥5.0`=yellow, `≥4.0`=cyan, else dim
Tsunami `YES` in red bold.

---

### 7. NEWS Tab

Stats bar: `Sources OK: N   Failed: N   Articles: N   Updated: HH:MM:SS`

Below: grouped by category (Top, Markets, Business, Tech, Space, Aviation, Shipping)
Each category has a blue header row, then articles:

```
── TOP ──────────────────────────────────────────────────────
  [ 3m] [Reuters]  Headline text in bold
          Short summary text in dim color, truncated to ~120 chars...
  [12m] [BBC World] Another headline...
```

Clicking a headline opens `article.link` in a new tab.

---

### 8. PARKING Tab

Stats bar: `Zones: N   Total Spaces: N,NNN   Cities: New York City, San Francisco, Chicago`

Full-width table:

Columns: `City | Location | Total | Available | Occupancy | Status | $/hr | Time Limit`

Status color-coded: Available=green, Moderate=cyan, Busy=yellow, Full=red

---

## Ticker Bar

Scrolling marquee at the very top. Content:
```
S&P 500: 5,123.45 ▲0.34%   ·   DOW: 38,921 ▲0.12%   ·   Bitcoin: $67,234 ▲2.1%   ·   ...
```

Update in real-time from WebSocket `markets` and `crypto` events.
Scroll speed: ~50px/sec continuous loop.

---

## WebSocket Integration

```js
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (e) => {
  const { event, data } = JSON.parse(e.data);
  switch (event) {
    case 'init':
      updateMarkets(data.markets);
      updateCrypto(data.crypto);
      break;
    case 'markets':   updateMarkets(data); break;
    case 'crypto':    updateCrypto(data); break;   // real-time, flash rows
    case 'aircraft':  updateAircraft(data); break;
    case 'ships':     updateShips(data); break;
    case 'space':     updateSpace(data); break;
    case 'earthquakes': updateEarthquakes(data); break;
  }
};

// Reconnect on disconnect
ws.onclose = () => setTimeout(() => reconnect(), 3000);
```

---

## Connection Status Indicator

Top-right of header bar. Three dots:
- `●` green = WS connected
- `●` yellow = connecting / polling-only mode
- `●` red = disconnected

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1`–`8` | Switch to panel |
| `Tab` | Next panel |
| `R` | Force refresh current panel (re-fetch REST endpoint) |
| `/` | Focus search/filter input in current table |
| `Esc` | Clear filter |

---

## Tech Stack Recommendation

Use **vanilla HTML + CSS + JavaScript** (no build step required). A single `index.html` file that:
1. Connects to `ws://localhost:8000/ws` on load
2. Falls back to polling REST endpoints every 15s if WS fails
3. Uses CSS Grid/Flexbox for layout
4. Sorts tables client-side on header click
5. Has a filter/search input per table

Alternatively, React or Vue is fine if preferred.

---

## File to Serve

The `index.html` (or React app) can be placed in `~/bloomberg/static/` and served by the existing FastAPI backend. Or opened directly in a browser (CORS is enabled on the backend).

---

## Notes

- All data is live — no mock data needed, the backend serves real feeds
- Markets data has a 15-min Yahoo Finance delay (normal for free tier)
- Crypto is true real-time via Binance WebSocket
- Aircraft updates every 15s from OpenSky Network
- Ships may show limited data depending on AIS stream availability
- ISS position updates every 60s
- Weather updates every 5 minutes (Open-Meteo)
- News updates every 2 minutes (RSS feeds)

---

*Open Bloomberg Terminal — Free, open source, no API keys required.*
*Backend: FastAPI + Python. Frontend: your choice.*
*Start backend: `cd ~/bloomberg && python server.py`*
