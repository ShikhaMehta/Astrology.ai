from __future__ import annotations

from typing import Any

from astrology_app.models import QuestionCategory

SIGN_NAMES = [
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]

SIGN_TO_INDEX = {name: idx for idx, name in enumerate(SIGN_NAMES)}
SIGN_LORDS = {
    "aries": "mars",
    "taurus": "venus",
    "gemini": "mercury",
    "cancer": "moon",
    "leo": "sun",
    "virgo": "mercury",
    "libra": "venus",
    "scorpio": "mars",
    "sagittarius": "jupiter",
    "capricorn": "saturn",
    "aquarius": "saturn",
    "pisces": "jupiter",
}
BENEFICS = {"jupiter", "venus", "moon", "mercury"}
MALEFICS = {"sun", "mars", "saturn", "rahu", "ketu"}
STRONG_DIGNITIES = {"exalted", "moolatrikona", "own_sign", "favorable_sign"}
WEAK_DIGNITIES = {"debilitated", "challenging_sign"}


def build_question_features(
    *,
    question: str,
    category: QuestionCategory,
    evidence: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if metadata.get("status") == "mock-data-for-development":
        return {
            "mode": "mock",
            "question_type": _question_type(question, category),
            "ready_for_model": False,
            "reason": "mock-data-for-development",
        }

    question_type = _question_type(question, category)
    if question_type == "children":
        return _children_features(evidence, metadata)
    if question_type == "marriage":
        return _marriage_features(evidence, metadata)

    return {
        "mode": "real",
        "question_type": question_type,
        "ready_for_model": False,
        "reason": "no-specialized-feature-extractor-yet",
        "available_evidence_keys": sorted(evidence.keys()),
    }


def _question_type(question: str, category: QuestionCategory) -> str:
    text = question.lower()
    if category == QuestionCategory.FAMILY and any(
        term in text for term in ("kid", "kids", "child", "children")
    ):
        return "children"
    if category in {QuestionCategory.RELATIONSHIPS, QuestionCategory.TIMING} and any(
        term in text for term in ("marriage", "married", "wedding", "spouse")
    ):
        return "marriage"
    return category.value


def _children_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    houses = evidence.get("derived.houses", {})
    house_lords = evidence.get("derived.house_lords", {})
    dignities = evidence.get("derived.dignities", {})
    d1 = evidence.get("charts.d1", {})
    d7 = evidence.get("charts.d7", {})
    dashas = evidence.get("dashas", {})

    fifth_house = houses.get("5", {})
    fifth_lord = house_lords.get("5", {})
    fifth_lord_name = fifth_lord.get("lord")
    fifth_lord_placement = fifth_lord.get("lord_placement", {})
    fifth_lord_house = fifth_lord_placement.get("house")
    fifth_lord_dignity = dignities.get(fifth_lord_name, {}).get("dignity")
    jupiter_dignity = dignities.get("jupiter", {}).get("dignity")
    jupiter_house_d1 = _planet_house(d1, "jupiter")

    d7_fifth_sign = _house_sign_from_chart(d7, 5)
    d7_fifth_lord = SIGN_LORDS.get(d7_fifth_sign) if d7_fifth_sign else None
    d7_fifth_lord_house = _planet_house(d7, d7_fifth_lord) if d7_fifth_lord else None
    d7_fifth_occupants = _house_occupants_from_chart(d7, 5)
    d7_jupiter_house = _planet_house(d7, "jupiter")

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    _collect_house_signals(
        house_data=fifth_house,
        label="D1 5th house",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=fifth_lord_name,
        lord_house=fifth_lord_house,
        lord_dignity=fifth_lord_dignity,
        house_label="5th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="jupiter",
        dignity=jupiter_dignity,
        house_num=jupiter_house_d1,
        chart_label="D1",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    if d7_fifth_occupants:
        supportive_signals.append(
            f"D7 5th house occupants: {', '.join(d7_fifth_occupants)}."
        )
    _collect_lord_signals(
        lord_name=d7_fifth_lord,
        lord_house=d7_fifth_lord_house,
        lord_dignity=None,
        house_label="D7 5th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="jupiter",
        dignity=None,
        house_num=d7_jupiter_house,
        chart_label="D7",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    current_stack = _current_dasha_stack(dashas)
    child_significators = sorted(
        signal for signal in {"jupiter", "moon", "venus", fifth_lord_name} if signal
    )
    current_overlap = sorted(set(current_stack) & set(child_significators))
    windows = _supportive_mahadasha_windows(dashas, set(child_significators))

    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "children",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "primary_house": "5",
            "primary_lord": fifth_lord_name,
            "key_significator": "jupiter",
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_5th_house": fifth_house,
            "d1_5th_lord": fifth_lord,
            "d1_jupiter": d1.get("planets", {}).get("jupiter"),
            "d7_5th_house_sign": d7_fifth_sign,
            "d7_5th_house_occupants": d7_fifth_occupants,
            "d7_5th_lord": {
                "lord": d7_fifth_lord,
                "house": d7_fifth_lord_house,
            },
            "d7_jupiter_house": d7_jupiter_house,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Do not claim an exact number of children as certain.",
            "Prefer describing promise, delay, and likely family size tendency.",
            "Use only the structured facts and signals provided.",
        ],
        "metadata": metadata,
    }


def _marriage_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    houses = evidence.get("derived.houses", {})
    house_lords = evidence.get("derived.house_lords", {})
    dignities = evidence.get("derived.dignities", {})
    d1 = evidence.get("charts.d1", {})
    d9 = evidence.get("charts.d9", {})
    dashas = evidence.get("dashas", {})

    seventh_house = houses.get("7", {})
    seventh_lord = house_lords.get("7", {})
    seventh_lord_name = seventh_lord.get("lord")
    seventh_lord_placement = seventh_lord.get("lord_placement", {})
    seventh_lord_house = seventh_lord_placement.get("house")
    seventh_lord_dignity = dignities.get(seventh_lord_name, {}).get("dignity")
    venus_dignity = dignities.get("venus", {}).get("dignity")
    jupiter_dignity = dignities.get("jupiter", {}).get("dignity")
    venus_house_d1 = _planet_house(d1, "venus")
    jupiter_house_d1 = _planet_house(d1, "jupiter")

    d9_seventh_sign = _house_sign_from_chart(d9, 7)
    d9_seventh_lord = SIGN_LORDS.get(d9_seventh_sign) if d9_seventh_sign else None
    d9_seventh_lord_house = _planet_house(d9, d9_seventh_lord) if d9_seventh_lord else None
    d9_seventh_occupants = _house_occupants_from_chart(d9, 7)
    d9_venus_house = _planet_house(d9, "venus")

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    _collect_house_signals(
        house_data=seventh_house,
        label="D1 7th house",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=seventh_lord_name,
        lord_house=seventh_lord_house,
        lord_dignity=seventh_lord_dignity,
        house_label="7th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="venus",
        dignity=venus_dignity,
        house_num=venus_house_d1,
        chart_label="D1",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="jupiter",
        dignity=jupiter_dignity,
        house_num=jupiter_house_d1,
        chart_label="D1",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    if d9_seventh_occupants:
        supportive_signals.append(
            f"D9 7th house occupants: {', '.join(d9_seventh_occupants)}."
        )
    _collect_lord_signals(
        lord_name=d9_seventh_lord,
        lord_house=d9_seventh_lord_house,
        lord_dignity=None,
        house_label="D9 7th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="venus",
        dignity=None,
        house_num=d9_venus_house,
        chart_label="D9",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    relationship_significators = sorted(
        signal for signal in {"venus", "jupiter", seventh_lord_name} if signal
    )
    current_stack = _current_dasha_stack(dashas)
    current_overlap = sorted(set(current_stack) & set(relationship_significators))
    windows = _supportive_mahadasha_windows(dashas, set(relationship_significators))

    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "marriage",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "primary_house": "7",
            "primary_lord": seventh_lord_name,
            "key_significators": ["venus", "jupiter"],
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_7th_house": seventh_house,
            "d1_7th_lord": seventh_lord,
            "d1_venus": d1.get("planets", {}).get("venus"),
            "d1_jupiter": d1.get("planets", {}).get("jupiter"),
            "d9_7th_house_sign": d9_seventh_sign,
            "d9_7th_house_occupants": d9_seventh_occupants,
            "d9_7th_lord": {
                "lord": d9_seventh_lord,
                "house": d9_seventh_lord_house,
            },
            "d9_venus_house": d9_venus_house,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Do not claim a single exact marriage year with certainty.",
            "Prefer likely timing windows and confidence-aware language.",
            "Use only the structured facts and signals provided.",
        ],
        "metadata": metadata,
    }


def _collect_house_signals(
    *,
    house_data: dict[str, Any],
    label: str,
    supportive_signals: list[str],
    challenging_signals: list[str],
) -> None:
    for occupant in house_data.get("occupants", []):
        if occupant in BENEFICS:
            supportive_signals.append(f"{label} contains benefic {occupant}.")
        elif occupant in MALEFICS:
            challenging_signals.append(f"{label} contains malefic {occupant}.")

    for aspect in house_data.get("aspected_by", []):
        if aspect in BENEFICS:
            supportive_signals.append(f"{label} receives support from {aspect}.")
        elif aspect in MALEFICS:
            challenging_signals.append(f"{label} is pressured by {aspect}.")


def _collect_lord_signals(
    *,
    lord_name: str | None,
    lord_house: int | None,
    lord_dignity: str | None,
    house_label: str,
    supportive_signals: list[str],
    challenging_signals: list[str],
) -> None:
    if lord_house in {1, 2, 4, 5, 7, 9, 10, 11}:
        supportive_signals.append(f"{house_label} {lord_name} is in house {lord_house}.")
    elif lord_house in {6, 8, 12}:
        challenging_signals.append(f"{house_label} {lord_name} is in house {lord_house}.")
    elif lord_name and lord_house is not None:
        supportive_signals.append(f"{house_label} {lord_name} is in house {lord_house}.")

    if lord_name and lord_dignity in STRONG_DIGNITIES:
        supportive_signals.append(f"{house_label} {lord_name} has {lord_dignity} dignity.")
    elif lord_name and lord_dignity in WEAK_DIGNITIES:
        challenging_signals.append(f"{house_label} {lord_name} has {lord_dignity} dignity.")


def _collect_planet_signals(
    *,
    planet_name: str,
    dignity: str | None,
    house_num: int | None,
    chart_label: str,
    supportive_signals: list[str],
    challenging_signals: list[str],
) -> None:
    if dignity in STRONG_DIGNITIES:
        supportive_signals.append(f"{chart_label} {planet_name} has {dignity} dignity.")
    elif dignity in WEAK_DIGNITIES:
        challenging_signals.append(f"{chart_label} {planet_name} has {dignity} dignity.")

    if house_num in {1, 5, 7, 9, 11}:
        supportive_signals.append(f"{chart_label} {planet_name} is in house {house_num}.")
    elif house_num in {6, 8, 12}:
        challenging_signals.append(f"{chart_label} {planet_name} is in house {house_num}.")


def _supportive_mahadasha_windows(dashas: dict[str, Any], supportive_lords: set[str]) -> list[str]:
    sequence = dashas.get("sequence", [])
    windows: list[str] = []
    for index, item in enumerate(sequence):
        lord = item.get("lord")
        if lord not in supportive_lords:
            continue
        start = item.get("start", {})
        start_year = start.get("year")
        end_year = None
        if index + 1 < len(sequence):
            end_year = sequence[index + 1].get("start", {}).get("year")
        if start_year is None:
            continue
        if end_year is not None:
            windows.append(f"{lord.capitalize()} Mahadasha ({start_year}-{end_year})")
        else:
            windows.append(f"{lord.capitalize()} Mahadasha (from {start_year})")
    return windows


def _current_dasha_stack(dashas: dict[str, Any]) -> list[str]:
    return [
        value
        for value in (
            dashas.get("current_mahadasha"),
            dashas.get("current_antardasha"),
            dashas.get("current_pratyantardasha"),
        )
        if value
    ]


def _confidence_from_signal_balance(supportive_count: int, challenging_count: int) -> str:
    margin = supportive_count - challenging_count
    total = supportive_count + challenging_count
    if total <= 2:
        return "low"
    if margin >= 3:
        return "medium"
    if margin >= 1:
        return "low_to_medium"
    return "low"


def _house_sign_from_chart(chart: dict[str, Any], house_num: int) -> str | None:
    ascendant = chart.get("ascendant", {})
    asc_sign = ascendant.get("sign")
    if asc_sign not in SIGN_TO_INDEX:
        return None
    sign_idx = (SIGN_TO_INDEX[asc_sign] + house_num - 1) % 12
    return SIGN_NAMES[sign_idx]


def _planet_house(chart: dict[str, Any], planet_name: str | None) -> int | None:
    if not planet_name:
        return None
    planet_data = chart.get("planets", {}).get(planet_name)
    if not isinstance(planet_data, dict):
        return None
    house_num = planet_data.get("house")
    return int(house_num) if house_num is not None else None


def _house_occupants_from_chart(chart: dict[str, Any], house_num: int) -> list[str]:
    occupants = []
    for planet_name, planet_data in chart.get("planets", {}).items():
        if isinstance(planet_data, dict) and planet_data.get("house") == house_num:
            occupants.append(planet_name)
    return occupants
