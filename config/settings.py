"""
Central configuration for the disaster alert system.

Everything that might change between a laptop test run, a Raspberry Pi
field unit, or a future hardware revision lives here -- so no other file
has hardcoded thresholds or paths.
"""

import os

from dotenv import load_dotenv

# Loads .env (GROQ_API_KEY, etc.) into the process environment if present --
# a no-op, not an error, when the file doesn't exist. Real env vars set
# outside the file (e.g. in CI) always win, since load_dotenv() by default
# never overwrites a variable that's already set.
load_dotenv()

# ---- Paths -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "disaster_alert.db")

# ---- Mode ----------------------------------------------------------------
# "auto"    -> check connectivity every loop, use online extras when present
# "offline" -> never attempt network calls, even if available (for testing)
# "online"  -> force online path (fails loudly if no internet)
RUN_MODE = os.environ.get("DISASTER_APP_MODE", "auto")

# Set to True once you wire up real GPIO/GSM hardware.
USE_REAL_HARDWARE = os.environ.get("USE_REAL_HARDWARE", "false").lower() == "true"

# ---- Risk thresholds (tune these against real local data later) --------
FLOOD_WATER_LEVEL_CM = 80          # ultrasonic sensor reading, cm from sensor to water
FLOOD_RAIN_RATE_MM_HR = 30         # rain gauge, mm/hour
FLOOD_PRESSURE_DROP_HPA = 6        # sudden pressure drop often precedes storms

EARTHQUAKE_STA_LTA_RATIO = 3.0     # STA/LTA trigger ratio (standard seismology technique)

# ---- Additional hazard thresholds ----------------------------------------
STORM_WIND_SPEED_KMH = 70          # sustained wind that needs immediate attention
STORM_RAIN_RATE_MM_HR = 50         # intense rainfall without a storm-code feed
TSUNAMI_SEA_LEVEL_CHANGE_CM = 50   # rapid coastal tide-gauge change; not river level

# ---- Map overlays (illustrative, not hazard modeling) ---------------------
# Flood has no standard "affected radius" formula without terrain/elevation
# data this project doesn't have -- this is a simple fixed circle drawn
# around the sensor on a high flood alert, not a flood-extent model.
FLOOD_ALERT_RADIUS_KM = 2

# How far out to look for nearby safe houses (schools, hospitals, community
# centres -- see network/shelters.py for why these, not a verified registry).
SAFE_HOUSE_SEARCH_RADIUS_KM = 5

# ---- Loop timing ---------------------------------------------------------
SENSOR_POLL_SECONDS = 5
CONNECTIVITY_CHECK_TIMEOUT = 2

# ---- LLM-assisted reasoning ------------------------------------------------
# On by default: the moment the system is online (and GROQ_API_KEY is set),
# a high-risk alert gets its reasoning rewritten as one plain-English
# sentence by Groq. Offline, or with no key, it silently stays on the
# pure rule-based reasoning -- never a requirement, always a bonus.
# Set USE_LLM_EXPLANATION=false to opt back out even when online.
USE_LLM_EXPLANATION = os.environ.get("USE_LLM_EXPLANATION", "true").lower() == "true"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
