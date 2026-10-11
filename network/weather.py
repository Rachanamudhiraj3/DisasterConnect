"""
Optional online enrichment. Only called when is_online() is True.
Uses Open-Meteo, which needs no API key.

Always fails SAFE: any network problem returns None rather than raising,
so the caller can just fall back to offline-only logic without special
error handling at every call site.
"""

import requests


def fetch_weather_context(lat: float, lon: float) -> dict | None:
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,rain,precipitation,surface_pressure,wind_speed_10m",
            },
            timeout=3,
        )
        resp.raise_for_status()
        data = resp.json().get("current", {})
        weather_code = data.get("weather_code")
        conditions = {
            0: ("Clear sky", "clear"), 1: ("Mostly clear", "clear"),
            2: ("Partly cloudy", "cloud"), 3: ("Overcast", "cloud"),
            45: ("Fog", "fog"), 48: ("Rime fog", "fog"),
            51: ("Light drizzle", "rain"), 53: ("Drizzle", "rain"),
            55: ("Heavy drizzle", "rain"), 61: ("Light rain", "rain"),
            63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
            71: ("Light snow", "snow"), 73: ("Snow", "snow"),
            75: ("Heavy snow", "snow"), 80: ("Rain showers", "rain"),
            81: ("Rain showers", "rain"), 82: ("Heavy showers", "storm"),
            95: ("Thunderstorm", "storm"), 96: ("Thunderstorm with hail", "storm"),
            99: ("Thunderstorm with hail", "storm"),
        }
        condition, icon = conditions.get(weather_code, ("Current conditions", "cloud"))
        return {
            "external_precipitation_mm": data.get("precipitation"),
            "external_pressure_hpa": data.get("surface_pressure"),
            "temp_c": data.get("temperature_2m"),
            "rain_mm": data.get("rain"),
            "precip_mm": data.get("precipitation"),
            "condition": condition,
            "icon": icon,
            "weather_code": weather_code,
            "wind_speed_kmh": data.get("wind_speed_10m"),
        }
    except (requests.ConnectionError, requests.Timeout, requests.HTTPError, ValueError):
        return None
