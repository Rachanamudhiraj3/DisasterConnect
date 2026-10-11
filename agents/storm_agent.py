"""Storm and thunderstorm risk agent.

Uses local wind/rain sensors offline and Open-Meteo weather codes online.
The online feed confirms a storm but never replaces local detection.
"""

from config.settings import STORM_RAIN_RATE_MM_HR, STORM_WIND_SPEED_KMH

_THUNDERSTORM_CODES = {95, 96, 99}


def check_storm_risk(sensors: dict, weather_context: dict | None) -> dict:
    wind_speed = sensors.get("wind_speed_kmh", 0.0)
    rain_rate = sensors.get("rain_rate_mm_hr", 0.0)
    weather_code = weather_context.get("weather_code") if weather_context else None

    if weather_code in _THUNDERSTORM_CODES:
        return {
            "risk": "high",
            "hazard": "thunderstorm",
            "reason": "official weather feed reports a thunderstorm at this location",
        }
    if wind_speed >= STORM_WIND_SPEED_KMH:
        return {
            "risk": "high",
            "hazard": "storm",
            "reason": f"wind speed {wind_speed:.1f} km/h exceeds trigger ({STORM_WIND_SPEED_KMH} km/h)",
        }
    if rain_rate >= STORM_RAIN_RATE_MM_HR:
        return {
            "risk": "high",
            "hazard": "storm",
            "reason": f"extreme rainfall {rain_rate:.1f} mm/hr exceeds storm trigger ({STORM_RAIN_RATE_MM_HR} mm/hr)",
        }
    return {
        "risk": "low",
        "hazard": "storm",
        "reason": f"wind {wind_speed:.1f} km/h and rain {rain_rate:.1f} mm/hr are below storm triggers",
    }
