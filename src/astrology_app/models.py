from dataclasses import dataclass
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
    date_of_birth: str  # YYYY-MM-DD
    time_of_birth: str  # HH:MM (24-hour)
    birth_place: str
    timezone: str  # IANA timezone or alias (e.g. "Asia/Kolkata", "IST")
