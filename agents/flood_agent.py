"""
Flood risk agent.

Rule-based on purpose: instant, explainable, and works with zero
internet. The online weather cross-check is an optional extra signal,
never a requirement.
"""

from config.settings import FLOOD_WATER_LEVEL_CM, FLOOD_RAIN_RATE_MM_HR


def check_flood_risk(sensors: dict, weather_context: dict | None) -> dict:
    reasons = []
    risk = "low"

    if sensors["water_level_cm"] < FLOOD_WATER_LEVEL_CM:
        reasons.append(f"water level high ({sensors['water_level_cm']}cm from sensor)")
        risk = "high"

    if sensors["rain_rate_mm_hr"] > FLOOD_RAIN_RATE_MM_HR:
        reasons.append(f"heavy rain ({sensors['rain_rate_mm_hr']}mm/hr)")
        risk = "high"

    if weather_context and (weather_context.get("external_precipitation_mm") or 0) > 10:
        reasons.append("external forecast also shows heavy precipitation")
        risk = "high"

    if not reasons:
        reasons.append("readings within normal range")

    return {"risk": risk, "reason": "; ".join(reasons)}
