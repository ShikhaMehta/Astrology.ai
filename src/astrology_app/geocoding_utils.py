from __future__ import annotations

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder


def geocode_place(place: str) -> tuple[float, float]:
    """Convert place string to lat/lon coordinates."""
    geolocator = Nominatim(user_agent="astrology-ai/0.1")
    location = geolocator.geocode(place, timeout=15)
    if location is None:
        raise ValueError(
            "Could not geocode the birth place. "
            "Try 'City, State, Country' format."
        )
    return float(location.latitude), float(location.longitude)


def infer_timezone(lat: float, lon: float) -> str:
    """Infer IANA timezone string from lat/lon coordinates."""
    tf = TimezoneFinder()
    timezone = tf.timezone_at(lat=lat, lng=lon)
    if timezone is None:
        raise ValueError(
            "Could not infer timezone from location. "
            "Please enter timezone manually."
        )
    return timezone
