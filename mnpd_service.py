"""
MNPD Dispatch Service - Core logic for fetching dispatches, geocoding, and proximity search.
"""

import math
import time
import requests
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field


MNPD_DISPATCH_URL = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
    "Metro_Nashville_Police_Department_Active_Dispatch_Table_view/FeatureServer/0/query"
)

NFD_DISPATCH_URL = (
    "https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/"
    "Nashville_Fire_Department_Active_Incidents_view/FeatureServer/0/query"
)

CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# Simple in-memory geocode cache to avoid hammering the Census API
_geocode_cache: dict[str, Optional["Coordinates"]] = {}


@dataclass
class Coordinates:
    lat: float
    lng: float


@dataclass
class DispatchEvent:
    incident_type_code: str
    incident_type: str
    call_received: datetime
    last_updated: datetime
    address: str
    location_info: Optional[str]
    city: str
    source: str  # "police" or "fire"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_miles: Optional[float] = None
    unit_id: Optional[str] = None
    event_number: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "incident_type_code": self.incident_type_code,
            "incident_type": self.incident_type,
            "call_received": self.call_received.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "address": self.address,
            "location_info": self.location_info,
            "city": self.city,
            "source": self.source,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_miles": round(self.distance_miles, 2) if self.distance_miles is not None else None,
            "unit_id": self.unit_id,
            "event_number": self.event_number,
        }


def geocode_address(address: str, city_hint: str = "Nashville, TN") -> Optional[Coordinates]:
    """
    Convert an address string to coordinates using the US Census Geocoder.
    Appends city_hint if not already present. Caches results.
    """
    full_address = address
    if city_hint and city_hint.lower() not in address.lower():
        full_address = f"{address}, {city_hint}"

    if full_address in _geocode_cache:
        return _geocode_cache[full_address]

    params = {
        "address": full_address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    }

    try:
        resp = requests.get(CENSUS_GEOCODER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            _geocode_cache[full_address] = None
            return None

        coords = matches[0].get("coordinates", {})
        result = Coordinates(lat=coords.get("y"), lng=coords.get("x"))
        _geocode_cache[full_address] = result
        return result
    except (requests.RequestException, KeyError, IndexError):
        _geocode_cache[full_address] = None
        return None


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def _epoch_ms_to_datetime(epoch_ms: Optional[int]) -> datetime:
    """Convert epoch milliseconds to a timezone-aware datetime."""
    if epoch_ms is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)


def fetch_mnpd_dispatches() -> list[DispatchEvent]:
    """Fetch active MNPD police dispatches."""
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "json",
        "orderByFields": "CallReceivedTime DESC",
    }

    try:
        resp = requests.get(MNPD_DISPATCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        events = []
        for feat in data.get("features", []):
            attrs = feat.get("attributes", {})
            events.append(DispatchEvent(
                incident_type_code=attrs.get("IncidentTypeCode", ""),
                incident_type=attrs.get("IncidentTypeName", ""),
                call_received=_epoch_ms_to_datetime(attrs.get("CallReceivedTime")),
                last_updated=_epoch_ms_to_datetime(attrs.get("LastUpdated")),
                address=attrs.get("Location", ""),
                location_info=attrs.get("LocationDescription"),
                city=attrs.get("CityName", ""),
                source="police",
            ))
        return events
    except requests.RequestException:
        return []


def fetch_nfd_dispatches() -> list[DispatchEvent]:
    """Fetch active Nashville Fire Department dispatches."""
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "json",
        "orderByFields": "DispatchDateTime DESC",
    }

    try:
        resp = requests.get(NFD_DISPATCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        events = []
        for feat in data.get("features", []):
            attrs = feat.get("attributes", {})
            events.append(DispatchEvent(
                incident_type_code="",
                incident_type=attrs.get("incident_type_id", ""),
                call_received=_epoch_ms_to_datetime(attrs.get("DispatchDateTime")),
                last_updated=_epoch_ms_to_datetime(attrs.get("DispatchDateTime")),
                address="",
                location_info=None,
                city=attrs.get("PostalCode", ""),
                source="fire",
                unit_id=attrs.get("Unit_ID"),
                event_number=attrs.get("event_number"),
            ))
        return events
    except requests.RequestException:
        return []


def fetch_all_dispatches() -> list[DispatchEvent]:
    """Fetch both police and fire dispatches."""
    return fetch_mnpd_dispatches() + fetch_nfd_dispatches()


def geocode_dispatches(events: list[DispatchEvent]) -> list[DispatchEvent]:
    """Geocode all dispatch events that have addresses but no coordinates."""
    for event in events:
        if event.address and event.latitude is None:
            coords = geocode_address(event.address)
            if coords:
                event.latitude = coords.lat
                event.longitude = coords.lng
    return events


def find_nearby_dispatches(
    home: Coordinates,
    radius_miles: float = 2.0,
    include_fire: bool = False,
    geocode: bool = True,
) -> list[DispatchEvent]:
    """
    Fetch active dispatches and return those within radius_miles of home,
    sorted by distance.
    """
    if include_fire:
        events = fetch_all_dispatches()
    else:
        events = fetch_mnpd_dispatches()

    if geocode:
        geocode_dispatches(events)

    results = []
    for event in events:
        if event.latitude is not None and event.longitude is not None:
            event.distance_miles = haversine_miles(
                home.lat, home.lng,
                event.latitude, event.longitude,
            )
            if event.distance_miles <= radius_miles:
                results.append(event)

    results.sort(key=lambda e: e.distance_miles or float("inf"))
    return results


def find_nearby_by_address(
    address: str,
    radius_miles: float = 2.0,
    include_fire: bool = False,
) -> dict:
    """
    High-level function: geocode a home address and find nearby dispatches.
    """
    home = geocode_address(address)
    if home is None:
        return {"error": "Could not geocode home address", "query_address": address}

    events = find_nearby_dispatches(
        home, radius_miles=radius_miles, include_fire=include_fire,
    )

    return {
        "query_address": address,
        "coordinates": {"lat": home.lat, "lng": home.lng},
        "radius_miles": radius_miles,
        "count": len(events),
        "dispatches": [e.to_dict() for e in events],
    }


# CLI interface for quick testing
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python mnpd_service.py <home_address> [radius_miles]")
        print("Example: python mnpd_service.py '123 Main St, Nashville, TN' 2.0")
        sys.exit(1)

    address = sys.argv[1]
    radius = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    result = find_nearby_by_address(address, radius_miles=radius)
    print(json.dumps(result, indent=2))
