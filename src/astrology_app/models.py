from dataclasses import dataclass


@dataclass(frozen=True)
class BirthInput:
    date_of_birth: str  # YYYY-MM-DD
    time_of_birth: str  # HH:MM (24-hour)
    birth_place: str
    timezone: str  # e.g. "America/Phoenix"
