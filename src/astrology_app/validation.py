from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astrology_app.geocoding_utils import geocode_place, infer_timezone
from astrology_app.models import BirthInput


class ValidationError(ValueError):
    pass


TIMEZONE_ALIASES = {
    "IST": "Asia/Kolkata",
    "INDIA": "Asia/Kolkata",
    "INDIAN STANDARD TIME": "Asia/Kolkata",
    "UTC": "UTC",
    "GMT": "Etc/GMT",
}


def normalize_and_validate_birth_input(birth_input: BirthInput) -> BirthInput:
    _validate_date(birth_input.date_of_birth)
    _validate_time(birth_input.time_of_birth)
    _validate_place(birth_input.birth_place)

    try:
        lat, lon = geocode_place(birth_input.birth_place)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    timezone, timezone_source = _resolve_timezone(
        birth_input.timezone,
        lat,
        lon,
    )

    return BirthInput(
        date_of_birth=birth_input.date_of_birth,
        time_of_birth=birth_input.time_of_birth,
        birth_place=birth_input.birth_place,
        timezone=timezone,
        timezone_source=timezone_source,
        latitude=lat,
        longitude=lon,
    )


def _validate_date(value: str) -> None:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValidationError("Date of birth must be YYYY-MM-DD.") from exc


def _validate_time(value: str) -> None:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValidationError("Time of birth must be HH:MM (24-hour).") from exc


def _validate_place(value: str) -> None:
    if not value.strip():
        raise ValidationError("Place of birth is required.")
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) < 2:
        raise ValidationError(
            "Place should be 'City, State, Country' or 'City, Country'. "
            "Zip/postal code can be included."
        )


def _resolve_timezone(timezone_input: str, lat: float, lon: float) -> tuple[str, str]:
    raw = timezone_input.strip()

    if raw:
        upper = raw.upper()
        if upper in TIMEZONE_ALIASES:
            return TIMEZONE_ALIASES[upper], "user provided"

        try:
            ZoneInfo(raw)
            return raw, "user provided"
        except ZoneInfoNotFoundError:
            print(
                f"Warning: '{raw}' is not recognized. "
                "Inferring timezone from location instead."
            )

    try:
        inferred = infer_timezone(lat, lon)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    try:
        ZoneInfo(inferred)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(
            f"Inferred timezone '{inferred}' is not supported on this system."
        ) from exc

    return inferred, "inferred from location"
