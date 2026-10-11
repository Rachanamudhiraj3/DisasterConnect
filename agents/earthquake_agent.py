"""
Earthquake risk agent.

Uses STA/LTA (Short-Term Average vs Long-Term Average) -- the standard
seismology technique for detecting a sudden vibration spike against a
noisy baseline. No ML model needed, runs instantly, fully offline.
"""

from collections import deque

from config.settings import EARTHQUAKE_STA_LTA_RATIO

# Rolling vibration history, kept at module level so it persists across
# calls within one running process (one field unit == one history).
_vibration_history = deque(maxlen=200)   # long-term window
_STA_WINDOW = 5                          # short-term window


def _sta_lta_ratio(new_value: float) -> float:
    _vibration_history.append(new_value)
    if len(_vibration_history) < _STA_WINDOW + 1:
        return 0.0
    lta = sum(_vibration_history) / len(_vibration_history)
    sta = sum(list(_vibration_history)[-_STA_WINDOW:]) / _STA_WINDOW
    if lta <= 1e-6:
        return 0.0
    return sta / lta


def check_earthquake_risk(sensors: dict, historical_event: dict | None = None) -> dict:
    """Check local vibration, or a date-specific event supplied by the simulator."""
    if historical_event:
        magnitude = historical_event["magnitude"]
        return {
            "risk": "high",
            "reason": (
                f"Historical earthquake detected: M{magnitude:.1f} — "
                f"{historical_event['place']} ({historical_event['source']})"
            ),
        }

    ratio = _sta_lta_ratio(sensors["vibration_g"])

    if ratio >= EARTHQUAKE_STA_LTA_RATIO:
        return {"risk": "high", "reason": f"STA/LTA ratio {ratio:.2f} exceeds trigger ({EARTHQUAKE_STA_LTA_RATIO})"}
    return {"risk": "low", "reason": f"STA/LTA ratio {ratio:.2f}, within normal range"}


_ISOLATED_BASELINE_VALUE = 0.01   # typical "quiet" reading, see sensors/reader.py
_ISOLATED_BASELINE_LENGTH = 20


def check_earthquake_risk_isolated(vibration_g: float) -> dict:
    """
    Same STA/LTA math as check_earthquake_risk, but scored against a
    synthetic quiet baseline instead of this process's shared rolling
    history. check_earthquake_risk is deliberately relative to whatever
    this unit has actually felt recently -- right for continuous live
    monitoring, wrong for a "what if this reading came in" test, where
    the same input should always give the same verdict regardless of
    what other tests ran earlier in this session.
    """
    baseline = [_ISOLATED_BASELINE_VALUE] * (_ISOLATED_BASELINE_LENGTH - 1) + [vibration_g]
    lta = sum(baseline) / len(baseline)
    sta = sum(baseline[-_STA_WINDOW:]) / _STA_WINDOW
    ratio = sta / lta if lta > 1e-6 else 0.0

    if ratio >= EARTHQUAKE_STA_LTA_RATIO:
        return {"risk": "high", "reason": f"STA/LTA ratio {ratio:.2f} exceeds trigger ({EARTHQUAKE_STA_LTA_RATIO}) against a quiet baseline"}
    return {"risk": "low", "reason": f"STA/LTA ratio {ratio:.2f} against a quiet baseline, within normal range"}
