"""
Nearby safe-house lookup for the map's "safe houses nearby" overlay.

There is no public, universal registry of official emergency shelters --
so this queries OpenStreetMap's free Overpass API for the building types
most commonly pressed into service as real evacuation points: hospitals,
community centres, fire/police stations, stadiums, and anything explicitly
tagged as a shelter or assembly point. These are candidate safe houses,
not a verified official shelter list -- always confirm locally before
relying on one.

Fails safe like network/weather.py: any network problem returns an empty
list rather than raising, so the caller never needs special-case handling.
"""

from math import asin, cos, radians, sin, sqrt

import requests

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass rejects requests with no real User-Agent/Accept (406) --
# identify the app rather than sending the bare default requests headers.
_REQUEST_HEADERS = {
    "User-Agent": "local-disaster-alert-demo/1.0 (educational project)",
    "Accept": "application/json",
}
_SHELTER_TAGS = [
    ("amenity", "shelter"),
    ("emergency", "assembly_point"),
    ("amenity", "community_centre"),
    ("amenity", "hospital"),
    ("amenity", "fire_station"),
    ("amenity", "police"),
    ("leisure", "stadium"),
]


def _distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    lat_delta = radians(lat_b - lat_a)
    lon_delta = radians(lon_b - lon_a)
    a = sin(lat_delta / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(lon_delta / 2) ** 2
    return 6_371 * 2 * asin(sqrt(a))


def _address(tags: dict) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"]
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p) or None
    city = tags.get("addr:city")
    if street and city:
        return f"{street}, {city}"
    return street or city


def find_nearby_shelters(lat: float, lon: float, radius_km: float) -> list[dict]:
    radius_m = int(radius_km * 1000)
    clauses = "".join(
        f'node["{key}"="{value}"](around:{radius_m},{lat},{lon});'
        for key, value in _SHELTER_TAGS
    )
    query = f"[out:json][timeout:10];({clauses});out center;"

    try:
        response = requests.post(_OVERPASS_URL, data={"data": query}, headers=_REQUEST_HEADERS, timeout=12)
        response.raise_for_status()
        elements = response.json().get("elements", [])
    except (requests.RequestException, ValueError):
        return []

    shelters = []
    for element in elements:
        tags = element.get("tags", {})
        shelter_lat = element.get("lat") or element.get("center", {}).get("lat")
        shelter_lon = element.get("lon") or element.get("center", {}).get("lon")
        if shelter_lat is None or shelter_lon is None:
            continue
        kind = tags.get("amenity") or tags.get("emergency") or tags.get("leisure") or "shelter"
        name = tags.get("name") or kind.replace("_", " ").title()
        shelters.append({
            "name": name,
            "type": kind,
            "lat": shelter_lat,
            "lon": shelter_lon,
            "distance_km": round(_distance_km(lat, lon, shelter_lat, shelter_lon), 2),
            "address": _address(tags),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "opening_hours": tags.get("opening_hours"),
        })

    shelters.sort(key=lambda s: s["distance_km"])
    return shelters[:30]
