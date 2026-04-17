from dataclasses import dataclass, field
from enum import Enum


class QuestionCategory(str, Enum):
    PERSONALITY = "personality"
    CAREER = "career"
    RELATIONSHIPS = "relationships"
    FAMILY = "family"
    HEALTH = "health"
    SPIRITUAL = "spiritual"
    TIMING = "timing"
    GENERAL = "general"


@dataclass(frozen=True)
class BirthInput:
    date_of_birth: str        # YYYY-MM-DD
    time_of_birth: str        # HH:MM (24-hour local time at place of birth)
    birth_place: str
    timezone: str             # IANA timezone e.g. "Asia/Kolkata"
    timezone_source: str = "unknown"   # "user provided" or "inferred from location"
    latitude: float = 0.0
    longitude: float = 0.0
