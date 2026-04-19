from __future__ import annotations

import json
from typing import Any

from astrology_app.models import QuestionCategory
from astrology_app.question_features import build_question_features


def build_interpretation_context(
    chart_package: dict[str, Any], question: str, category: QuestionCategory, keys: list[str]
) -> dict[str, Any]:
    context = {
        "question": question,
        "category": category.value,
        "evidence": {},
        "metadata": chart_package.get("metadata", {}),
    }
    for key in keys:
        value = _get_by_path(chart_package, key)
        if value is not None:
            context["evidence"][key] = value
    if _is_longevity_question(question=question):
        context["evidence"] = _compact_longevity_evidence(chart_package)
    elif _is_health_question(category=category):
        context["evidence"] = _compact_health_evidence(chart_package)
    elif _is_marriage_timing_question(question=question, category=category):
        context["evidence"] = _compact_marriage_timing_evidence(chart_package)
    elif _is_career_question(category=category):
        context["evidence"] = _compact_career_evidence(chart_package)
    elif _is_relationship_question(question=question, category=category):
        context["evidence"] = _compact_relationship_evidence(chart_package)
    context["reading_input"] = build_question_features(
        question=question,
        category=category,
        evidence=context["evidence"],
        metadata=context["metadata"],
    )
    return context


def generate_interpretation_answer(context: dict[str, Any]) -> str:
    category = context["category"]
    if category == QuestionCategory.FAMILY.value:
        return _interpret_family_question(context)
    if category == QuestionCategory.RELATIONSHIPS.value:
        return _interpret_relationship_question(context)
    if category == QuestionCategory.TIMING.value:
        return _interpret_timing_question(context)
    return _fallback_interpretation(context)


def build_llm_prompt(context: dict[str, Any]) -> str:
    evidence_keys = ", ".join(context["evidence"].keys()) or "none"
    return (
        "You are an assistant for Hindu/Vedic astrology interpretation.\n"
        "Rules:\n"
        "1) Use only the chart evidence provided.\n"
        "2) If evidence is insufficient, say so clearly.\n"
        "3) Avoid deterministic or fear-based claims.\n"
        "4) Explain uncertainty where relevant.\n\n"
        f"User question: {context['question']}\n"
        f"Question category: {context['category']}\n"
        f"Available evidence keys: {evidence_keys}\n\n"
        "Selected chart evidence:\n"
        f"{json.dumps(context['evidence'], indent=2)}\n\n"
        "Structured reading input:\n"
        f"{json.dumps(context.get('reading_input', {}), indent=2)}\n"
    )


def _interpret_family_question(context: dict[str, Any]) -> str:
    if _is_mock_context(context):
        return (
            "This is still mock data, so I cannot read children or family prospects from it yet. "
            "Run the real `jhora` engine and I can use the actual D1, D7, house-lord, and dasha evidence."
        )

    text = context["question"].lower()
    if any(term in text for term in ("kid", "kids", "child", "children")):
        return _interpret_children_question(context)
    return _fallback_interpretation(context)


def _interpret_relationship_question(context: dict[str, Any]) -> str:
    if _is_mock_context(context):
        return (
            "This is still mock data, so I cannot read marriage or relationship timing from it yet. "
            "Run the real `jhora` engine and I can use the actual D1, D9, 7th-house, and dasha evidence."
        )

    text = context["question"].lower()
    if any(term in text for term in ("marriage", "married", "wedding", "spouse")):
        return _interpret_marriage_question(context)
    return _fallback_interpretation(context)


def _interpret_timing_question(context: dict[str, Any]) -> str:
    text = context["question"].lower()
    if any(term in text for term in ("marriage", "married", "wedding", "spouse")):
        return _interpret_marriage_question(context)
    return _fallback_interpretation(context)


def _interpret_children_question(context: dict[str, Any]) -> str:
    reading_input = context.get("reading_input", {})
    supportive = len(reading_input.get("supportive_signals", []))
    challenging = len(reading_input.get("challenging_signals", []))
    timing_note = _timing_note_from_reading_input(
        reading_input,
        positive_label="child-related significator",
    )
    score = supportive - challenging

    if score >= 4:
        conclusion = (
            "The chart shows a fairly supportive promise for children. "
            "I would read this as more consistent with having children than with denial, "
            "and more suggestive of a modest family size than an extreme outcome."
        )
    elif score >= 1:
        conclusion = (
            "The chart shows children potential, but with mixed signals. "
            "I would read this as possible, though timing or effort may matter more than average."
        )
    else:
        conclusion = (
            "The chart is mixed to challenging for a clean children indication. "
            "I would be cautious about making a firm count prediction and would frame this more in terms of delay, effort, or uncertainty."
        )

    count_line = (
        "On exact count: I would not treat this rule-based reading as precise enough to promise a fixed number. "
        "At most, the present signals lean toward a smaller number of children rather than a very large family."
    )

    evidence_points = reading_input.get("supportive_signals", []) + reading_input.get("challenging_signals", [])
    evidence_summary = " ".join(evidence_points[:5]) if evidence_points else (
        "There is not enough structured family evidence in the selected context yet."
    )

    return f"{conclusion} {count_line} Key evidence: {evidence_summary} {timing_note}".strip()


def _interpret_marriage_question(context: dict[str, Any]) -> str:
    if _is_mock_context(context):
        return (
            "This is still mock data, so I cannot read marriage timing from it yet. "
            "Run the real `jhora` engine and I can use the actual D1, D9, 7th-house, and dasha evidence."
        )

    reading_input = context.get("reading_input", {})
    supportive = len(reading_input.get("supportive_signals", []))
    challenging = len(reading_input.get("challenging_signals", []))
    windows = reading_input.get("structured_facts", {}).get("supportive_mahadasha_windows", [])
    score = supportive - challenging
    if score >= 4:
        conclusion = (
            "The chart supports marriage reasonably well, though timing still needs caution. "
            "I would read this as marriage being likely rather than denied."
        )
    elif score >= 1:
        conclusion = (
            "The marriage indicators are mixed but workable. "
            "I would read this as marriage being possible, though timing may be delayed or uneven."
        )
    else:
        conclusion = (
            "The marriage indicators are more strained than smooth. "
            "I would frame marriage timing with caution and expect delay, complexity, or a less straightforward path."
        )

    timing_line = (
        "On exact year: this rule-based layer is not precise enough to claim a single definite year with confidence. "
        "It can point to likely windows better than a single exact date."
    )
    if windows:
        timing_line += f" The most marriage-supportive Mahadasha windows in the current evidence are: {', '.join(windows[:3])}."
    else:
        timing_line += " The current exported dasha evidence does not isolate a clear timing window yet."

    evidence_points = reading_input.get("supportive_signals", []) + reading_input.get("challenging_signals", [])
    evidence_summary = " ".join(evidence_points[:5]) if evidence_points else (
        "There is not enough structured relationship evidence in the selected context yet."
    )

    if "which year" in context["question"].lower() or "when" in context["question"].lower():
        return f"{conclusion} {timing_line} Key evidence: {evidence_summary}".strip()
    return f"{conclusion} Key evidence: {evidence_summary} {timing_line}".strip()


def _timing_note_from_reading_input(reading_input: dict[str, Any], positive_label: str) -> str:
    overlap = reading_input.get("focus", {}).get("supportive_dasha_overlap", [])
    if overlap:
        return (
            f"Timing note: the current dasha stack includes a {positive_label}, "
            "so the present period may be more relevant for family developments."
        )
    return (
        "Timing note: the current dasha stack does not strongly emphasize the usual significators in this topic, "
        "so timing may depend on a later period."
    )


def _fallback_interpretation(context: dict[str, Any]) -> str:
    evidence_keys = ", ".join(context["evidence"].keys()) or "none"
    return (
        "I have selected the relevant chart evidence, but this question does not yet have a dedicated rule-based interpretation path. "
        f"Current evidence keys: {evidence_keys}. The next step would be to pass this context into an LLM or add a category-specific interpreter."
    )


def _is_mock_context(context: dict[str, Any]) -> bool:
    return context.get("metadata", {}).get("status") == "mock-data-for-development"


def _is_marriage_timing_question(*, question: str, category: QuestionCategory) -> bool:
    text = question.lower()
    marriage_terms = ("marriage", "married", "wedding", "spouse")
    timing_terms = ("when", "timing", "period", "dasha", "transit")
    return (
        category in {QuestionCategory.TIMING, QuestionCategory.RELATIONSHIPS}
        and any(term in text for term in marriage_terms)
        and any(term in text for term in timing_terms)
    )


def _is_longevity_question(*, question: str) -> bool:
    text = question.lower()
    longevity_terms = (
        "longevity",
        "lifespan",
        "life span",
        "long life",
        "short life",
        "medium life",
        "alpa",
        "miedium",
    )
    return any(term in text for term in longevity_terms)


def _is_relationship_question(*, question: str, category: QuestionCategory) -> bool:
    text = question.lower()
    relationship_terms = ("love", "love life", "relationship", "partner", "romance", "dating")
    marriage_terms = ("marriage", "married", "wedding", "spouse")
    return (
        category == QuestionCategory.RELATIONSHIPS
        and (any(term in text for term in relationship_terms) or any(term in text for term in marriage_terms))
    )


def _is_health_question(*, category: QuestionCategory) -> bool:
    return category == QuestionCategory.HEALTH


def _is_career_question(*, category: QuestionCategory) -> bool:
    return category == QuestionCategory.CAREER


def _compact_health_evidence(chart_package: dict[str, Any]) -> dict[str, Any]:
    d1 = chart_package.get("charts", {}).get("d1", {})
    d6 = chart_package.get("charts", {}).get("d6", {})
    d8 = chart_package.get("charts", {}).get("d8", {})
    d30 = chart_package.get("charts", {}).get("d30", {})
    houses = chart_package.get("derived", {}).get("houses", {})
    house_lords = chart_package.get("derived", {}).get("house_lords", {})
    dignities = chart_package.get("derived", {}).get("dignities", {})
    dashas = chart_package.get("dashas", {})
    transits = chart_package.get("transits", {}).get("current", {})
    sudarshana = chart_package.get("sudarshana_chakra", {}).get("current_cycle", {})
    return {
        "health.d1": {
            "ascendant": d1.get("ascendant", {}),
            "1st_house": houses.get("1", {}),
            "6th_house": houses.get("6", {}),
            "8th_house": houses.get("8", {}),
            "12th_house": houses.get("12", {}),
            "1st_lord": house_lords.get("1", {}),
            "6th_lord": house_lords.get("6", {}),
            "8th_lord": house_lords.get("8", {}),
            "12th_lord": house_lords.get("12", {}),
            "planets": {
                "sun": d1.get("planets", {}).get("sun", {}),
                "moon": d1.get("planets", {}).get("moon", {}),
                "mars": d1.get("planets", {}).get("mars", {}),
                "mercury": d1.get("planets", {}).get("mercury", {}),
                "jupiter": d1.get("planets", {}).get("jupiter", {}),
                "saturn": d1.get("planets", {}).get("saturn", {}),
                "rahu": d1.get("planets", {}).get("rahu", {}),
                "ketu": d1.get("planets", {}).get("ketu", {}),
            },
            "dignities": {
                "sun": dignities.get("sun", {}),
                "moon": dignities.get("moon", {}),
                "mars": dignities.get("mars", {}),
                "mercury": dignities.get("mercury", {}),
                "jupiter": dignities.get("jupiter", {}),
                "saturn": dignities.get("saturn", {}),
                "rahu": dignities.get("rahu", {}),
                "ketu": dignities.get("ketu", {}),
                "1st_lord": dignities.get(house_lords.get("1", {}).get("lord"), {}),
                "6th_lord": dignities.get(house_lords.get("6", {}).get("lord"), {}),
                "8th_lord": dignities.get(house_lords.get("8", {}).get("lord"), {}),
                "12th_lord": dignities.get(house_lords.get("12", {}).get("lord"), {}),
            },
        },
        "health.d6": _compact_planet_house_view(
            d6, ("sun", "moon", "mars", "mercury", "jupiter", "saturn", "rahu", "ketu")
        ),
        "health.d8": _compact_planet_house_view(
            d8, ("sun", "moon", "mars", "mercury", "jupiter", "saturn", "rahu", "ketu")
        ),
        "health.d30": _compact_planet_house_view(
            d30, ("sun", "moon", "mars", "mercury", "jupiter", "saturn", "rahu", "ketu")
        ),
        "health.dashas": {
            **_compact_dasha_evidence(dashas),
        },
        "health.transits": {
            "as_of": transits.get("as_of", {}),
            "jupiter": transits.get("chart", {}).get("planets", {}).get("jupiter", {}),
            "saturn": transits.get("chart", {}).get("planets", {}).get("saturn", {}),
            "mars": transits.get("chart", {}).get("planets", {}).get("mars", {}),
            "rahu": transits.get("chart", {}).get("planets", {}).get("rahu", {}),
            "ketu": transits.get("chart", {}).get("planets", {}).get("ketu", {}),
            "retrograde_planets": transits.get("retrograde_planets", []),
        },
        "health.sudarshana": {
            "reference": sudarshana.get("reference", {}),
            "retrograde_planets": sudarshana.get("retrograde_planets", []),
        },
    }


def _compact_marriage_timing_evidence(chart_package: dict[str, Any]) -> dict[str, Any]:
    d1 = chart_package.get("charts", {}).get("d1", {})
    d9 = chart_package.get("charts", {}).get("d9", {})
    houses = chart_package.get("derived", {}).get("houses", {})
    house_lords = chart_package.get("derived", {}).get("house_lords", {})
    dashas = chart_package.get("dashas", {})
    transits = chart_package.get("transits", {})
    return {
        "marriage_timing.d1": {
            "ascendant": d1.get("ascendant", {}),
            "7th_house": houses.get("7", {}),
            "7th_lord": house_lords.get("7", {}),
            "venus": d1.get("planets", {}).get("venus", {}),
        },
        "marriage_timing.d9": _compact_d9_marriage_view(d9),
        "marriage_timing.dashas": {
            **_compact_dasha_evidence(dashas),
        },
        "marriage_timing.transits": _compact_marriage_timing_transits(transits, d1),
    }


def _compact_longevity_evidence(chart_package: dict[str, Any]) -> dict[str, Any]:
    d1 = chart_package.get("charts", {}).get("d1", {})
    d8 = chart_package.get("charts", {}).get("d8", {})
    houses = chart_package.get("derived", {}).get("houses", {})
    house_lords = chart_package.get("derived", {}).get("house_lords", {})
    dignities = chart_package.get("derived", {}).get("dignities", {})
    aspects = chart_package.get("derived", {}).get("aspects", {}).get("graha_drishti", {})
    dashas = chart_package.get("dashas", {})
    return {
        "longevity.d1": {
            "ascendant": d1.get("ascendant", {}),
            "1st_house": houses.get("1", {}),
            "3rd_house": houses.get("3", {}),
            "8th_house": houses.get("8", {}),
            "1st_lord": house_lords.get("1", {}),
            "3rd_lord": house_lords.get("3", {}),
            "8th_lord": house_lords.get("8", {}),
            "saturn": d1.get("planets", {}).get("saturn", {}),
            "lagna_lord_planet": d1.get("planets", {}).get(house_lords.get("1", {}).get("lord", ""), {}),
            "8th_lord_planet": d1.get("planets", {}).get(house_lords.get("8", {}).get("lord", ""), {}),
            "dignities": {
                "saturn": dignities.get("saturn", {}),
                "1st_lord": dignities.get(house_lords.get("1", {}).get("lord"), {}),
                "3rd_lord": dignities.get(house_lords.get("3", {}).get("lord"), {}),
                "8th_lord": dignities.get(house_lords.get("8", {}).get("lord"), {}),
            },
            "relevant_aspects": {
                "saturn": aspects.get("saturn", {}),
                house_lords.get("1", {}).get("lord", ""): aspects.get(house_lords.get("1", {}).get("lord", ""), {}),
                house_lords.get("8", {}).get("lord", ""): aspects.get(house_lords.get("8", {}).get("lord", ""), {}),
            },
        },
        "longevity.d8": {
            "ascendant": d8.get("ascendant", {}),
            "saturn": d8.get("planets", {}).get("saturn", {}),
            "mars": d8.get("planets", {}).get("mars", {}),
            "8th_lord_reference": house_lords.get("8", {}),
            "planets": {
                "sun": d8.get("planets", {}).get("sun", {}),
                "moon": d8.get("planets", {}).get("moon", {}),
                "saturn": d8.get("planets", {}).get("saturn", {}),
                "mars": d8.get("planets", {}).get("mars", {}),
            },
        },
        "longevity.dashas": {
            **_compact_dasha_evidence(dashas),
        },
    }


def _compact_career_evidence(chart_package: dict[str, Any]) -> dict[str, Any]:
    d1 = chart_package.get("charts", {}).get("d1", {})
    d2 = chart_package.get("charts", {}).get("d2", {})
    d9 = chart_package.get("charts", {}).get("d9", {})
    d10 = chart_package.get("charts", {}).get("d10", {})
    house_lords = chart_package.get("derived", {}).get("house_lords", {})
    dignities = chart_package.get("derived", {}).get("dignities", {})
    aspects = chart_package.get("derived", {}).get("aspects", {}).get("graha_drishti", {})
    dashas = chart_package.get("dashas", {})
    return {
        "career.d1": {
            "ascendant": d1.get("ascendant", {}),
            "2nd_lord": house_lords.get("2", {}),
            "6th_lord": house_lords.get("6", {}),
            "10th_lord": house_lords.get("10", {}),
            "11th_lord": house_lords.get("11", {}),
            "sun": d1.get("planets", {}).get("sun", {}),
            "mercury": d1.get("planets", {}).get("mercury", {}),
            "venus": d1.get("planets", {}).get("venus", {}),
            "jupiter": d1.get("planets", {}).get("jupiter", {}),
            "saturn": d1.get("planets", {}).get("saturn", {}),
            "dignities": {
                "sun": dignities.get("sun", {}),
                "mercury": dignities.get("mercury", {}),
                "venus": dignities.get("venus", {}),
                "jupiter": dignities.get("jupiter", {}),
                "saturn": dignities.get("saturn", {}),
                "2nd_lord": dignities.get(house_lords.get("2", {}).get("lord"), {}),
                "6th_lord": dignities.get(house_lords.get("6", {}).get("lord"), {}),
                "10th_lord": dignities.get(house_lords.get("10", {}).get("lord"), {}),
                "11th_lord": dignities.get(house_lords.get("11", {}).get("lord"), {}),
            },
            "career_aspects": {
                "saturn": aspects.get("saturn", {}),
                "jupiter": aspects.get("jupiter", {}),
                "sun": aspects.get("sun", {}),
                "mercury": aspects.get("mercury", {}),
            },
        },
        "career.d2": _compact_planet_house_view(d2, ("jupiter", "venus", "mercury", "saturn")),
        "career.d9": _compact_planet_house_view(d9, ("sun", "mercury", "venus", "jupiter", "saturn")),
        "career.d10": _compact_planet_house_view(d10, ("sun", "mercury", "venus", "jupiter", "saturn")),
        "career.dashas": {
            **_compact_dasha_evidence(dashas),
        },
    }


def _compact_relationship_evidence(chart_package: dict[str, Any]) -> dict[str, Any]:
    d1 = chart_package.get("charts", {}).get("d1", {})
    d9 = chart_package.get("charts", {}).get("d9", {})
    houses = chart_package.get("derived", {}).get("houses", {})
    house_lords = chart_package.get("derived", {}).get("house_lords", {})
    dignities = chart_package.get("derived", {}).get("dignities", {})
    dashas = chart_package.get("dashas", {})
    transits = chart_package.get("transits", {})
    return {
        "relationship.d1": {
            "ascendant": d1.get("ascendant", {}),
            "5th_house": houses.get("5", {}),
            "7th_house": houses.get("7", {}),
            "5th_lord": house_lords.get("5", {}),
            "7th_lord": house_lords.get("7", {}),
            "venus": d1.get("planets", {}).get("venus", {}),
            "moon": d1.get("planets", {}).get("moon", {}),
            "jupiter": d1.get("planets", {}).get("jupiter", {}),
            "dignities": {
                "venus": dignities.get("venus", {}),
                "moon": dignities.get("moon", {}),
                "jupiter": dignities.get("jupiter", {}),
                "5th_lord": dignities.get(house_lords.get("5", {}).get("lord"), {}),
                "7th_lord": dignities.get(house_lords.get("7", {}).get("lord"), {}),
            },
        },
        "relationship.d9": _compact_d9_marriage_view(d9),
        "relationship.dashas": {
            **_compact_dasha_evidence(dashas),
        },
        "relationship.transits": _compact_marriage_timing_transits(transits, d1),
    }


def _compact_planet_house_view(chart: dict[str, Any], planet_names: tuple[str, ...]) -> dict[str, Any]:
    planets = chart.get("planets", {})
    return {
        "ascendant": chart.get("ascendant", {}),
        "planets": {
            planet_name: planets.get(planet_name, {})
            for planet_name in planet_names
        },
    }


def _compact_d9_marriage_view(d9: dict[str, Any]) -> dict[str, Any]:
    asc_sign = d9.get("ascendant", {}).get("sign")
    planets = d9.get("planets", {})
    if asc_sign is None:
        return {
            "ascendant": d9.get("ascendant", {}),
            "7th_house": {},
            "7th_lord": {},
            "venus": planets.get("venus", {}),
        }

    seventh_house_sign = _house_sign_from_chart(asc_sign, 7)
    seventh_lord_name = _sign_lord(seventh_house_sign)
    seventh_lord = planets.get(seventh_lord_name, {}) if seventh_lord_name else {}
    seventh_occupants = [
        planet_name
        for planet_name, planet_data in planets.items()
        if isinstance(planet_data, dict) and planet_data.get("house") == 7
    ]
    return {
        "ascendant": d9.get("ascendant", {}),
        "7th_house": {
            "sign": seventh_house_sign,
            "occupants": seventh_occupants,
        },
        "7th_lord": {
            "lord": seventh_lord_name,
            "placement": seventh_lord,
        },
        "venus": planets.get("venus", {}),
    }


def _slim_antardasha_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "mahadasha_lord": row.get("mahadasha_lord"),
            "antardasha_lord": row.get("antardasha_lord"),
            "start": row.get("start", {}),
            "end": row.get("end", {}),
        }
        for row in rows
    ]


def _compact_dasha_evidence(dashas: dict[str, Any]) -> dict[str, Any]:
    current_periods = dashas.get("current_periods", {})
    return {
        "birth_balance": dashas.get("birth_balance", {}),
        "current_periods": current_periods,
        "sequence": dashas.get("sequence", []),
        "nearby_mahadashas": _focused_mahadasha_table(
            dashas.get("mahadasha_table", []),
            current_periods.get("mahadasha", {}),
        ),
        "nearby_antardashas": _focused_antardasha_table(
            dashas.get("antardasha_table", []),
            current_periods.get("antardasha", {}),
        ),
    }


def _focused_mahadasha_table(rows: list[dict[str, Any]], current_period: dict[str, Any], radius: int = 1) -> list[dict[str, Any]]:
    slim_rows = [
        {
            "mahadasha_lord": row.get("mahadasha_lord"),
            "start": row.get("start", {}),
            "end": row.get("end", {}),
        }
        for row in rows
    ]
    index = _find_period_index(slim_rows, current_period)
    if index is None:
        return slim_rows[: min(3, len(slim_rows))]
    start = max(0, index - radius)
    end = min(len(slim_rows), index + radius + 1)
    return slim_rows[start:end]


def _focused_antardasha_table(rows: list[dict[str, Any]], current_period: dict[str, Any], radius: int = 2) -> list[dict[str, Any]]:
    slim_rows = _slim_antardasha_table(rows)
    index = _find_period_index(slim_rows, current_period)
    if index is None:
        return slim_rows[: min(5, len(slim_rows))]
    start = max(0, index - radius)
    end = min(len(slim_rows), index + radius + 1)
    return slim_rows[start:end]


def _find_period_index(rows: list[dict[str, Any]], current_period: dict[str, Any]) -> int | None:
    current_start = current_period.get("start", {})
    current_end = current_period.get("end", {})
    if not current_start or not current_end:
        return None
    for index, row in enumerate(rows):
        if row.get("start") == current_start and row.get("end") == current_end:
            return index
    return None


def _compact_marriage_timing_transits(transits: dict[str, Any], d1: dict[str, Any]) -> dict[str, Any]:
    current = transits.get("current", {})
    planets = current.get("chart", {}).get("planets", {})
    natal_venus = d1.get("planets", {}).get("venus", {})
    return {
        "optional": True,
        "as_of": current.get("as_of", {}),
        "jupiter": planets.get("jupiter", {}),
        "saturn": planets.get("saturn", {}),
        "reference_to_natal_venus": {
            "venus_sign": natal_venus.get("sign"),
            "venus_house": natal_venus.get("house"),
        },
    }


def _house_sign_from_chart(asc_sign: str, house_num: int) -> str | None:
    signs = [
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
    if asc_sign not in signs:
        return None
    return signs[(signs.index(asc_sign) + house_num - 1) % 12]


def _sign_lord(sign_name: str | None) -> str | None:
    sign_lords = {
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
    return sign_lords.get(sign_name)


def _get_by_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current
