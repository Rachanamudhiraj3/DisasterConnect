"""Historical earthquake lookup for the date/country test simulator.

The bundled catalogue keeps important demo cases available without an
internet connection.  When online, USGS is queried for all events in the
selected day close to the selected country coordinate.
"""

from datetime import date, timedelta
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import requests


_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "earthquake_catalog.json"
_USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
_MIN_MAGNITUDE = 4.5
_SEARCH_RADIUS_KM = 1_500

# USGS event times are UTC. A country far from UTC can have its local calendar
# date land a day before/after the UTC date, so an exact-day match silently
# misses real events -- pad the search window by a day on each side.
_DATE_PAD_DAYS = 1


def _load_offline_catalog() -> list[dict]:
    try:
        with _CATALOG_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return []


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Great-circle distance, used to reject remote USGS results."""
    lat_delta = radians(lat_b - lat_a)
    lon_delta = radians(lon_b - lon_a)
    a = sin(lat_delta / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(lon_delta / 2) ** 2
    return 6_371 * 2 * asin(sqrt(a))


def _offline_events(start_date: date, end_date: date, country: str) -> list[dict]:
    window_start = start_date - timedelta(days=_DATE_PAD_DAYS)
    window_end = end_date + timedelta(days=_DATE_PAD_DAYS)
    matches = []
    for event in _load_offline_catalog():
        event_date_str = event.get("date")
        if not event_date_str or event.get("country", "").casefold() != country.casefold():
            continue
        try:
            event_date = date.fromisoformat(event_date_str)
        except ValueError:
            continue
        if window_start <= event_date <= window_end:
            matches.append({**event, "mode": "offline catalog"})
    return matches


def _online_events(start_date: date, end_date: date, location: dict) -> list[dict]:
    """Return every USGS event near the selected country within the padded window."""
    window_start = start_date - timedelta(days=_DATE_PAD_DAYS)
    window_end = end_date + timedelta(days=_DATE_PAD_DAYS + 1)  # USGS endtime is exclusive
    try:
        response = requests.get(
            _USGS_URL,
            params={
                "format": "geojson",
                "starttime": window_start.isoformat(),
                "endtime": window_end.isoformat(),
                "minmagnitude": _MIN_MAGNITUDE,
                "orderby": "magnitude",
            },
            timeout=8,
        )
        response.raise_for_status()
        features = response.json().get("features", [])
    except (requests.RequestException, ValueError):
        return []

    events = []
    for feature in features:
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) < 2 or properties.get("mag") is None or properties.get("time") is None:
            continue
        lon, lat = coordinates[:2]
        distance = _distance_km(location["lat"], location["lon"], lat, lon)
        if distance > _SEARCH_RADIUS_KM:
            continue
        event_date = date.fromtimestamp(properties["time"] / 1000)
        events.append({
            "date": event_date.isoformat(),
            "magnitude": properties["mag"],
            "place": properties.get("place", "near the selected country"),
            "latitude": lat,
            "longitude": lon,
            "distance_km": round(distance),
            "source": "USGS live historical catalog",
            "mode": "online catalog",
        })
    return events


def find_historical_earthquakes(
    start_date: date | None,
    end_date: date | None,
    country: str | None,
    location: dict,
    online: bool,
) -> list[dict]:
    """Find every historical event between two dates (inclusive), merging the
    live source with the offline catalogue so nothing is missed when one side
    comes up empty. Sorted by date, strongest first within a date."""
    if not start_date or not country:
        return []
    end_date = end_date or start_date

    events = _online_events(start_date, end_date, location) if online else []
    events += _offline_events(start_date, end_date, country)

    deduped: dict[tuple, dict] = {}
    for event in events:
        key = (event["date"], round(event["magnitude"], 1))
        if key not in deduped:
            deduped[key] = event
    return sorted(deduped.values(), key=lambda e: (e["date"], -e["magnitude"]))


def find_historical_earthquake(selected_date: date | None, country: str | None, location: dict, online: bool) -> dict | None:
    """Find the single strongest historical event on (or right around) the
    selected day -- used by the main detection pipeline."""
    events = find_historical_earthquakes(selected_date, selected_date, country, location, online)
    if not events:
        return None
    return max(events, key=lambda e: e["magnitude"])
