#!/usr/bin/env python3
"""
Open Bloomberg Terminal
Free, open-source alternative to Bloomberg Terminal.
All data sources require no API keys.

Usage:
    python main.py

Keys:
    Tab / Shift+Tab  — navigate panels
    Q                — quit
    R                — force refresh all feeds
    F                — toggle fullscreen panel
    1-7              — jump to panel
"""

import asyncio
import time
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, TabbedContent, TabPane, DataTable,
    Label, RichLog, Static, Digits
)
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual import work, on
from textual.binding import Binding
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

# ── data feeds ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from feeds import market, crypto, aircraft, ships, space, weather, earthquakes, news, parking

# ── refresh intervals (seconds) ─────────────────────────────────────────────
REFRESH_MARKET    = 30
REFRESH_AIRCRAFT  = 15
REFRESH_SHIPS     = 30
REFRESH_SPACE     = 60
REFRESH_WEATHER   = 300
REFRESH_EQ        = 60
REFRESH_NEWS      = 120
REFRESH_PARKING   = 300
REFRESH_UI        = 5      # UI repaint interval


def fmt_price(v: float, decimals: int = 2) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    elif v >= 1_000:
        return f"{v:,.{decimals}f}"
    return f"{v:.{decimals}f}"


def fmt_change(v: float, pct: float) -> Text:
    sign  = "▲" if v >= 0 else "▼"
    color = "green" if v >= 0 else "red"
    t = Text()
    t.append(f"{sign}{abs(v):.2f} ({abs(pct):.2f}%)", style=color)
    return t


def fmt_volume(v: float) -> str:
    if v >= 1e9: return f"{v/1e9:.1f}B"
    if v >= 1e6: return f"{v/1e6:.1f}M"
    if v >= 1e3: return f"{v/1e3:.0f}K"
    return str(int(v))


# ── Widgets ──────────────────────────────────────────────────────────────────

class TickerBar(Static):
    """Scrolling top ticker bar."""
    DEFAULT_CSS = "TickerBar { height: 1; background: #0d1b2a; overflow: hidden; }"
    _offset: reactive[int] = reactive(0)
    _content: str = ""

    def update_content(self, text: str) -> None:
        self._content = text

    def on_mount(self) -> None:
        self.set_interval(0.1, self._scroll)

    def _scroll(self) -> None:
        if not self._content:
            return
        self._offset = (self._offset + 1) % max(1, len(self._content))
        display = self._content[self._offset:] + "    " + self._content[:self._offset]
        self.update(Text(display[:self.size.width * 2], style="#00d4aa"))


class SectionHeader(Static):
    """Colored section header bar."""
    DEFAULT_CSS = "SectionHeader { height: 1; background: #0d1b2a; color: #00aaff; text-style: bold; }"

    def __init__(self, title: str, subtitle: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title
        self._subtitle = subtitle

    def on_mount(self) -> None:
        t = Text()
        t.append(f" ▶ {self._title}", style="bold #00aaff")
        if self._subtitle:
            t.append(f"  {self._subtitle}", style="#446688")
        self.update(t)


# ── Market Tab ───────────────────────────────────────────────────────────────

class MarketTab(Container):
    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="market-left"):
                yield SectionHeader("INDICES & ETFS", id="mh-1")
                yield DataTable(id="dt-indices", zebra_stripes=True, cursor_type="row")
                yield SectionHeader("EQUITIES", id="mh-2")
                yield DataTable(id="dt-equities", zebra_stripes=True, cursor_type="row")
            with Vertical(id="market-right"):
                yield SectionHeader("CRYPTOCURRENCY  (Binance real-time)", id="mh-3")
                yield DataTable(id="dt-crypto", zebra_stripes=True, cursor_type="row")
                yield SectionHeader("MACRO", id="mh-4")
                yield DataTable(id="dt-macro", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        self._init_tables()

    def _init_tables(self) -> None:
        cols = [("Symbol", 10), ("Name", 22), ("Price", 14), ("Change", 20), ("High", 12), ("Low", 12), ("Volume", 10)]
        for tid in ("dt-indices", "dt-equities", "dt-macro"):
            dt = self.query_one(f"#{tid}", DataTable)
            for col, w in cols:
                dt.add_column(col, width=w)

        dt_c = self.query_one("#dt-crypto", DataTable)
        for col, w in [("Coin", 12), ("Name", 14), ("Price $", 16), ("24h Change", 22), ("High", 14), ("Low", 14), ("Volume", 14)]:
            dt_c.add_column(col, width=w)

    def refresh_market(self, quotes: dict) -> None:
        groups = {
            "dt-indices":  market.WATCHLIST["Indices"] + market.WATCHLIST["ETFs"],
            "dt-equities": market.WATCHLIST["Tech"],
            "dt-macro":    market.WATCHLIST["Macro"],
        }
        for tid, tickers in groups.items():
            dt = self.query_one(f"#{tid}", DataTable)
            dt.clear()
            for t in tickers:
                q = quotes.get(t)
                if not q:
                    continue
                color = "green" if q.change >= 0 else "red"
                dt.add_row(
                    t,
                    q.name,
                    Text(fmt_price(q.price), style="bold"),
                    fmt_change(q.change, q.change_pct),
                    Text(fmt_price(q.day_high or 0), style="dim"),
                    Text(fmt_price(q.day_low or 0), style="dim"),
                    Text(fmt_volume(q.volume or 0), style="dim"),
                )

    def refresh_crypto(self, ticks: dict) -> None:
        dt = self.query_one("#dt-crypto", DataTable)
        dt.clear()
        for sym, tick in sorted(ticks.items(), key=lambda x: x[1].price, reverse=True):
            color = "green" if tick.change_pct_24h >= 0 else "red"
            arrow = "▲" if tick.change_pct_24h >= 0 else "▼"
            dt.add_row(
                Text(tick.symbol.replace("USDT", ""), style="bold"),
                tick.name,
                Text(f"${tick.price:,.2f}", style="bold"),
                Text(f"{arrow}{abs(tick.change_pct_24h):.2f}%  ${abs(tick.change_24h):,.2f}", style=color),
                Text(f"${tick.high_24h:,.2f}", style="dim"),
                Text(f"${tick.low_24h:,.2f}", style="dim"),
                Text(fmt_volume(tick.volume_24h), style="dim"),
            )


# ── Aircraft Tab ─────────────────────────────────────────────────────────────

class AircraftTab(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("LIVE AIRCRAFT  (OpenSky Network — anonymous)", id="aircraft-header")
        yield DataTable(id="dt-aircraft", zebra_stripes=True, cursor_type="row")
        yield Static(id="aircraft-stats", classes="neutral")

    def on_mount(self) -> None:
        dt = self.query_one("#dt-aircraft", DataTable)
        for col, w in [
            ("ICAO", 8), ("Callsign", 10), ("Country", 16),
            ("Lat", 8), ("Lon", 8), ("Alt", 8), ("Spd kts", 8),
            ("Hdg", 5), ("FL", 6), ("Status", 10),
        ]:
            dt.add_column(col, width=w)

    def refresh(self, state: aircraft.AircraftState) -> None:
        dt = self.query_one("#dt-aircraft", DataTable)
        stats = self.query_one("#aircraft-stats", Static)
        dt.clear()

        if state.error:
            stats.update(Text(f" ⚠ {state.error}", style="yellow"))
        else:
            t = Text()
            t.append(f" ✈ Total: ", style="dim")
            t.append(str(state.total), style="bold #00aaff")
            t.append("  Airborne: ", style="dim")
            t.append(str(state.airborne), style="bold green")
            t.append("  On Ground: ", style="dim")
            t.append(str(state.total - state.airborne), style="bold yellow")
            t.append(f"  Updated: {datetime.utcfromtimestamp(state.updated).strftime('%H:%M:%S')} UTC", style="dim")
            stats.update(t)

        # Sort by altitude descending, show top 200
        planes = sorted(state.aircraft, key=lambda p: p.altitude_m or 0, reverse=True)[:200]
        for p in planes:
            status_color = "dim" if p.on_ground else "green"
            dt.add_row(
                Text(p.icao24.upper(), style="dim"),
                Text(p.callsign or "---", style="bold #00d4aa"),
                Text(p.origin_country or "---", style="dim"),
                Text(f"{p.latitude:.2f}" if p.latitude else "---", style="dim"),
                Text(f"{p.longitude:.2f}" if p.longitude else "---", style="dim"),
                Text(f"{int(p.altitude_ft or 0):,}" if p.altitude_ft else ("GND" if p.on_ground else "---"), style=status_color),
                Text(f"{int(p.speed_kts or 0)}" if p.speed_kts else "---", style="dim"),
                Text(p.heading_arrow, style="#00aaff"),
                Text(p.fl, style="bold" if not p.on_ground else "dim"),
                Text("Ground" if p.on_ground else "Airborne", style=status_color),
            )


# ── Ships Tab ────────────────────────────────────────────────────────────────

class ShipsTab(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("VESSEL TRAFFIC  (AIS — public stream)", id="ships-header")
        yield DataTable(id="dt-ships", zebra_stripes=True, cursor_type="row")
        yield Static(id="ships-stats", classes="neutral")

    def on_mount(self) -> None:
        dt = self.query_one("#dt-ships", DataTable)
        for col, w in [
            ("MMSI", 10), ("Name", 20), ("Flag", 6),
            ("Type", 16), ("Lat", 8), ("Lon", 8),
            ("Speed kts", 10), ("Course", 7), ("Status", 22),
        ]:
            dt.add_column(col, width=w)

    def refresh(self, state: ships.ShipState) -> None:
        dt = self.query_one("#dt-ships", DataTable)
        stats_w = self.query_one("#ships-stats", Static)
        dt.clear()

        if state.error:
            t = Text()
            t.append(f" ⚠ {state.error}", style="yellow")
            t.append("\n\n   To enable global AIS: register free at aishub.net (no credit card), then", style="dim")
            t.append("\n   set env var AISHUB_USERNAME=your_username before starting.", style="dim")
            stats_w.update(t)
        else:
            t = Text()
            t.append(f" ⚓ Vessels: ", style="dim")
            t.append(str(state.total), style="bold #00aaff")
            t.append("  Under Way: ", style="dim")
            t.append(str(state.underway), style="bold green")
            t.append(f"  Source: {state.source}", style="dim")
            t.append(f"  {datetime.utcfromtimestamp(state.updated).strftime('%H:%M:%S')} UTC", style="dim")
            stats_w.update(t)

        for v in sorted(state.vessels, key=lambda x: x.speed_kts or 0, reverse=True)[:150]:
            color = "green" if v.nav_status == 0 else "dim"
            dt.add_row(
                Text(v.mmsi, style="dim"),
                Text(v.name or "---", style="bold #00d4aa"),
                Text(v.flag or "---", style="dim"),
                Text(v.type_name, style="dim"),
                Text(f"{v.lat:.3f}" if v.lat else "---", style="dim"),
                Text(f"{v.lon:.3f}" if v.lon else "---", style="dim"),
                Text(f"{v.speed_kts:.1f}" if v.speed_kts is not None else "---", style=color),
                Text(f"{v.heading_arrow} {int(v.course or 0)}°" if v.course else "---", style="dim"),
                Text(v.status_name, style=color),
            )


# ── Space Tab ────────────────────────────────────────────────────────────────

class SpaceTab(Container):
    def compose(self) -> ComposeResult:
        with Horizontal(id="space-top"):
            yield Container(id="iss-panel")
            yield Container(id="tg-panel")
        with Horizontal():
            with Vertical(classes="split-left"):
                yield SectionHeader("VISUALLY TRACKED OBJECTS  (CelesTrak)", id="space-h1")
                yield DataTable(id="dt-sats", zebra_stripes=True, cursor_type="row")
            with Vertical(classes="split-right"):
                yield SectionHeader("STARLINK CONSTELLATION", id="space-h2")
                yield DataTable(id="dt-starlink", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        for tid in ("dt-sats", "dt-starlink"):
            dt = self.query_one(f"#{tid}", DataTable)
            for col, w in [("Name", 24), ("NORAD", 7), ("Orbit", 5), ("Inc°", 6),
                           ("Apo km", 8), ("Per km", 8), ("Period", 8)]:
                dt.add_column(col, width=w)

    def refresh(self, state: space.SpaceState) -> None:
        # ISS panel
        iss_p = self.query_one("#iss-panel", Container)
        iss_p.remove_children()
        if state.iss:
            i = state.iss
            lines = [
                Text(f" ISS — International Space Station", style="bold #00aaff"),
                Text(f" Lat: {i.lat:+.4f}°  Lon: {i.lon:+.4f}°", style="#00d4aa"),
                Text(f" Alt: {i.altitude_km:.1f} km  ({i.altitude_mi:.1f} mi)", style="#c8d8e8"),
                Text(f" Vel: {i.velocity_kms:.2f} km/s  ({i.velocity_kms * 2236.94:.0f} mph)", style="#c8d8e8"),
                Text(f" Vis: {i.visibility or 'N/A'}  {datetime.utcfromtimestamp(i.updated).strftime('%H:%M:%S')} UTC", style="dim"),
            ]
            for l in lines:
                iss_p.mount(Static(l))

        # Tiangong panel
        tg_p = self.query_one("#tg-panel", Container)
        tg_p.remove_children()
        if state.tiangong:
            t = state.tiangong
            lines = [
                Text(f" Tiangong — Chinese Space Station", style="bold #00aaff"),
                Text(f" Lat: {t.lat:+.4f}°  Lon: {t.lon:+.4f}°", style="#00d4aa"),
                Text(f" Alt: {t.altitude_km:.1f} km  ({t.altitude_mi:.1f} mi)", style="#c8d8e8"),
                Text(f" Vel: {t.velocity_kms:.2f} km/s  ({t.velocity_kms * 2236.94:.0f} mph)", style="#c8d8e8"),
                Text(f" Vis: {t.visibility or 'N/A'}  {datetime.utcfromtimestamp(t.updated).strftime('%H:%M:%S')} UTC", style="dim"),
            ]
            for l in lines:
                tg_p.mount(Static(l))

        # Satellites table
        dt = self.query_one("#dt-sats", DataTable)
        dt.clear()
        for obj in state.notable[:80]:
            dt.add_row(
                Text(obj.name[:23], style="#00d4aa"),
                Text(obj.norad_id, style="dim"),
                Text(obj.orbit_type, style="bold"),
                Text(f"{obj.inclination:.1f}", style="dim"),
                Text(f"{obj.apogee_km:,.0f}", style="dim"),
                Text(f"{obj.perigee_km:,.0f}", style="dim"),
                Text(f"{obj.period_min:.1f}m", style="dim"),
            )

        # Starlink
        stk = self.query_one("#dt-starlink", DataTable)
        stk.clear()
        stk.add_row(
            Text("Starlink Fleet", style="bold"),
            Text(str(state.starlink_count), style="#00aaff"),
            "LEO", "53.0°", "540", "540", "97m",
        )


# ── Weather Tab ──────────────────────────────────────────────────────────────

class WeatherTab(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("GLOBAL WEATHER  (Open-Meteo — no API key)", id="wx-header")
        yield DataTable(id="dt-weather", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        dt = self.query_one("#dt-weather", DataTable)
        for col, w in [
            ("City", 16), ("Condition", 22), ("Temp °C", 9), ("Feels °C", 9),
            ("Temp °F", 9), ("Humidity", 10), ("Wind km/h", 10), ("Wind Dir", 9), ("Precip mm", 10),
        ]:
            dt.add_column(col, width=w)

    def refresh(self, state: weather.WeatherState) -> None:
        dt = self.query_one("#dt-weather", DataTable)
        dt.clear()
        for city, wx in sorted(state.cities.items()):
            dt.add_row(
                Text(city, style="bold"),
                Text(f"{wx.icon}  {wx.condition}", style="#c8d8e8"),
                Text(f"{wx.temp_c:.1f}", style="bold" if abs(wx.temp_c) >= 35 or wx.temp_c <= -10 else ""),
                Text(f"{wx.feels_like_c:.1f}", style="dim"),
                Text(f"{wx.temp_f:.1f}", style="dim"),
                Text(f"{wx.humidity:.0f}%", style="cyan" if wx.humidity > 80 else "dim"),
                Text(f"{wx.wind_speed_kph:.0f}", style="red" if wx.wind_speed_kph > 50 else "dim"),
                Text(wx.wind_direction_str, style="dim"),
                Text(f"{wx.precipitation_mm:.1f}", style="cyan" if wx.precipitation_mm > 0 else "dim"),
            )


# ── Earthquakes Tab ──────────────────────────────────────────────────────────

class EarthquakesTab(Container):
    def compose(self) -> ComposeResult:
        yield Static(id="eq-stats")
        yield SectionHeader("SIGNIFICANT EARTHQUAKES  (USGS — real-time)", id="eq-header")
        yield DataTable(id="dt-eq-sig", zebra_stripes=True, cursor_type="row")
        yield SectionHeader("LAST HOUR", id="eq-hour-header")
        yield DataTable(id="dt-eq-hour", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        for tid in ("dt-eq-sig", "dt-eq-hour"):
            dt = self.query_one(f"#{tid}", DataTable)
            for col, w in [
                ("Magnitude", 11), ("Location", 42), ("Depth km", 9),
                ("Lat", 8), ("Lon", 8), ("When", 10),
                ("Tsunami", 8), ("Alert", 8), ("Felt", 6),
            ]:
                dt.add_column(col, width=w)

    def refresh(self, state: earthquakes.EarthquakeState) -> None:
        stats = self.query_one("#eq-stats", Static)
        t = Text()
        t.append(f" Last hour: ", style="dim")
        t.append(str(state.hourly_count), style="bold #00aaff")
        t.append("  Today: ", style="dim")
        t.append(str(state.daily_count), style="bold")
        if state.largest_today:
            q = state.largest_today
            t.append(f"  Largest today: ", style="dim")
            t.append(q.magnitude_str, style=f"bold {q.severity_color}")
            t.append(f" — {q.place}", style="")
        stats.update(t)

        def fill_table(tid: str, quakes: list) -> None:
            dt = self.query_one(f"#{tid}", DataTable)
            dt.clear()
            for q in quakes:
                dt.add_row(
                    Text(q.magnitude_str, style=f"bold {q.severity_color}"),
                    Text(q.place[:40], style=""),
                    Text(f"{q.depth_km:.1f}", style="dim"),
                    Text(f"{q.lat:.2f}", style="dim"),
                    Text(f"{q.lon:.2f}", style="dim"),
                    Text(q.time_ago, style="dim"),
                    Text("⚠ YES" if q.tsunami else "No", style="red bold" if q.tsunami else "dim"),
                    Text(q.alert or "---", style=earthquakes.ALERT_COLORS.get(q.alert or "", "dim")),
                    Text(str(q.felt) if q.felt else "---", style="dim"),
                )

        fill_table("dt-eq-sig", state.significant[:30])
        fill_table("dt-eq-hour", state.recent[:30])


# ── News Tab ─────────────────────────────────────────────────────────────────

class NewsTab(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("NEWS FEED  (Reuters · BBC · AP · FT · WSJ · CNBC · MarketWatch)", id="news-header")
        yield Static(id="news-stats")
        yield RichLog(id="news-log", wrap=True, markup=True, highlight=False, auto_scroll=False)

    def refresh(self, state: news.NewsState) -> None:
        stats = self.query_one("#news-stats", Static)
        t = Text()
        t.append(f" Sources OK: ", style="dim")
        t.append(str(state.sources_ok), style="green")
        t.append("  Failed: ", style="dim")
        t.append(str(state.sources_fail), style="red" if state.sources_fail > 5 else "dim")
        t.append(f"  Articles: ", style="dim")
        t.append(str(len(state.articles)), style="#00aaff")
        t.append(f"  Updated: {datetime.utcfromtimestamp(state.updated).strftime('%H:%M:%S')} UTC", style="dim")
        stats.update(t)

        log = self.query_one("#news-log", RichLog)
        log.clear()

        # Group by category
        category_order = ["Top", "Markets", "Business", "Tech", "Space", "Aviation", "Shipping"]
        for cat in category_order:
            articles = state.by_category.get(cat, [])
            if not articles:
                continue
            log.write(Text(f"\n── {cat.upper()} ─{'─' * 50}", style="bold #00aaff"))
            for a in articles[:8]:
                t = Text()
                t.append(f"  [{a.time_ago:>3}]", style="dim")
                t.append(f" [{a.source}]", style="#446688")
                t.append(f" {a.title}", style="bold")
                log.write(t)
                if a.summary:
                    log.write(Text(f"        {a.summary[:120]}…", style="dim"))


# ── Parking Tab ──────────────────────────────────────────────────────────────

class ParkingTab(Container):
    def compose(self) -> ComposeResult:
        yield SectionHeader("URBAN PARKING  (NYC · SF · Chicago Open Data)", id="parking-header")
        yield Static(id="parking-stats")
        yield DataTable(id="dt-parking", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        dt = self.query_one("#dt-parking", DataTable)
        for col, w in [
            ("City", 16), ("Location", 36), ("Total", 7),
            ("Available", 10), ("Occupancy", 10), ("Status", 10),
            ("$/hr", 6), ("Limit min", 10),
        ]:
            dt.add_column(col, width=w)

    def refresh(self, state: parking.ParkingState) -> None:
        stats = self.query_one("#parking-stats", Static)
        t = Text()
        t.append(f" Zones: ", style="dim")
        t.append(str(len(state.zones)), style="#00aaff")
        t.append("  Total Spaces: ", style="dim")
        t.append(f"{state.total_spaces:,}", style="bold")
        t.append("  Cities: ", style="dim")
        t.append(", ".join(state.by_city.keys()) or "loading…", style="dim")
        stats.update(t)

        dt = self.query_one("#dt-parking", DataTable)
        dt.clear()
        for z in state.zones[:150]:
            occ_str = f"{z.occupancy_pct:.0f}%" if z.occupancy_pct is not None else "---"
            avail_str = str(z.available_spaces) if z.available_spaces is not None else "---"
            dt.add_row(
                Text(z.city, style="dim"),
                Text(z.location[:35] or z.zone_id, style="#c8d8e8"),
                Text(str(z.total_spaces), style="dim"),
                Text(avail_str, style="green" if (z.available_spaces or 0) > 0 else "dim"),
                Text(occ_str, style=z.status_color),
                Text(z.status, style=z.status_color),
                Text(f"{z.rate_per_hour:.2f}" if z.rate_per_hour else "---", style="dim"),
                Text(str(z.time_limit_min) if z.time_limit_min else "---", style="dim"),
            )


# ── Main App ─────────────────────────────────────────────────────────────────

class BloombergTerminal(App):
    CSS_PATH = "bloomberg.css"
    TITLE    = "Open Bloomberg Terminal"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_all", "Refresh"),
        Binding("1", "switch_tab('markets')",  "Markets"),
        Binding("2", "switch_tab('aircraft')", "Aircraft"),
        Binding("3", "switch_tab('ships')",    "Ships"),
        Binding("4", "switch_tab('space')",    "Space"),
        Binding("5", "switch_tab('weather')",  "Weather"),
        Binding("6", "switch_tab('quakes')",   "Earthquakes"),
        Binding("7", "switch_tab('news')",     "News"),
        Binding("8", "switch_tab('parking')",  "Parking"),
    ]

    _market_quotes: dict   = {}
    _crypto_ticks: dict    = {}
    _ticker_text: str      = ""

    def compose(self) -> ComposeResult:
        yield TickerBar(id="ticker-bar")
        with Horizontal(id="header"):
            yield Static(
                Text("◆ OPEN BLOOMBERG TERMINAL", style="bold #00aaff") +
                Text("  ·  ", style="dim") +
                Text("Free · Open Source · No API Keys", style="#446688"),
                id="header-left"
            )
            yield Static(id="clock", classes="neutral")

        with TabbedContent(initial="markets", id="main-tabs"):
            with TabPane("◈ Markets",    id="markets"):
                yield MarketTab(id="market-panel")
            with TabPane("✈ Aircraft",   id="aircraft"):
                yield AircraftTab(id="aircraft-panel")
            with TabPane("⚓ Ships",     id="ships"):
                yield ShipsTab(id="ships-panel")
            with TabPane("🛰 Space",     id="space"):
                yield SpaceTab(id="space-panel")
            with TabPane("🌦 Weather",   id="weather"):
                yield WeatherTab(id="weather-panel")
            with TabPane("🌍 Quakes",    id="quakes"):
                yield EarthquakesTab(id="quakes-panel")
            with TabPane("📰 News",      id="news"):
                yield NewsTab(id="news-panel")
            with TabPane("🅿 Parking",   id="parking"):
                yield ParkingTab(id="parking-panel")

        yield Static(
            " Q: quit  |  R: refresh  |  1-8: switch panel  |  Tab: next panel",
            id="status-bar"
        )

    # ── lifecycle ────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        # Clock
        self.set_interval(1, self._update_clock)
        # UI repaint
        self.set_interval(REFRESH_UI, self._repaint_ui)

        # Background data pollers
        self._start_feeds()

    def _start_feeds(self) -> None:
        self._run_market_poller()
        self._run_crypto_stream()
        self._run_aircraft_poller()
        self._run_ships_poller()
        self._run_space_poller()
        self._run_weather_poller()
        self._run_earthquake_poller()
        self._run_news_poller()
        self._run_parking_poller()

    # ── workers ──────────────────────────────────────────────────────────────

    @work(exclusive=False, thread=False)
    async def _run_market_poller(self) -> None:
        await market.run_poller_async(self._on_market_update, REFRESH_MARKET)

    @work(exclusive=False, thread=False)
    async def _run_crypto_stream(self) -> None:
        await crypto.run_stream(self._on_crypto_update)

    @work(exclusive=False, thread=False)
    async def _run_aircraft_poller(self) -> None:
        await aircraft.run_poller(REFRESH_AIRCRAFT)

    @work(exclusive=False, thread=False)
    async def _run_ships_poller(self) -> None:
        await ships.run_poller(REFRESH_SHIPS)

    @work(exclusive=False, thread=False)
    async def _run_space_poller(self) -> None:
        await space.run_poller(REFRESH_SPACE)

    @work(exclusive=False, thread=False)
    async def _run_weather_poller(self) -> None:
        await weather.run_poller(REFRESH_WEATHER)

    @work(exclusive=False, thread=False)
    async def _run_earthquake_poller(self) -> None:
        await earthquakes.run_poller(REFRESH_EQ)

    @work(exclusive=False, thread=False)
    async def _run_news_poller(self) -> None:
        await news.run_poller(REFRESH_NEWS)

    @work(exclusive=False, thread=False)
    async def _run_parking_poller(self) -> None:
        await parking.run_poller(REFRESH_PARKING)

    # ── callbacks from data feeds ────────────────────────────────────────────

    def _on_market_update(self, quotes: dict) -> None:
        self._market_quotes = quotes
        self._rebuild_ticker()

    def _on_crypto_update(self, ticks: dict) -> None:
        self._crypto_ticks = ticks
        self._rebuild_ticker()

    def _rebuild_ticker(self) -> None:
        parts = []
        key_tickers = ["^GSPC", "^DJI", "^IXIC", "^VIX", "GC=F", "CL=F"]
        for t in key_tickers:
            q = self._market_quotes.get(t)
            if q:
                arrow = "▲" if q.change >= 0 else "▼"
                parts.append(f"{q.name}: {fmt_price(q.price)} {arrow}{abs(q.change_pct):.2f}%")

        for sym, tick in list(self._crypto_ticks.items())[:4]:
            arrow = "▲" if tick.change_pct_24h >= 0 else "▼"
            parts.append(f"{tick.name}: ${tick.price:,.0f} {arrow}{abs(tick.change_pct_24h):.1f}%")

        self._ticker_text = "   ·   ".join(parts)
        try:
            ticker = self.query_one("#ticker-bar", TickerBar)
            ticker.update_content("  " + self._ticker_text + "     ")
        except Exception:
            pass

    # ── UI refresh ───────────────────────────────────────────────────────────

    def _update_clock(self) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        try:
            self.query_one("#clock", Static).update(
                Text(f" {now} ", style="#88aacc")
            )
        except Exception:
            pass

    def _repaint_ui(self) -> None:
        """Refresh whichever tab is currently visible."""
        try:
            tabs = self.query_one("#main-tabs", TabbedContent)
            active = tabs.active
        except Exception:
            return

        try:
            if active == "markets":
                panel = self.query_one("#market-panel", MarketTab)
                if self._market_quotes:
                    panel.refresh_market(self._market_quotes)
                if self._crypto_ticks:
                    panel.refresh_crypto(self._crypto_ticks)
            elif active == "aircraft":
                self.query_one("#aircraft-panel", AircraftTab).refresh(aircraft.get_aircraft())
            elif active == "ships":
                self.query_one("#ships-panel", ShipsTab).refresh(ships.get_ships())
            elif active == "space":
                self.query_one("#space-panel", SpaceTab).refresh(space.get_space())
            elif active == "weather":
                self.query_one("#weather-panel", WeatherTab).refresh(weather.get_weather())
            elif active == "quakes":
                self.query_one("#quakes-panel", EarthquakesTab).refresh(earthquakes.get_earthquakes())
            elif active == "news":
                self.query_one("#news-panel", NewsTab).refresh(news.get_news())
            elif active == "parking":
                self.query_one("#parking-panel", ParkingTab).refresh(parking.get_parking())
        except Exception:
            pass

    # ── actions ──────────────────────────────────────────────────────────────

    def action_refresh_all(self) -> None:
        self._run_market_poller()
        self._run_aircraft_poller()
        self.notify("Refresh triggered", title="Open Bloomberg")

    def action_switch_tab(self, tab_id: str) -> None:
        try:
            self.query_one("#main-tabs", TabbedContent).active = tab_id
        except Exception:
            pass


# ── market async helper ──────────────────────────────────────────────────────

async def _market_poll_loop(callback, interval: int):
    while True:
        quotes = await market.fetch_quotes(market.ALL_TICKERS)
        if quotes and callback:
            callback(quotes)
        await asyncio.sleep(interval)


# Monkey-patch a run_poller_async onto the market module
market.run_poller_async = _market_poll_loop


if __name__ == "__main__":
    app = BloombergTerminal()
    app.run()
