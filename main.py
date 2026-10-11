"""
Main loop. This is the file you run.

    python main.py                 # auto: online when available, offline otherwise
    python main.py --mode offline  # force offline (good for testing without wifi)
    python main.py --mode online   # force online (fails loudly if no internet)
    python main.py --once          # run a single loop iteration and exit (for testing)
"""

import time
import os
from datetime import date
from config.settings import RUN_MODE, SENSOR_POLL_SECONDS
from database.db import init_db, save_reading, unsynced_readings, mark_synced
from sensors.reader import read_sensors, get_gps_location
from network.connectivity import is_online
from network.weather import fetch_weather_context
from network.earthquakes import find_historical_earthquake
from agents.graph import run_agent
from alerts.dispatcher import dispatch_alert


def sync_unsynced_readings():
    """Called right after the system detects it's back online -- pushes
    anything logged during the offline gap."""
    pending = unsynced_readings()
    if not pending:
        return
    print(f"[SYNC] Reconnected -- syncing {len(pending)} offline reading(s).")
    for row in pending:
        # requests.post("https://your-server/api/readings", json=row)  # real sync call
        mark_synced(row["id"])


def run_once(
    location: dict | None = None,
    selected_date: date | None = None,
    country: str | None = None,
) -> dict:
    """
    Run a single detection cycle and return the agent result.
    Used by the test simulator and --once flag.
    If location is provided, uses it instead of GPS.  Supplying a date and
    country enables historical-event lookup for the test simulator.
    """
    init_db()
    online = is_online()

    loc     = location or get_gps_location()
    sensors = read_sensors()

    reading_id = save_reading({**sensors, **loc})
    if online:
        mark_synced(reading_id)

    weather_context = fetch_weather_context(loc["lat"], loc["lon"]) if online else None
    historical_earthquake = find_historical_earthquake(selected_date, country, loc, online)
    result = run_agent(sensors, loc, weather_context, online, historical_earthquake)
    dispatch_alert(result, online)

    return result


def run_loop(once: bool = False):
    init_db()
    was_online = False

    print(f"Disaster alert system starting -- mode: {RUN_MODE}")

    while True:
        online = is_online()

        if online and not was_online:
            sync_unsynced_readings()
        was_online = online

        location   = get_gps_location()
        sensors    = read_sensors()
        reading_id = save_reading({**sensors, **location})
        if online:
            mark_synced(reading_id)

        weather_context = fetch_weather_context(location["lat"], location["lon"]) if online else None

        result = run_agent(sensors, location, weather_context, online)
        dispatch_alert(result, online)

        status = "ONLINE " if online else "OFFLINE"
        print(f"[{status}] flood={result['flood_risk']} | earthquake={result['earthquake_risk']} "
              f"| overall={result['overall_risk']} | {result['reasoning']}")

        if once:
            return result

        time.sleep(SENSOR_POLL_SECONDS)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["auto", "online", "offline"], default=None)
    parser.add_argument("--once", action="store_true", help="run a single loop and exit (for testing)")
    args = parser.parse_args()

    if args.mode:
        os.environ["DISASTER_APP_MODE"] = args.mode

    run_loop(once=args.once)
