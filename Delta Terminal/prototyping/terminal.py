#!/usr/bin/env python3
"""
Open Bloomberg Terminal - TUI Application
Professional terminal UI using Textual framework
"""

import asyncio
import yfinance as yf
import feedparser
import aiohttp
from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel
from rich.table import Table


class MarketsTab(Static):
    """Markets data tab."""
    
    def __init__(self):
        super().__init__()
        self.data = {}
        self.update_in_progress = False
    
    async def on_mount(self):
        """Mount the widget."""
        await self.update_data()
        self.set_interval(5, self.update_data)
    
    async def update_data(self):
        """Fetch market data."""
        if self.update_in_progress:
            return
        
        self.update_in_progress = True
        try:
            tickers = ['^GSPC', '^DJI', '^IXIC', '^VIX', 'SPY', 'QQQ', 
                      'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA', 'AMZN']
            
            for ticker in tickers:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    current = info.get('currentPrice', 0)
                    prev_close = info.get('previousClose', current)
                    change = current - prev_close
                    change_pct = (change / prev_close * 100) if prev_close else 0
                    
                    self.data[ticker] = {
                        'symbol': ticker,
                        'name': info.get('longName', ticker)[:20],
                        'price': current,
                        'change': change,
                        'change_pct': change_pct,
                        'volume': info.get('volume', 0),
                    }
                except:
                    pass
        except:
            pass
        finally:
            self.update_in_progress = False
            self.refresh()
    
    def render(self):
        """Render markets."""
        if not self.data:
            return Panel("Loading market data...", title="MARKETS")
        
        table = Table(title="MARKETS", show_header=True, header_style="bold cyan")
        table.add_column("Symbol", style="cyan", width=10)
        table.add_column("Name", width=20)
        table.add_column("Price", justify="right", width=12)
        table.add_column("Change", justify="right", width=15)
        table.add_column("Volume", justify="right", width=12)
        
        for ticker in sorted(self.data.keys())[:12]:
            quote = self.data[ticker]
            change_color = "green" if quote['change_pct'] >= 0 else "red"
            arrow = "▲" if quote['change_pct'] >= 0 else "▼"
            change_text = f"{arrow} {quote['change']:.2f} ({quote['change_pct']:.1f}%)"
            
            table.add_row(
                quote['symbol'],
                quote['name'],
                f"${quote['price']:.2f}" if quote['price'] > 0 else "—",
                Text(change_text, style=change_color),
                f"{quote['volume']/1e6:.1f}M" if quote['volume'] > 0 else "—"
            )
        
        return Panel(table, expand=True)


class CryptoTab(Static):
    """Cryptocurrency data tab."""
    
    def __init__(self):
        super().__init__()
        self.data = {}
    
    async def on_mount(self):
        """Mount the widget."""
        await self.update_data()
        self.set_interval(5, self.update_data)
    
    async def update_data(self):
        """Fetch crypto data."""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {
                    'ids': 'bitcoin,ethereum,ripple,cardano,solana,dogecoin',
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true',
                    'include_market_cap': 'true'
                }
                
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        coins = {
                            'bitcoin': ('Bitcoin', 'BTC'),
                            'ethereum': ('Ethereum', 'ETH'),
                            'ripple': ('Ripple', 'XRP'),
                            'cardano': ('Cardano', 'ADA'),
                            'solana': ('Solana', 'SOL'),
                            'dogecoin': ('Dogecoin', 'DOGE')
                        }
                        
                        self.data = {}
                        for coin_id, (name, symbol) in coins.items():
                            if coin_id in data:
                                coin_data = data[coin_id]
                                self.data[symbol] = {
                                    'symbol': symbol,
                                    'name': name,
                                    'price': coin_data.get('usd', 0),
                                    'change_24h': coin_data.get('usd_24h_change', 0),
                                    'market_cap': coin_data.get('usd_market_cap', 0)
                                }
                        self.refresh()
        except:
            pass
    
    def render(self):
        """Render crypto."""
        if not self.data:
            return Panel("Loading crypto data...", title="CRYPTO")
        
        table = Table(title="CRYPTOCURRENCY (Real-time)", show_header=True, header_style="bold cyan")
        table.add_column("Coin", style="cyan", width=20)
        table.add_column("Price $", justify="right", width=15)
        table.add_column("24h Change", justify="right", width=15)
        table.add_column("Market Cap", justify="right", width=15)
        
        for symbol in sorted(self.data.keys()):
            crypto = self.data[symbol]
            change = crypto['change_24h']
            change_color = "green" if change >= 0 else "red"
            arrow = "▲" if change >= 0 else "▼"
            change_text = f"{arrow} {change:.1f}%"
            
            table.add_row(
                f"{crypto['name']} ({symbol})",
                f"${crypto['price']:,.2f}",
                Text(change_text, style=change_color),
                f"${crypto['market_cap']/1e9:.1f}B" if crypto['market_cap'] > 0 else "—"
            )
        
        return Panel(table, expand=True)


class AircraftTab(Static):
    """Aircraft tracking tab."""
    
    def __init__(self):
        super().__init__()
        self.aircraft = []
    
    async def on_mount(self):
        """Mount the widget."""
        await self.update_data()
        self.set_interval(15, self.update_data)
    
    async def update_data(self):
        """Fetch aircraft data from OpenSky Network."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://opensky-network.org/api/states/all", 
                                      timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        self.aircraft = []
                        if data.get('states'):
                            for state in data['states'][:50]:
                                if state[6] and not state[8]:
                                    self.aircraft.append({
                                        'callsign': (state[1] or 'N/A').strip(),
                                        'country': state[2] or 'Unknown',
                                        'altitude': int(state[7] * 3.28084) if state[7] else 0,
                                        'speed': int(state[9] * 1.94384) if state[9] else 0,
                                        'heading': state[10] or 0
                                    })
                        
                        self.aircraft.sort(key=lambda x: x['altitude'], reverse=True)
                        self.refresh()
        except:
            pass
    
    def render(self):
        """Render aircraft."""
        if not self.aircraft:
            return Panel("Loading aircraft data...", title="AIRCRAFT")
        
        table = Table(title=f"AIRCRAFT ({len(self.aircraft)} airborne)", show_header=True, header_style="bold cyan")
        table.add_column("Callsign", style="cyan", width=12)
        table.add_column("Country", width=12)
        table.add_column("Altitude ft", justify="right", width=14)
        table.add_column("Speed kts", justify="right", width=12)
        
        for plane in self.aircraft[:25]:
            table.add_row(
                plane['callsign'],
                plane['country'],
                f"{plane['altitude']:,}",
                str(plane['speed'])
            )
        
        return Panel(table, expand=True)


class EarthquakesTab(Static):
    """Earthquakes data tab."""
    
    def __init__(self):
        super().__init__()
        self.quakes = []
    
    async def on_mount(self):
        """Mount the widget."""
        await self.update_data()
        self.set_interval(60, self.update_data)
    
    async def update_data(self):
        """Fetch earthquake data from USGS."""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        self.quakes = []
                        for feature in data.get('features', [])[:20]:
                            props = feature['properties']
                            coords = feature['geometry']['coordinates']
                            mag = props.get('mag', 0)
                            
                            self.quakes.append({
                                'magnitude': mag,
                                'place': props.get('place', 'Unknown')[:40],
                                'depth': coords[2],
                                'lat': coords[1],
                                'lon': coords[0]
                            })
                        
                        self.quakes.sort(key=lambda x: x['magnitude'], reverse=True)
                        self.refresh()
        except:
            pass
    
    def render(self):
        """Render earthquakes."""
        if not self.quakes:
            return Panel("Loading earthquake data...", title="EARTHQUAKES")
        
        table = Table(title="EARTHQUAKES (Last Hour)", show_header=True, header_style="bold cyan")
        table.add_column("Magnitude", style="cyan", width=12)
        table.add_column("Location", width=30)
        table.add_column("Depth km", justify="right", width=10)
        
        for quake in self.quakes[:20]:
            mag_color = "red" if quake['magnitude'] >= 6 else "yellow" if quake['magnitude'] >= 5 else "cyan"
            table.add_row(
                Text(f"M{quake['magnitude']:.1f}", style=mag_color),
                quake['place'],
                f"{quake['depth']:.1f}"
            )
        
        return Panel(table, expand=True)


class NewsTab(Static):
    """News feed tab."""
    
    def __init__(self):
        super().__init__()
        self.articles = []
    
    async def on_mount(self):
        """Mount the widget."""
        await self.update_data()
        self.set_interval(120, self.update_data)
    
    async def update_data(self):
        """Fetch news from RSS feeds."""
        try:
            feeds = [
                'http://feeds.bbci.co.uk/news/rss.xml',
                'http://feeds.cnbc.com/id/100003114/device/rss/rss.html'
            ]
            
            self.articles = []
            for feed_url in feeds:
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:5]:
                        self.articles.append({
                            'title': entry.get('title', 'No title')[:60],
                            'source': feed.feed.get('title', 'Unknown')[:20],
                        })
                except:
                    pass
            
            self.refresh()
        except:
            pass
    
    def render(self):
        """Render news."""
        if not self.articles:
            return Panel("Loading news...", title="NEWS")
        
        table = Table(title="NEWS FEED", show_header=True, header_style="bold cyan")
        table.add_column("Source", style="cyan", width=15)
        table.add_column("Headline", width=60)
        
        for article in self.articles[:20]:
            table.add_row(
                article['source'],
                article['title']
            )
        
        return Panel(table, expand=True)


class TerminalApp(ComposeResult):
    """Main Bloomberg Terminal app."""
    
    BINDINGS = [Binding("q", "quit", "Quit")]
    
    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header(show_clock=True)
        
        with TabbedContent():
            with TabPane("Markets", id="markets"):
                yield MarketsTab()
            with TabPane("Crypto", id="crypto"):
                yield CryptoTab()
            with TabPane("Aircraft", id="aircraft"):
                yield AircraftTab()
            with TabPane("Earthquakes", id="earthquakes"):
                yield EarthquakesTab()
            with TabPane("News", id="news"):
                yield NewsTab()
        
        yield Footer()


if __name__ == "__main__":
    from textual.app import App
    
    class BloombergApp(App):
        TITLE = "Open Bloomberg Terminal"
        
        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            
            with TabbedContent():
                with TabPane("Markets", id="markets"):
                    yield MarketsTab()
                with TabPane("Crypto", id="crypto"):
                    yield CryptoTab()
                with TabPane("Aircraft", id="aircraft"):
                    yield AircraftTab()
                with TabPane("Earthquakes", id="earthquakes"):
                    yield EarthquakesTab()
                with TabPane("News", id="news"):
                    yield NewsTab()
            
            yield Footer()
        
        BINDINGS = [Binding("q", "quit", "Quit")]
    
    app = BloombergApp()
    app.run()
