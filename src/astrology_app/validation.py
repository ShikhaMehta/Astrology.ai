from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

# Country-level defaults are safe only where one timezone is used nationally.
COUNTRY_DEFAULT_TIMEZONES = {
    "india": "Asia/Kolkata",
    "nepal": "Asia/Kathmandu",
    "sri lanka": "Asia/Colombo",
    "bhutan": "Asia/Thimphu",
}


def normalize_and_validate_birth_input(birth_input: BirthInput) -> BirthInput:
    _validate_date(birth_input.date_of_birth)
    _validate_time(birth_input.time_of_birth)
    country = _validate_place(birth_input.birth_place)
    timezone = _resolve_timezone(birth_input.timezone, country)
    _validate_timezone(timezone)
    return BirthInput(
        date_of_birth=birth_input.date_of_birth,
        time_of_birth=birth_input.time_of_birth,
        birth_place=birth_input.birth_place,
        timezone=timezone,
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


def _validate_place(value: str) -> str:
    if not value.strip():
        raise ValidationError("Place of birth is required.")
    if "," not in value:
        raise ValidationError(
            "Place should be 'City, State, Country' or 'City, Country'. "
            "Zip/postal code can be included."
        )
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) < 2:
        raise ValidationError(
            "Place should include at least city and country (or city, state, country)."
        )
    return parts[-1].lower()


def _validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError(
            "Timezone is invalid. Use IANA zone like Asia/Kolkata or America/Phoenix."
        ) from exc


def _resolve_timezone(timezone_input: str, country: str) -> str:
    raw = timezone_input.strip()
    if raw:
        upper = raw.upper()
        if upper in TIMEZONE_ALIASES:
            return TIMEZONE_ALIASES[upper]
        return raw
    if country in COUNTRY_DEFAULT_TIMEZONES:
        return COUNTRY_DEFAULT_TIMEZONES[country]
    raise ValidationError(
        "Timezone is required for this country. For example: America/New_York."
    )
