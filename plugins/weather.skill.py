"""
Skill: Weather
==============
Provides current weather conditions and a 3-day forecast using OpenWeatherMap.

Requires environment variable OPENWEATHERMAP_API_KEY with a free-tier key
from https://openweathermap.org/api.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

WEATHER_API = "https://api.openweathermap.org/data/2.5"
GEO_API = "https://api.openweathermap.org/geo/1.0"
THERMO_API = "http://ip-api.com/json"  # fallback geolocation via IP

# OpenWeatherMap condition codes grouped into human-readable categories
_COND_MAP = {
    (200, 233): "Thunderstorm",
    (300, 321): "Drizzle",
    (500, 531): "Rain",
    (600, 622): "Snow",
    (701, 781): "Atmospheric (fog/haze)",
    (800, 800): "Clear",
    (801, 804): "Clouds",
}


def _code_to_condition(code: int) -> str:
    for (lo, hi), label in _COND_MAP.items():
        if lo <= code <= hi:
            return label
    return "Unknown"


def _api_key(context: SkillContext) -> str | None:
    return (
        os.getenv("OPENWEATHERMAP_API_KEY")
        or context.parameters.get("api_key")
    )


async def _geocode_city(
    client: httpx.AsyncClient, city: str, key: str
) -> tuple[float, float] | None:
    resp = await client.get(
        f"{GEO_API}/direct", params={"q": city, "limit": 1, "appid": key}
    )
    if resp.status_code == 200 and resp.json():
        data = resp.json()[0]
        return data["lat"], data["lon"]
    return None


async def _geocode_ip(client: httpx.AsyncClient) -> tuple[float, float] | None:
    resp = await client.get(THERMO_API)
    if resp.status_code == 200:
        data = resp.json()
        return data["lat"], data["lon"]
    return None


async def _fetch_weather(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    key: str,
    units: str = "metric",
) -> dict:
    resp = await client.get(
        f"{WEATHER_API}/weather",
        params={"lat": lat, "lon": lon, "appid": key, "units": units},
    )
    resp.raise_for_status()
    return resp.json()


async def _fetch_forecast(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    key: str,
    units: str = "metric",
) -> list[dict]:
    resp = await client.get(
        f"{WEATHER_API}/forecast",
        params={"lat": lat, "lon": lon, "appid": key, "units": units},
    )
    resp.raise_for_status()
    data = resp.json()
    # forecast endpoint returns 3-hour intervals; pick one per calendar day
    by_date: dict[str, dict] = {}
    for item in data.get("list", []):
        dt = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        date_key = dt.strftime("%Y-%m-%d")
        if date_key not in by_date:
            by_date[date_key] = item
    # skip today, return next 3 days
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    days = [v for k, v in by_date.items() if k != today]
    return days[:3]


def _format_current(weather: dict, units: str) -> str:
    temp = weather["main"]
    wind = weather["wind"]
    cond = weather["weather"][0]
    symbol = "°C" if units == "metric" else "°F"
    return (
        f"{cond['main']} ({cond['description']})\n"
        f"Temperature: {temp['temp']}{symbol}  "
        f"(feels like {temp['feels_like']}{symbol})\n"
        f"Humidity: {temp['humidity']}%\n"
        f"Wind: {wind['speed']} {'m/s' if units == 'metric' else 'mph'}"
    )


def _format_forecast(days: list[dict], units: str) -> str:
    if not days:
        return "No forecast data available."
    symbol = "°C" if units == "metric" else "°F"
    lines = []
    for d in days:
        dt = datetime.fromtimestamp(d["dt"], tz=timezone.utc)
        cond = d["weather"][0]
        temp = d["main"]
        lines.append(
            f"{dt.strftime('%a %d %b')}: {cond['main']} "
            f"{temp['temp_min']}{symbol}–{temp['temp_max']}{symbol}"
        )
    return "Forecast:\n" + "\n".join(lines)


class WeatherSkill(BaseSkill):
    """Provides current weather and a 3-day forecast.

    Example:
        User: "What's the weather in London?"
        JARVIS: "Overcast Clouds (overcast clouds) ..."
    """

    metadata = SkillMetadata(
        name="weather",
        version="1.0.0",
        description="Current weather and 3-day forecast via OpenWeatherMap",
        author="JARVIS Team",
        tags=["weather", "forecast"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        key = _api_key(context)
        if not key:
            return SkillResult(
                success=False,
                error=(
                    "OPENWEATHERMAP_API_KEY not set. "
                    "Add it to your environment or pass api_key in parameters."
                ),
            )

        city = context.parameters.get("city", "").strip()
        units = context.parameters.get("units", "metric")

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Resolve coordinates
            coords = None
            if city:
                coords = await _geocode_city(client, city, key)
            if coords is None:
                coords = await _geocode_ip(client)
            if coords is None:
                return SkillResult(
                    success=False,
                    error="Could not determine location. Provide a city name.",
                )

            lat, lon = coords
            try:
                current = await _fetch_weather(client, lat, lon, key, units)
            except httpx.HTTPStatusError as exc:
                return SkillResult(
                    success=False, error=f"Weather API error: {exc.response.status_code}",
                )

            forecast = await _fetch_forecast(client, lat, lon, key, units)

        location_label = current.get("name") or city or "your location"
        summary = (
            f"Weather for {location_label}:\n"
            f"{_format_current(current, units)}\n\n"
            f"{_format_forecast(forecast, units)}"
        )

        return SkillResult(
            success=True,
            output=summary,
            metadata={
                "location": location_label,
                "lat": lat,
                "lon": lon,
                "units": units,
            },
        )
