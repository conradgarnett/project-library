# Delta Terminal

An open-source, Bloomberg-style markets and world-data terminal built entirely
from **free and public APIs** — no paid data subscriptions. A FastAPI backend
aggregates dozens of live data feeds and serves them as REST JSON plus a
WebSocket stream; a browser/Electron frontend renders them as terminal panels.

## Architecture

```
feeds/*.py   →   server.py (FastAPI)   →   static/delta/*.jsx   →   delta-terminal-app/
 48 data         REST /api/* + WebSocket    React panel UI            Electron desktop
 sources         live stream                (served at /delta/)       wrapper
```

- **`server.py`** — FastAPI backend. Exposes each feed under `/api/...`, pushes
  live updates over a WebSocket, and serves the static frontend. Loads a `.env`
  for any optional API keys before the feeds read the environment.
- **`feeds/`** — ~48 self-contained feed modules, each fetching and normalizing
  one data source.
- **`static/delta/`** — the panel-based frontend (JSX): shell, panels, live
  data, maps, options, 3-D order-flow, and category views.
- **`delta-terminal-app/`** — Electron wrapper that launches the Python server
  and loads the UI as a desktop app.
- **`prototyping/`** — earlier iterations (Textual TUI, pywebview desktop) kept
  for reference; see `prototyping/README.md`.

## Data feeds

Roughly 48 feeds spanning markets and the wider world:

- **Markets & finance** — equities, crypto, bonds, forex, FRED macro series,
  options flow, options mispricing, dark pool, earnings, economic calendar,
  SEC EDGAR filings, energy (EIA), charts and analyst recommendations.
- **Geospatial & physical** — live aircraft, ships, satellites, space weather,
  weather, earthquakes, wildfires, climate and ocean data, public cameras.
- **Geopolitics & society** — conflicts, sanctions, elections, threats, refugee
  (UNHCR) and health (WHO) data, population, trade.
- **Tech & information** — CVE feeds, Cloudflare/outage status, arXiv,
  Hacker News, clinical trials, and general news.

## Running it

```bash
# backend
python server.py           # serves http://localhost:8000

# desktop app (spawns the server automatically)
cd delta-terminal-app
npm install
npm start
```

Then open <http://localhost:8000> in a browser, or use the Electron app.

## Notes

- Feeds degrade gracefully: a source that is rate-limited or unavailable is
  skipped rather than breaking the terminal. `feeds/yf_throttle.py` provides a
  throttled yfinance client to stay within free rate limits.
- API keys are optional — most feeds are fully keyless. Any keys go in a local
  `.env` and are never committed.
