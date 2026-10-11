"""
Emergency alert dispatcher.

Responsibilities:
- Build a structured disaster alert
- Trigger local buzzer
- Send SMS through GSM
- Send browser/app notification
- Store alert history
- Prevent repeated SMS/buzzer spam for the same ongoing event
"""

from datetime import datetime, timezone

from config.settings import USE_REAL_HARDWARE
from database.db import save_alert, recent_similar_alert


# ---------------------------------------------------------
# Alert configuration
# ---------------------------------------------------------

ALERT_COOLDOWN_MINUTES = 10


def get_recommended_action(hazard: str) -> str:
    """Return simple, actionable safety guidance."""

    hazard = (hazard or "").lower()

    actions = {
        "flood": (
            "Avoid flooded and low-lying roads. "
            "Do not walk or drive through moving water. "
            "Move toward a safe shelter if conditions worsen."
        ),

        "storm": (
            "Stay indoors if possible. "
            "Avoid open areas, trees and damaged electrical lines. "
            "Avoid low-lying or flooded roads."
        ),

        "thunderstorm": (
            "Stay indoors and avoid open areas. "
            "Keep away from trees, poles and exposed electrical equipment."
        ),

        "earthquake": (
            "Move away from windows and unstable structures. "
            "Drop, cover and hold until the shaking stops. "
            "Follow local emergency instructions."
        ),

        "tsunami": (
            "Move immediately toward higher ground and away from the coast. "
            "Do not return until authorities confirm it is safe."
        ),
    }

    return actions.get(
        hazard,
        "Move to a safe location and follow local emergency instructions."
    )


def get_alert_title(hazard: str) -> str:
    hazard = (hazard or "disaster").replace("_", " ").title()
    return f"{hazard} Emergency Alert"


def get_alert_priority(risk: str) -> str:
    """
    Current agent architecture produces low/high.
    Keep the same risk decision and convert it into a
    user-friendly priority label.
    """

    risk = (risk or "").lower()

    if risk == "high":
        return "HIGH"

    if risk == "medium":
        return "MEDIUM"

    return "INFO"


# ---------------------------------------------------------
# Hardware / notification channels
# ---------------------------------------------------------

def trigger_buzzer():
    if USE_REAL_HARDWARE:
        # Future Raspberry Pi implementation:
        #
        # import RPi.GPIO as GPIO
        # GPIO.setup(BUZZER_PIN, GPIO.OUT)
        # GPIO.output(BUZZER_PIN, GPIO.HIGH)
        #
        pass

    print("[ALERT] Buzzer triggered.")


def send_sms_via_gsm(message: str, contacts: list[str]):
    """
    SMS through GSM.

    Works without internet when a SIM800L or similar GSM
    module is connected.
    """

    if USE_REAL_HARDWARE:
        # Future GSM implementation:
        #
        # import serial
        # gsm = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)
        #
        # for number in contacts:
        #     gsm.write(b'AT+CMGF=1\r')
        #     gsm.write(f'AT+CMGS="{number}"\r'.encode())
        #     gsm.write(message.encode() + b"\x1A")
        #
        pass

    print(f"[ALERT] SMS to {contacts}: {message}")


def push_app_notification(message: str):
    """
    Browser/mobile notification placeholder.

    The web frontend receives the structured alert separately.
    """

    print(f"[ALERT] App push notification: {message}")


# ---------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------

def dispatch_alert(
    agent_result: dict,
    online: bool,
    contacts: list[str] | None = None
):
    """
    Dispatch a structured alert when the agent detects HIGH risk.

    Returns the structured alert so the API can also expose it
    directly to the frontend.
    """

    contacts = contacts or ["+917620622761"]

    risk = agent_result.get("overall_risk", "low")
    location = agent_result.get("location", {})
    hazard = agent_result.get("hazard_type", "unknown")
    reasoning = agent_result.get("reasoning", "Risk condition detected.")

    lat = location.get("lat")
    lon = location.get("lon")

    # -----------------------------------------------------
    # No emergency risk
    # -----------------------------------------------------

    if risk != "high":
        return {
            "active": False,
            "dispatched": False,
            "risk_level": risk,
        }

    # -----------------------------------------------------
    # Build structured alert
    # -----------------------------------------------------

    priority = get_alert_priority(risk)
    title = get_alert_title(hazard)
    action = get_recommended_action(hazard)

    now = datetime.now(timezone.utc).isoformat()

    alert = {
        "active": True,
        "risk_level": risk,
        "priority": priority,
        "hazard_type": hazard,
        "title": title,
        "message": reasoning,
        "reason": reasoning,
        "recommended_action": action,
        "lat": lat,
        "lon": lon,
        "timestamp": now,
        "mode": "online" if online else "offline",
        "channels": [],
        "dispatched": False,
        "duplicate_suppressed": False,
    }

    # -----------------------------------------------------
    # Prevent repeated alerts
    # -----------------------------------------------------

    if recent_similar_alert(
        hazard_type=hazard,
        lat=lat,
        lon=lon,
        minutes=ALERT_COOLDOWN_MINUTES,
    ):
        alert["duplicate_suppressed"] = True

        print(
            f"[ALERT] Duplicate {hazard} alert suppressed "
            f"(cooldown {ALERT_COOLDOWN_MINUTES} minutes)."
        )

        return alert

    # -----------------------------------------------------
    # Human-readable emergency message
    # -----------------------------------------------------

    sms_message = (
        f"DISASTER CONNECT - {priority} {hazard.upper()} ALERT\n"
        f"{reasoning}\n"
        f"Location: {lat:.4f}, {lon:.4f}\n"
        f"Action: {action}"
    )

    # -----------------------------------------------------
    # Buzzer
    # -----------------------------------------------------

    trigger_buzzer()
    alert["channels"].append("buzzer")

    # -----------------------------------------------------
    # SMS
    # -----------------------------------------------------

    send_sms_via_gsm(sms_message, contacts)
    alert["channels"].append("sms")

    # -----------------------------------------------------
    # Browser / app notification
    # -----------------------------------------------------

    if online:
        push_app_notification(sms_message)
        alert["channels"].append("browser")

    # -----------------------------------------------------
    # Save alert
    # -----------------------------------------------------

    save_alert(
        hazard_type=hazard,
        risk_level=risk,
        reasoning=reasoning,
        lat=lat,
        lon=lon,
        mode="online" if online else "offline",
        title=title,
        recommended_action=action,
        priority=priority,
        message=reasoning,
    )

    alert["dispatched"] = True

    print(
        f"[ALERT] {priority} {hazard.upper()} alert dispatched "
        f"through {', '.join(alert['channels'])}"
    )

    return alert