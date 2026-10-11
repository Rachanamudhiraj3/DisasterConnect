"""
Local FastAPI API + web frontend server. Runs on the same device (or local
network) -- the browser page talks to this over localhost, never over
the public internet.

    python -m backend.server

Then open http://localhost:5000 in a browser. One page covers four
things, all backed by the exact same agent pipeline main.py uses:

- Live Monitor  -- reads your device's GPS chip via the browser's
                   Geolocation API, sends only lat/lon to this local
                   server, and shows the resulting risk decision.
- History       -- recent sensor readings + alert log, straight from
                   the local SQLite database.
- Historical Event Test -- replay a real flood/earthquake by date +
                   country (e.g. 28 Sep 2018, Indonesia) instead of
                   waiting for the sensor simulator to roll a spike.
- Testing       -- hand-enter any sensor values you like and run them
                   through the real pipeline -- a genuine "what if"
                   sandbox, not a mocked preview.
"""

import os
import networkx as nx
from datetime import date
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config.settings import (
    FLOOD_WATER_LEVEL_CM,
    FLOOD_RAIN_RATE_MM_HR,
    EARTHQUAKE_STA_LTA_RATIO,
    STORM_WIND_SPEED_KMH,
    STORM_RAIN_RATE_MM_HR,
    TSUNAMI_SEA_LEVEL_CHANGE_CM,
    FLOOD_ALERT_RADIUS_KM,
    SAFE_HOUSE_SEARCH_RADIUS_KM,
)

from database.db import (
    init_db,
    recent_readings,
    recent_alerts,
    save_reading,
    mark_synced,
)
from network.connectivity import is_online
from network.weather import fetch_weather_context
from network.earthquakes import find_historical_earthquakes
from network.shelters import find_nearby_shelters
from sensors.reader import read_sensors
from agents.graph import run_agent, run_agent_isolated
from alerts.dispatcher import dispatch_alert
from main import run_once
from routing.route_service import find_route

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Same country lookup the old Streamlit test simulator offered, so the
# bundled demo cases (e.g. Palu 2018 M7.5) still work identically.
COUNTRIES = {
    "India":        (20.5937,  78.9629),
    "Bangladesh":   (23.6850,  90.3563),
    "Nepal":        (28.3949,  84.1240),
    "Sri Lanka":    ( 7.8731,  80.7718),
    "Pakistan":     (30.3753,  69.3451),
    "China":        (35.8617, 104.1954),
    "Japan":        (36.2048, 138.2529),
    "Philippines":  (12.8797, 121.7740),
    "Indonesia":    (-0.7893, 113.9213),
    "Thailand":     (15.8700, 100.9925),
    "Vietnam":      (14.0583, 108.2772),
    "Malaysia":     ( 4.2105, 101.9758),
    "Myanmar":      (21.9162,  95.9560),
    "USA":          (37.0902,  -95.7129),
    "Mexico":       (23.6345, -102.5528),
    "Brazil":       (-14.2350, -51.9253),
    "Colombia":     ( 4.5709,  -74.2973),
    "Peru":         (-9.1900,  -75.0152),
    "UK":           (55.3781,   -3.4360),
    "France":       (46.2276,    2.2137),
    "Germany":      (51.1657,   10.4515),
    "Italy":        (41.8719,   12.5674),
    "Turkey":       (38.9637,   35.2433),
    "Egypt":        (26.8206,   30.8025),
    "Nigeria":      ( 9.0820,    8.6753),
    "Kenya":        ( 0.0236,   37.9062),
    "Ethiopia":     ( 9.1450,   40.4897),
    "Australia":    (-25.2744, 133.7751),
    "New Zealand":  (-40.9006, 174.8860),
    "UAE":          (23.4241,   53.8478),
}

app = FastAPI(title="Local Disaster Watch")
init_db()


class LocationIn(BaseModel):
    lat: float
    lon: float


class HistoricalTestIn(BaseModel):
    country: str
    start_date: date
    end_date: date | None = None


class ManualTestIn(BaseModel):
    water_level_cm: float
    rain_rate_mm_hr: float
    pressure_hpa: float
    vibration_g: float
    wind_speed_kmh: float = 0.0
    sea_level_change_cm: float = 0.0
    lat: float
    lon: float


def _dashboard_payload(
    location: dict,
    sensors: dict,
    result: dict,
    online: bool,
    weather: dict | None,
    alert: dict | None = None,
) -> dict:
    """Build the response used by the Disaster Connect frontend."""

    return {
        "online": online,

        "location": location,

        "sensors": sensors,

        "weather": weather,

        "risk": {
            "level": result["overall_risk"],
            "hazard": result["hazard_type"],
            "reason": result["reasoning"],
            "flood": result["flood_risk"],
            "earthquake": result["earthquake_risk"],
            "storm": result["storm_risk"],
            "tsunami": result["tsunami_risk"],
        },

        "alert": alert or {
            "active": False,
            "risk_level": result["overall_risk"],
        },

        "updated": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/status")
def status():
    return {"online": is_online()}


@app.get("/api/config")
def get_config():
    """Risk thresholds straight from config/settings.py, so the UI can never
    drift out of sync with what the agents actually enforce."""
    return {
        "flood_water_level_cm": FLOOD_WATER_LEVEL_CM,
        "flood_rain_rate_mm_hr": FLOOD_RAIN_RATE_MM_HR,
        "earthquake_sta_lta_ratio": EARTHQUAKE_STA_LTA_RATIO,
        "storm_wind_speed_kmh": STORM_WIND_SPEED_KMH,
        "storm_rain_rate_mm_hr": STORM_RAIN_RATE_MM_HR,
        "tsunami_sea_level_change_cm": TSUNAMI_SEA_LEVEL_CHANGE_CM,
        "flood_alert_radius_km": FLOOD_ALERT_RADIUS_KM,
        "safe_house_search_radius_km": SAFE_HOUSE_SEARCH_RADIUS_KM,
    }


@app.get("/api/countries")
def countries():
    return {name: {"lat": lat, "lon": lon} for name, (lat, lon) in COUNTRIES.items()}


@app.get("/api/readings")
def readings(limit: int = 50):
    return recent_readings(limit=limit)


@app.get("/api/alerts")
def alerts(limit: int = 20):
    return recent_alerts(limit=limit)

@app.get("/api/route")
def route(
    start_lat: float,
    start_lon: float,
    destination_lat: float,
    destination_lon: float,
):
    """
    Calculate an offline route using the locally stored
    Hyderabad OpenStreetMap road network.
    """

    try:
        result = find_route(
            start_lat=start_lat,
            start_lon=start_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
        )

        return result

    except nx.NetworkXNoPath:
        raise HTTPException(
            status_code=404,
            detail="No route found between the selected locations."
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Offline routing failed: {exc}"
        )

@app.get("/api/safe-houses")
def safe_houses(lat: float, lon: float, radius_km: float = SAFE_HOUSE_SEARCH_RADIUS_KM):
    """
    Nearby hospitals, community centres, fire/police stations, stadiums,
    and tagged shelters from OpenStreetMap -- candidate safe houses, not a
    verified official shelter list. Needs
    internet (Overpass API); returns an empty list offline or on any lookup
    failure rather than erroring, same fail-safe pattern as the weather and
    historical-earthquake lookups.

    If nothing turns up within radius_km, automatically retries once at up
    to 3x the radius (capped at 20km) -- sparser areas shouldn't just come
    back empty when a wider look would find something.
    """
    if not is_online():
        return {"shelters": [], "radius_km": radius_km, "expanded": False}

    shelters = find_nearby_shelters(lat, lon, radius_km)
    expanded = False
    if not shelters and radius_km < 20:
        wider_radius = min(radius_km * 3, 20)
        shelters = find_nearby_shelters(lat, lon, wider_radius)
        if shelters:
            radius_km = wider_radius
            expanded = True

    return {"shelters": shelters, "radius_km": radius_km, "expanded": expanded}


@app.post("/api/location")
def receive_location(body: LocationIn):
    """
    Called by the browser frontend after navigator.geolocation succeeds.
    Only lat/lon cross the network (to localhost) -- everything else
    (sensor reading, risk decision) happens on this same local machine.
    """
    location = {"lat": body.lat, "lon": body.lon}
    sensors = read_sensors()
    online = is_online()

    reading_id = save_reading({**sensors, **location})
    if online:
        mark_synced(reading_id)

    weather_context = fetch_weather_context(body.lat, body.lon) if online else None
    result = run_agent(sensors, location, weather_context, online)
    alert = dispatch_alert(result, online)
    result["alert"] = alert
    return result



@app.post("/api/dashboard")
def dashboard(body: LocationIn):
    """Run one live check and return the compact response used by the mobile UI."""
    location = {"lat": body.lat, "lon": body.lon}
    sensors = read_sensors()
    online = is_online()
    reading_id = save_reading({**sensors, **location})
    if online:
        mark_synced(reading_id)

    weather = fetch_weather_context(body.lat, body.lon) if online else None
    result = run_agent(sensors, location, weather, online)
    alert = dispatch_alert(result, online)

    return _dashboard_payload(
        location,
        sensors,
        result,
        online,
        weather,
        alert,
    )



def _linear_slope(values: list[float]) -> float:
    """Least-squares change per reading; returns zero when a trend is unavailable."""
    if len(values) < 2:
        return 0.0
    midpoint = (len(values) - 1) / 2
    denominator = sum((index - midpoint) ** 2 for index in range(len(values)))
    if not denominator:
        return 0.0
    average = sum(values) / len(values)
    return sum((index - midpoint) * (value - average) for index, value in enumerate(values)) / denominator


@app.get("/api/prediction")
def prediction(limit: int = 24):
    """Return a short-term, explainable sensor-trend estimate for the mobile AI tab.

    This endpoint deliberately does not claim to predict earthquakes. It visualises
    vibration activity and flags an elevated near-term reading for attention only.
    """
    limit = max(2, min(limit, 100))
    samples = list(reversed(recent_readings(limit=limit)))

    def values_for(name: str) -> list[float]:
        return [float(sample[name]) for sample in samples if sample.get(name) is not None]

    water_values = values_for("water_level_cm")
    rain_values = values_for("rain_rate_mm_hr")
    vibration_values = values_for("vibration_g")
    horizon = 3
    water_forecast = max(0.0, water_values[-1] + _linear_slope(water_values) * horizon) if water_values else None
    rain_forecast = max(0.0, rain_values[-1] + _linear_slope(rain_values) * horizon) if rain_values else None
    vibration_forecast = max(0.0, vibration_values[-1] + _linear_slope(vibration_values) * horizon) if vibration_values else None

    flood_high = (
        (water_forecast is not None and water_forecast < FLOOD_WATER_LEVEL_CM)
        or (rain_forecast is not None and rain_forecast > FLOOD_RAIN_RATE_MM_HR)
    )
    if not water_values or not rain_values:
        flood_reason = "More local water and rain readings are needed before a short-term estimate is available."
    elif flood_high:
        flood_reason = (
            f"The next {horizon}-reading trend reaches a flood trigger: "
            f"water {water_forecast:.1f} cm or rain {rain_forecast:.1f} mm/hr."
        )
    else:
        flood_reason = (
            f"The next {horizon}-reading trend remains below flood triggers "
            f"(water {water_forecast:.1f} cm; rain {rain_forecast:.1f} mm/hr)."
        )

    vibration_attention_g = 0.1
    quake_high = vibration_forecast is not None and vibration_forecast >= vibration_attention_g
    if not vibration_values:
        quake_reason = "More local vibration readings are needed to show activity."
    elif quake_high:
        quake_reason = f"Vibration trend is elevated at {vibration_forecast:.3f} g; inspect the live seismic reading now."
    else:
        quake_reason = f"Vibration trend is currently quiet at {vibration_forecast:.3f} g. This is activity monitoring, not earthquake prediction."

    explanation = (
        "The flood estimate fits a straight trend to recent water-level and rain-gauge values, then compares a short projection with configured alert thresholds. "
        "The seismic panel only monitors sensor activity: earthquakes cannot be reliably predicted from a short local vibration history."
    )
    return {
        "samples": samples,
        "flood": {"level": "high" if flood_high else "low", "reason": flood_reason},
        "earthquake": {"level": "high" if quake_high else "low", "reason": quake_reason},
        "thresholds": {
            "flood_water_level_cm": FLOOD_WATER_LEVEL_CM,
            "vibration_attention_g": vibration_attention_g,
        },
        "explanation": explanation,
    }


@app.post("/api/manual-test")
def manual_test(body: ManualTestIn):
    """
    Powers the Testing tab -- feeds hand-entered sensor values straight into
    the same agent logic main.py uses, instead of GPS + the random
    simulator or a historical date lookup. This is the real pipeline, not
    a preview: a high-risk result saves a reading, dispatches the real
    alert (buzzer/SMS -- printed to the server console -- and, if online,
    the app-push bonus channel), and gets logged to History exactly like a
    live detection would.

    The flood check is a pure threshold comparison on the two values given,
    so it's fully deterministic. The earthquake check uses
    run_agent_isolated (see agents/graph.py) rather than the live path's
    shared rolling history, so the same vibration_g value always gives the
    same verdict here regardless of what other tests ran earlier -- a
    clearly extreme value (0.5g+) reliably crosses the trigger.
    """
    sensors = {
        "water_level_cm": body.water_level_cm,
        "rain_rate_mm_hr": body.rain_rate_mm_hr,
        "pressure_hpa": body.pressure_hpa,
        "vibration_g": body.vibration_g,
        "wind_speed_kmh": body.wind_speed_kmh,
        "sea_level_change_cm": body.sea_level_change_cm,
    }
    location = {"lat": body.lat, "lon": body.lon}
    online = is_online()

    reading_id = save_reading({**sensors, **location})
    if online:
        mark_synced(reading_id)

    weather_context = fetch_weather_context(body.lat, body.lon) if online else None
    result = run_agent_isolated(sensors, location, weather_context, online)
    dispatch_alert(result, online)

    return result


@app.post("/api/historical-test")
def historical_test(body: HistoricalTestIn):
    """
    Powers the historical-event test tool -- runs the exact same pipeline
    as main.py (via run_once), but with a chosen country/date instead of
    GPS + the live clock, so a known event can be replayed deterministically
    instead of waiting for the sensor simulator to roll a spike.
    """
    if body.country not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Unknown country: {body.country}")

    lat, lon = COUNTRIES[body.country]
    location = {"lat": lat, "lon": lon}
    end_date = body.end_date or body.start_date
    if end_date < body.start_date:
        body.start_date, end_date = end_date, body.start_date
    online = is_online()

    result = run_once(location=location, selected_date=body.start_date, country=body.country)
    events = find_historical_earthquakes(body.start_date, end_date, body.country, location, online)

    return {"result": result, "events": events, "location": location}


# Registered last so it only catches what the /api/* routes above didn't --
# serves index.html at "/" and style.css / app.js alongside it.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import threading
    import webbrowser
    import uvicorn
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    uvicorn.run(app, host="0.0.0.0", port=5000)
