"""Tsunami risk agent.

This is intentionally conservative. A tsunami alert needs a coastal tide gauge
or equivalent sea-level sensor; a river/pond water-level reading is not valid
evidence. The agent only raises risk for a rapid sea-level change.
"""

from config.settings import TSUNAMI_SEA_LEVEL_CHANGE_CM


def check_tsunami_risk(sensors: dict) -> dict:
    sea_level_change = abs(sensors.get("sea_level_change_cm", 0.0))
    if sea_level_change >= TSUNAMI_SEA_LEVEL_CHANGE_CM:
        return {
            "risk": "high",
            "reason": (
                f"rapid coastal sea-level change {sea_level_change:.1f} cm exceeds "
                f"trigger ({TSUNAMI_SEA_LEVEL_CHANGE_CM} cm)"
            ),
        }
    return {
        "risk": "low",
        "reason": "no rapid coastal sea-level change detected by the tide gauge",
    }
