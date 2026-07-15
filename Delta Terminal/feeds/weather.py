"""
Global weather via Open-Meteo — completely free, no API key required.
Also fetches active wildfires from NASA FIRMS (no key for public data).
"""

import asyncio
import time
import aiohttp
from dataclasses import dataclass, field
from typing import Optional

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Major world cities
CITIES = {
    "New York":      (40.7128,  -74.0060),
    "London":        (51.5074,   -0.1278),
    "Tokyo":         (35.6762,  139.6503),
    "Shanghai":      (31.2304,  121.4737),
    "Sydney":       (-33.8688,  151.2093),
    "Dubai":         (25.2048,   55.2708),
    "Singapore":      (1.3521,  103.8198),
    "Frankfurt":     (50.1109,    8.6821),
    "Los Angeles":   (34.0522, -118.2437),
    "Chicago":       (41.8781,  -87.6298),
    "São Paulo":    (-23.5505,  -46.6333),
    "Mumbai":        (19.0760,   72.8777),
    "Hong Kong":     (22.3193,  114.1694),
    "Paris":         (48.8566,    2.3522),
    "Moscow":        (55.7558,   37.6173),
}

WMO_CODES = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Showers", 82: "Violent showers",
    85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Thunderstorm w/ heavy hail",
}

WMO_ICONS = {
    0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
    45: "🌫", 48: "🌫",
    51: "🌦", 53: "🌧", 55: "🌧",
    61: "🌦", 63: "🌧", 65: "⛈",
    71: "🌨", 73: "❄️", 75: "❄️",
    80: "🌦", 81: "🌧", 82: "⛈",
    95: "⛈", 96: "⛈", 99: "⛈",
}


@dataclass
class CityWeather:
    city: str
    lat: float
    lon: float
    temp_c: float
    feels_like_c: float
    humidity: float
    wind_speed_kph: float
    wind_dir: float
    precipitation_mm: float
    weather_code: int
    is_day: bool
    updated: float = field(default_factory=time.time)

    @property
    def temp_f(self) -> float:
        return self.temp_c * 9 / 5 + 32

    @property
    def condition(self) -> str:
        return WMO_CODES.get(self.weather_code, "Unknown")

    @property
    def icon(self) -> str:
        return WMO_ICONS.get(self.weather_code, "?")

    @property
    def wind_direction_str(self) -> str:
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        return dirs[round(self.wind_dir / 45) % 8]


@dataclass
class WeatherState:
    cities: dict[str, CityWeather] = field(default_factory=dict)
    updated: float = field(default_factory=time.time)
    error: Optional[str] = None


_state = WeatherState()


def get_weather() -> WeatherState:
    return _state


async def _fetch_city(session: aiohttp.ClientSession, city: str, lat: float, lon: float) -> Optional[CityWeather]:
    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                   "precipitation,weather_code,wind_speed_10m,wind_direction_10m,"
                   "is_day",
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
    }
    try:
        async with session.get(OPEN_METEO_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            d = await r.json()
            cur = d["current"]
            return CityWeather(
                city=city, lat=lat, lon=lon,
                temp_c=cur["temperature_2m"],
                feels_like_c=cur["apparent_temperature"],
                humidity=cur["relative_humidity_2m"],
                wind_speed_kph=cur["wind_speed_10m"],
                wind_dir=cur["wind_direction_10m"],
                precipitation_mm=cur["precipitation"],
                weather_code=cur["weather_code"],
                is_day=bool(cur["is_day"]),
            )
    except Exception:
        return None


async def run_poller(interval: int = 300):
    global _state
    async with aiohttp.ClientSession() as session:
        while True:
            cities = {}
            tasks = [_fetch_city(session, city, lat, lon) for city, (lat, lon) in CITIES.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for city, result in zip(CITIES.keys(), results):
                if isinstance(result, CityWeather):
                    cities[city] = result
            _state = WeatherState(cities=cities, updated=time.time())
            await asyncio.sleep(interval)
