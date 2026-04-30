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
    if question_type == "career":
        return _career_features(evidence, metadata)
    if question_type == "wealth":
        return _wealth_features(evidence, metadata)
    if question_type == "health":
        return _health_features(evidence, metadata)
    if question_type == "longevity":
        return _longevity_features(evidence, metadata)

    return {
        "mode": "real",
        "question_type": question_type,
        "ready_for_model": False,
        "reason": "no-specialized-feature-extractor-yet",
        "available_evidence_keys": sorted(evidence.keys()),
    }


def _question_type(question: str, category: QuestionCategory) -> str:
    text = question.lower()
    if any(
        term in text
        for term in ("longevity", "lifespan", "life span", "long life", "short life", "medium life", "alpa", "miedium")
    ):
        return "longevity"
    if category == QuestionCategory.CAREER and any(
        term in text for term in ("money", "finance", "finances", "wealth", "income", "earning")
    ):
        return "wealth"
    if category == QuestionCategory.FAMILY and any(
        term in text for term in ("kid", "kids", "child", "children")
    ):
        return "children"
    if category in {QuestionCategory.RELATIONSHIPS, QuestionCategory.TIMING} and any(
        term in text for term in ("marriage", "married", "wedding", "spouse", "love", "relationship", "partner", "love life")
    ):
        return "marriage"
    return category.value


def _career_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    compact = evidence.get("career.d1")
    if isinstance(compact, dict):
        return _compact_career_features(evidence, metadata)

    house_lords = evidence.get("derived.house_lords", {})
    dignities = evidence.get("derived.dignities", {})
    aspects = evidence.get("derived.aspects", {}).get("graha_drishti", {})
    dashas = evidence.get("dashas", {})
    d1 = evidence.get("charts.d1", {})
    d2 = evidence.get("charts.d2", {})
    d9 = evidence.get("charts.d9", {})
    d10 = evidence.get("charts.d10", {})
    d60 = evidence.get("charts.d60", {})

    second_lord = house_lords.get("2", {})
    eleventh_lord = house_lords.get("11", {})
    tenth_lord = house_lords.get("10", {})
    ninth_lord = house_lords.get("9", {})

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    for lord_label, lord_data in (
        ("2nd lord", second_lord),
        ("11th lord", eleventh_lord),
        ("10th lord", tenth_lord),
        ("9th lord", ninth_lord),
    ):
        lord_name = lord_data.get("lord")
        placement = lord_data.get("lord_placement", {})
        _collect_lord_signals(
            lord_name=lord_name,
            lord_house=placement.get("house"),
            lord_dignity=dignities.get(lord_name, {}).get("dignity"),
            house_label=lord_label,
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for chart_label, chart in (
        ("D1", d1),
        ("D2", d2),
        ("D9", d9),
        ("D10", d10),
        ("D60", d60),
    ):
        for planet_name in ("jupiter", "venus", "mercury", "saturn", "moon", "sun"):
            _collect_planet_signals(
                planet_name=planet_name,
                dignity=dignities.get(planet_name, {}).get("dignity") if chart_label == "D1" else None,
                house_num=_planet_house(chart, planet_name),
                chart_label=chart_label,
                supportive_signals=supportive_signals,
                challenging_signals=challenging_signals,
            )

    second_lord_name = second_lord.get("lord")
    if second_lord_name and aspects.get("saturn", {}).get("planets") and second_lord_name in aspects.get("saturn", {}).get("planets", []):
        challenging_signals.append(f"Saturn directly aspects the 2nd-house zone through {second_lord_name}.")

    current_stack = _current_dasha_stack(dashas)
    wealth_significators = sorted(
        signal
        for signal in {
            "jupiter",
            "venus",
            "mercury",
            second_lord.get("lord"),
            eleventh_lord.get("lord"),
            tenth_lord.get("lord"),
        }
        if signal
    )
    current_overlap = sorted(set(current_stack) & set(wealth_significators))
    windows = _supportive_mahadasha_windows(dashas, set(wealth_significators))
    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "career",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "wealth_houses": ["2", "11"],
            "career_house": "10",
            "current_dasha_stack": current_stack,
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_wealth_lords": {
                "2": second_lord,
                "9": ninth_lord,
                "10": tenth_lord,
                "11": eleventh_lord,
            },
            "d1_planet_house_placements": _planet_house_map(d1),
            "d2_planet_house_placements": _planet_house_map(d2),
            "d9_planet_house_placements": _planet_house_map(d9),
            "d10_planet_house_placements": _planet_house_map(d10),
            "d60_planet_house_placements": _planet_house_map(d60),
            "d1_dignities": dignities,
            "d1_aspects": aspects,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Assess wealth trends in phases, not as one fixed outcome.",
            "Use D2 and D10 for money and career execution, D9 for strength and maturity, and D60 only as a secondary karmic background layer.",
            "Explicitly mention the current pratyantardasha when discussing the present struggle or short-term period.",
            "Use only the provided structured facts and selected evidence.",
        ],
        "metadata": metadata,
    }


def _wealth_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    compact = evidence.get("career.d1")
    if isinstance(compact, dict):
        return _compact_wealth_features(evidence, metadata)

    features = _career_features(evidence, metadata)
    features["question_type"] = "wealth"
    features["focus"] = {
        "wealth_houses": ["2", "4", "11", "12"],
        "liquidity_planets": ["moon", "mercury", "jupiter"],
        "debt_indicators": ["6th_house", "8th_house", "rahu"],
        "dasha_wealth_lords": ["venus", "jupiter", "moon"],
    }
    return features


def _compact_career_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    d1 = evidence.get("career.d1", {})
    d2 = evidence.get("career.d2", {})
    d9 = evidence.get("career.d9", {})
    d10 = evidence.get("career.d10", {})
    dashas = evidence.get("career.dashas", {})
    transit_window = evidence.get("career.transit_window", {})

    dignities = d1.get("dignities", {})
    aspects = d1.get("career_aspects", {})
    second_lord = d1.get("2nd_lord", {})
    sixth_lord = d1.get("6th_lord", {})
    tenth_lord = d1.get("10th_lord", {})
    eleventh_lord = d1.get("11th_lord", {})

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    for lord_label, lord_key, lord_data in (
        ("2nd lord", "2nd_lord", second_lord),
        ("6th lord", "6th_lord", sixth_lord),
        ("10th lord", "10th_lord", tenth_lord),
        ("11th lord", "11th_lord", eleventh_lord),
    ):
        lord_name = lord_data.get("lord")
        placement = lord_data.get("lord_placement", {})
        _collect_lord_signals(
            lord_name=lord_name,
            lord_house=placement.get("house"),
            lord_dignity=dignities.get(lord_key, {}).get("dignity"),
            house_label=lord_label,
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for chart_label, chart in (("D1", d1), ("D2", d2), ("D9", d9), ("D10", d10)):
        planets = chart.get("planets", chart)
        for planet_name in ("sun", "mercury", "venus", "jupiter", "saturn"):
            planet_data = planets.get(planet_name, {})
            _collect_planet_signals(
                planet_name=planet_name,
                dignity=dignities.get(planet_name, {}).get("dignity") if chart_label == "D1" else None,
                house_num=planet_data.get("house"),
                chart_label=chart_label,
                supportive_signals=supportive_signals,
                challenging_signals=challenging_signals,
            )

    second_lord_name = second_lord.get("lord")
    saturn_aspects = aspects.get("saturn", {}).get("planets", [])
    if second_lord_name and second_lord_name in saturn_aspects:
        challenging_signals.append(f"Saturn directly aspects the 2nd-house zone through {second_lord_name}.")

    current_stack = _current_dasha_stack(dashas)
    career_significators = sorted(
        signal
        for signal in {
            "sun",
            "mercury",
            "venus",
            "jupiter",
            "saturn",
            second_lord.get("lord"),
            sixth_lord.get("lord"),
            tenth_lord.get("lord"),
            eleventh_lord.get("lord"),
        }
        if signal
    )
    current_overlap = sorted(set(current_stack) & set(career_significators))
    windows = _supportive_mahadasha_windows(dashas, set(career_significators))
    transit_window_summary = _career_transit_window_summary(transit_window)
    if transit_window_summary:
        supportive_signals.append(
            f"Transit window loaded for {transit_window_summary.get('requested_range', {}).get('start_date')} "
            f"to {transit_window_summary.get('requested_range', {}).get('end_date')}."
        )
    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "career",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "career_houses": ["2", "6", "10", "11"],
            "current_dasha_stack": current_stack,
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_career_lords": {
                "2": second_lord,
                "6": sixth_lord,
                "10": tenth_lord,
                "11": eleventh_lord,
            },
            "d1_core_planets": {
                "sun": d1.get("sun", {}),
                "mercury": d1.get("mercury", {}),
                "venus": d1.get("venus", {}),
                "jupiter": d1.get("jupiter", {}),
                "saturn": d1.get("saturn", {}),
            },
            "d2_core_planets": d2.get("planets", {}),
            "d9_core_planets": d9.get("planets", {}),
            "d10_core_planets": d10.get("planets", {}),
            "d1_dignities": dignities,
            "career_aspects": aspects,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
            "transit_window_summary": transit_window_summary,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Focus on profession, work pattern, and career growth rather than unrelated life areas.",
            "Use D10 as the main confirmation chart and D2 only as support for income and resources.",
            "Discuss timing as likely periods, not exact promises.",
            "If a transit window is present, use it for short-period trend calls instead of relying only on the current transit snapshot.",
        ],
        "metadata": metadata,
    }


def _compact_wealth_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    d1 = evidence.get("career.d1", {})
    d2 = evidence.get("career.d2", {})
    d4 = evidence.get("career.d4", {})
    d9 = evidence.get("career.d9", {})
    d10 = evidence.get("career.d10", {})
    ashtakavarga = evidence.get("career.ashtakavarga", {})
    special_conditions = evidence.get("career.special_conditions", {})
    dashas = evidence.get("career.dashas", {})

    dignities = d1.get("dignities", {})
    aspects = d1.get("career_aspects", {})
    second_house = d1.get("2nd_house", {})
    fourth_house = d1.get("4th_house", {})
    sixth_house = d1.get("6th_house", {})
    eighth_house = d1.get("8th_house", {})
    eleventh_house = d1.get("11th_house", {})
    twelfth_house = d1.get("12th_house", {})
    second_lord = d1.get("2nd_lord", {})
    fourth_lord = d1.get("4th_lord", {})
    sixth_lord = d1.get("6th_lord", {})
    eighth_lord = d1.get("8th_lord", {})
    eleventh_lord = d1.get("11th_lord", {})
    twelfth_lord = d1.get("12th_lord", {})
    wealth_dasha_links = dashas.get("wealth_lord_links", [])
    gandanta = special_conditions.get("gandanta", [])
    ashtakavarga_houses = ashtakavarga.get("sav_by_house", {})

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    for house_num, label, house_data in (
        ("2", "D1 2nd house", second_house),
        ("4", "D1 4th house", fourth_house),
        ("11", "D1 11th house", eleventh_house),
        ("12", "D1 12th house", twelfth_house),
        ("6", "D1 6th house", sixth_house),
        ("8", "D1 8th house", eighth_house),
    ):
        _collect_house_signals(
            house_data=house_data,
            label=label,
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for lord_label, lord_key, lord_data in (
        ("2nd lord", "2nd_lord", second_lord),
        ("4th lord", "4th_lord", fourth_lord),
        ("6th lord", "6th_lord", sixth_lord),
        ("8th lord", "8th_lord", eighth_lord),
        ("11th lord", "11th_lord", eleventh_lord),
        ("12th lord", "12th_lord", twelfth_lord),
    ):
        lord_name = lord_data.get("lord")
        placement = lord_data.get("lord_placement", {})
        _collect_lord_signals(
            lord_name=lord_name,
            lord_house=placement.get("house"),
            lord_dignity=dignities.get(lord_key, {}).get("dignity"),
            house_label=lord_label,
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for chart_label, chart in (("D1", d1), ("D2", d2), ("D4", d4), ("D9", d9), ("D10", d10)):
        planets = chart.get("planets", chart)
        for planet_name in ("moon", "mercury", "venus", "jupiter", "saturn", "rahu"):
            planet_data = planets.get(planet_name, {})
            _collect_planet_signals(
                planet_name=planet_name,
                dignity=dignities.get(planet_name, {}).get("dignity") if chart_label == "D1" else None,
                house_num=planet_data.get("house"),
                chart_label=chart_label,
                supportive_signals=supportive_signals,
                challenging_signals=challenging_signals,
            )

    second_lord_name = second_lord.get("lord")
    saturn_aspects = aspects.get("saturn", {}).get("planets", [])
    if second_lord_name and second_lord_name in saturn_aspects:
        challenging_signals.append(f"Saturn directly aspects the 2nd-house zone through {second_lord_name}.")

    current_stack = _current_dasha_stack(dashas)
    wealth_lords = ["venus", "jupiter", "moon"]
    windows = _supportive_mahadasha_windows(dashas, set(wealth_lords))

    for house_num, label in (("2", "2nd"), ("11", "11th")):
        points = ashtakavarga_houses.get(house_num, {}).get("points")
        if points is None:
            continue
        if points >= 28:
            supportive_signals.append(f"Ashtakavarga supports the {label} house with {points} SAV points.")
        elif points <= 24:
            challenging_signals.append(f"Ashtakavarga weakens the {label} house with only {points} SAV points.")

    for item in wealth_dasha_links:
        tags = set(item.get("link_tags", []))
        active_lord = item.get("active_lord")
        if item.get("is_direct_wealth_lord"):
            supportive_signals.append(f"Current {item.get('period')} lord {active_lord} is a direct wealth lord.")
        elif tags & {"conjunct_2nd_lord", "conjunct_11th_lord", "aspects_2nd_lord", "aspects_11th_lord"}:
            supportive_signals.append(
                f"Current {item.get('period')} lord {active_lord} links with wealth lords via {', '.join(sorted(tags))}."
            )
        elif item.get("active_lord_house") in {6, 8, 12}:
            challenging_signals.append(
                f"Current {item.get('period')} lord {active_lord} operates from house {item.get('active_lord_house')}."
            )

    if gandanta:
        flagged = ", ".join(item.get("planet", "") for item in gandanta[:3] if item.get("planet"))
        challenging_signals.append(f"Gandanta sensitivity is present for: {flagged}.")

    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "wealth",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "wealth_houses": ["2", "4", "11", "12"],
            "liquidity_planets": ["moon", "mercury", "jupiter"],
            "debt_indicators": ["6th_house", "8th_house", "rahu"],
            "dasha_wealth_lords": wealth_lords,
        },
        "structured_facts": {
            "d1_wealth_lords": {
                "2": second_lord,
                "4": fourth_lord,
                "6": sixth_lord,
                "8": eighth_lord,
                "11": eleventh_lord,
                "12": twelfth_lord,
            },
            "d1_wealth_houses": {
                "2": second_house,
                "4": fourth_house,
                "6": sixth_house,
                "8": eighth_house,
                "11": eleventh_house,
                "12": twelfth_house,
            },
            "d1_core_planets": {
                "moon": d1.get("moon", {}),
                "mercury": d1.get("mercury", {}),
                "venus": d1.get("venus", {}),
                "jupiter": d1.get("jupiter", {}),
                "saturn": d1.get("saturn", {}),
                "rahu": d1.get("rahu", {}),
            },
            "d2_core_planets": d2.get("planets", {}),
            "d4_asset_planets": d4.get("planets", {}),
            "d9_core_planets": d9.get("planets", {}),
            "d10_core_planets": d10.get("planets", {}),
            "d1_dignities": dignities,
            "career_aspects": aspects,
            "ashtakavarga_summary": ashtakavarga_houses,
            "gandanta": gandanta,
            "current_dasha_wealth_links": wealth_dasha_links,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Focus on wealth accumulation, cash flow, savings pressure, and debt exposure rather than generic career themes.",
            "Use D2 for liquid resources, D4 for assets/property, and D1 for house-lord context without drifting into unrelated career themes.",
            "Use only the compact Ashtakavarga and Gandanta summaries provided here; do not invent extra strength systems.",
            "Discuss timing as likely financial phases, not exact promises.",
        ],
        "metadata": metadata,
    }


def _health_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    compact = evidence.get("health.d1")
    if isinstance(compact, dict):
        return _compact_health_features(evidence, metadata)

    houses = evidence.get("derived.houses", {})
    house_lords = evidence.get("derived.house_lords", {})
    dignities = evidence.get("derived.dignities", {})
    dashas = evidence.get("dashas", {})
    d1 = evidence.get("charts.d1", {})
    d6 = evidence.get("charts.d6", {})
    d8 = evidence.get("charts.d8", {})
    d30 = evidence.get("charts.d30", {})
    sudarshana = evidence.get("sudarshana_chakra", {}).get("current_cycle", {})
    transits = evidence.get("transits", {}).get("current", {})

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    for house_num, label in (("1", "Lagna"), ("6", "6th house"), ("8", "8th house"), ("12", "12th house")):
        house_data = houses.get(house_num, {})
        _collect_house_signals(
            house_data=house_data,
            label=f"D1 {label}",
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

        lord_data = house_lords.get(house_num, {})
        lord_name = lord_data.get("lord")
        placement = lord_data.get("lord_placement", {})
        _collect_lord_signals(
            lord_name=lord_name,
            lord_house=placement.get("house"),
            lord_dignity=dignities.get(lord_name, {}).get("dignity"),
            house_label=f"{label} lord",
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for chart_label, chart in (("D1", d1), ("D6", d6), ("D8", d8), ("D30", d30)):
        for planet_name in ("sun", "moon", "mars", "mercury", "saturn", "rahu", "ketu", "jupiter"):
            _collect_planet_signals(
                planet_name=planet_name,
                dignity=dignities.get(planet_name, {}).get("dignity") if chart_label == "D1" else None,
                house_num=_planet_house(chart, planet_name),
                chart_label=chart_label,
                supportive_signals=supportive_signals,
                challenging_signals=challenging_signals,
            )

    transit_retrogrades = transits.get("retrograde_planets", [])
    if transit_retrogrades:
        challenging_signals.append(
            f"Current gochara retrogrades active: {', '.join(transit_retrogrades)}."
        )

    current_stack = _current_dasha_stack(dashas)
    sensitive_lords = sorted(
        signal
        for signal in {
            house_lords.get("1", {}).get("lord"),
            house_lords.get("6", {}).get("lord"),
            house_lords.get("8", {}).get("lord"),
            house_lords.get("12", {}).get("lord"),
            "saturn",
            "mars",
            "rahu",
            "ketu",
            "jupiter",
        }
        if signal
    )
    current_overlap = sorted(set(current_stack) & set(sensitive_lords))
    windows = _supportive_mahadasha_windows(dashas, {"jupiter", house_lords.get("1", {}).get("lord")})
    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "health",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "primary_houses": ["1", "6", "8", "12"],
            "current_dasha_stack": current_stack,
            "sensitive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_health_houses": {
                "1": houses.get("1", {}),
                "6": houses.get("6", {}),
                "8": houses.get("8", {}),
                "12": houses.get("12", {}),
            },
            "d1_health_lords": {
                "1": house_lords.get("1", {}),
                "6": house_lords.get("6", {}),
                "8": house_lords.get("8", {}),
                "12": house_lords.get("12", {}),
            },
            "d1_planet_house_placements": _planet_house_map(d1),
            "d6_planet_house_placements": _planet_house_map(d6),
            "d8_planet_house_placements": _planet_house_map(d8),
            "d30_planet_house_placements": _planet_house_map(d30),
            "d1_dignities": dignities,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
            "current_transits": {
                "as_of": transits.get("as_of", {}),
                "planet_house_placements": _planet_house_map(transits.get("chart", {})),
                "retrograde_planets": transit_retrogrades,
            },
            "sudarshana_chakra_current_cycle": sudarshana,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Do not make medical diagnoses or certainty claims.",
            "Describe health periods as supportive, sensitive, or cautionary windows.",
            "Use D6, D8, D30, current dasha stack, current transits, and Sudarshana Chakra only as the provided evidence supports.",
            "If discussing the present period, explicitly mention the current pratyantardasha.",
        ],
        "metadata": metadata,
    }


def _compact_health_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    d1 = evidence.get("health.d1", {})
    d6 = evidence.get("health.d6", {})
    d8 = evidence.get("health.d8", {})
    d30 = evidence.get("health.d30", {})
    dashas = evidence.get("health.dashas", {})
    transits = evidence.get("health.transits", {})
    sudarshana = evidence.get("health.sudarshana", {})

    houses = {
        "1": d1.get("1st_house", {}),
        "6": d1.get("6th_house", {}),
        "8": d1.get("8th_house", {}),
        "12": d1.get("12th_house", {}),
    }
    house_lords = {
        "1": d1.get("1st_lord", {}),
        "6": d1.get("6th_lord", {}),
        "8": d1.get("8th_lord", {}),
        "12": d1.get("12th_lord", {}),
    }
    dignities = d1.get("dignities", {})

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    for house_num, label in (("1", "Lagna"), ("6", "6th house"), ("8", "8th house"), ("12", "12th house")):
        house_data = houses.get(house_num, {})
        _collect_house_signals(
            house_data=house_data,
            label=f"D1 {label}",
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

        lord_data = house_lords.get(house_num, {})
        lord_key = f"{house_num}th_lord" if house_num not in {"1", "6", "8"} else {
            "1": "1st_lord",
            "6": "6th_lord",
            "8": "8th_lord",
        }[house_num]
        placement = lord_data.get("lord_placement", {})
        _collect_lord_signals(
            lord_name=lord_data.get("lord"),
            lord_house=placement.get("house"),
            lord_dignity=dignities.get(lord_key, {}).get("dignity"),
            house_label=f"{label} lord",
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for chart_label, chart in (("D1", d1), ("D6", d6), ("D8", d8), ("D30", d30)):
        planets = chart.get("planets", {})
        for planet_name in ("sun", "moon", "mars", "mercury", "saturn", "rahu", "ketu", "jupiter"):
            planet_data = planets.get(planet_name, {})
            _collect_planet_signals(
                planet_name=planet_name,
                dignity=dignities.get(planet_name, {}).get("dignity") if chart_label == "D1" else None,
                house_num=planet_data.get("house"),
                chart_label=chart_label,
                supportive_signals=supportive_signals,
                challenging_signals=challenging_signals,
            )

    transit_retrogrades = transits.get("retrograde_planets", [])
    if transit_retrogrades:
        challenging_signals.append(
            f"Current gochara retrogrades active: {', '.join(transit_retrogrades)}."
        )

    current_stack = _current_dasha_stack(dashas)
    sensitive_lords = sorted(
        signal
        for signal in {
            house_lords.get("1", {}).get("lord"),
            house_lords.get("6", {}).get("lord"),
            house_lords.get("8", {}).get("lord"),
            house_lords.get("12", {}).get("lord"),
            "saturn",
            "mars",
            "rahu",
            "ketu",
            "jupiter",
        }
        if signal
    )
    current_overlap = sorted(set(current_stack) & set(sensitive_lords))
    windows = _supportive_mahadasha_windows(dashas, {"jupiter", house_lords.get("1", {}).get("lord")})
    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "health",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "primary_houses": ["1", "6", "8", "12"],
            "current_dasha_stack": current_stack,
            "sensitive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_health_houses": houses,
            "d1_health_lords": house_lords,
            "d1_core_planets": d1.get("planets", {}),
            "d6_core_planets": d6.get("planets", {}),
            "d8_core_planets": d8.get("planets", {}),
            "d30_core_planets": d30.get("planets", {}),
            "d1_dignities": dignities,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
            "current_transits": transits,
            "sudarshana_chakra_current_cycle": sudarshana,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Do not make medical diagnoses or certainty claims.",
            "Describe health periods as supportive, sensitive, or cautionary windows.",
            "Use only the structured facts and signals provided.",
            "If discussing the present period, explicitly mention the current pratyantardasha.",
        ],
        "metadata": metadata,
    }


def _longevity_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    d1 = evidence.get("longevity.d1", {})
    d8 = evidence.get("longevity.d8", {})
    dashas = evidence.get("longevity.dashas", {})

    first_house = d1.get("1st_house", {})
    third_house = d1.get("3rd_house", {})
    eighth_house = d1.get("8th_house", {})
    first_lord = d1.get("1st_lord", {})
    third_lord = d1.get("3rd_lord", {})
    eighth_lord = d1.get("8th_lord", {})
    dignities = d1.get("dignities", {})

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    for label, house_data in (
        ("D1 1st house", first_house),
        ("D1 3rd house", third_house),
        ("D1 8th house", eighth_house),
    ):
        _collect_house_signals(
            house_data=house_data,
            label=label,
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    for label, lord_key, lord_data in (
        ("1st lord", "1st_lord", first_lord),
        ("3rd lord", "3rd_lord", third_lord),
        ("8th lord", "8th_lord", eighth_lord),
    ):
        _collect_lord_signals(
            lord_name=lord_data.get("lord"),
            lord_house=lord_data.get("lord_placement", {}).get("house"),
            lord_dignity=dignities.get(lord_key, {}).get("dignity"),
            house_label=label,
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    _collect_planet_signals(
        planet_name="saturn",
        dignity=dignities.get("saturn", {}).get("dignity"),
        house_num=d1.get("saturn", {}).get("house"),
        chart_label="D1",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="saturn",
        dignity=None,
        house_num=d8.get("saturn", {}).get("house"),
        chart_label="D8",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="mars",
        dignity=None,
        house_num=d8.get("mars", {}).get("house"),
        chart_label="D8",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    longevity_significators = sorted(
        signal
        for signal in {
            "saturn",
            first_lord.get("lord"),
            third_lord.get("lord"),
            eighth_lord.get("lord"),
        }
        if signal
    )
    current_stack = _current_dasha_stack(dashas)
    current_overlap = sorted(set(current_stack) & set(longevity_significators))
    windows = _supportive_mahadasha_windows(dashas, set(longevity_significators))
    confidence = _confidence_from_signal_balance(
        len(supportive_signals),
        len(challenging_signals),
    )

    return {
        "mode": "real",
        "question_type": "longevity",
        "ready_for_model": True,
        "confidence": confidence,
        "focus": {
            "primary_houses": ["1", "3", "8"],
            "primary_significators": longevity_significators,
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_longevity_houses": {
                "1": first_house,
                "3": third_house,
                "8": eighth_house,
            },
            "d1_longevity_lords": {
                "1": first_lord,
                "3": third_lord,
                "8": eighth_lord,
            },
            "d1_saturn": d1.get("saturn", {}),
            "d8_core": {
                "ascendant": d8.get("ascendant", {}),
                "saturn": d8.get("saturn", {}),
                "mars": d8.get("mars", {}),
                "planets": d8.get("planets", {}),
            },
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Do not make fatalistic or deterministic death predictions.",
            "Frame the reading in broad longevity tendency only, such as shorter, medium, or longer life indications.",
            "Use only the provided structured facts and signals.",
        ],
        "metadata": metadata,
    }


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
    compact = evidence.get("marriage_timing.d1")
    if isinstance(compact, dict):
        return _marriage_timing_features(evidence, metadata)
    compact_relationship = evidence.get("relationship.d1")
    if isinstance(compact_relationship, dict):
        return _relationship_features(evidence, metadata)

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


def _relationship_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    d1 = evidence.get("relationship.d1", {})
    d9 = evidence.get("relationship.d9", {})
    dashas = evidence.get("relationship.dashas", {})

    fifth_house = d1.get("5th_house", {})
    seventh_house = d1.get("7th_house", {})
    fifth_lord = d1.get("5th_lord", {})
    seventh_lord = d1.get("7th_lord", {})
    dignities = d1.get("dignities", {})

    fifth_lord_name = fifth_lord.get("lord")
    fifth_lord_house = fifth_lord.get("lord_placement", {}).get("house")
    seventh_lord_name = seventh_lord.get("lord")
    seventh_lord_house = seventh_lord.get("lord_placement", {}).get("house")

    supportive_signals: list[str] = []
    challenging_signals: list[str] = []

    _collect_house_signals(
        house_data=fifth_house,
        label="D1 5th house",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_house_signals(
        house_data=seventh_house,
        label="D1 7th house",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=fifth_lord_name,
        lord_house=fifth_lord_house,
        lord_dignity=dignities.get("5th_lord", {}).get("dignity"),
        house_label="5th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=seventh_lord_name,
        lord_house=seventh_lord_house,
        lord_dignity=dignities.get("7th_lord", {}).get("dignity"),
        house_label="7th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    for planet_name in ("venus", "moon", "jupiter"):
        _collect_planet_signals(
            planet_name=planet_name,
            dignity=dignities.get(planet_name, {}).get("dignity"),
            house_num=d1.get(planet_name, {}).get("house"),
            chart_label="D1",
            supportive_signals=supportive_signals,
            challenging_signals=challenging_signals,
        )

    d9_fifth_sign = d9.get("5th_house", {}).get("sign")
    d9_fifth_occupants = d9.get("5th_house", {}).get("occupants", [])
    d9_fifth_lord = d9.get("5th_lord", {}).get("lord")
    d9_fifth_lord_house = d9.get("5th_lord", {}).get("placement", {}).get("house")
    d9_fifth_lord_strength = d9.get("5th_lord", {}).get("sign_strength")
    d9_seventh_sign = d9.get("7th_house", {}).get("sign")
    d9_seventh_occupants = d9.get("7th_house", {}).get("occupants", [])
    d9_seventh_lord = d9.get("7th_lord", {}).get("lord")
    d9_seventh_lord_house = d9.get("7th_lord", {}).get("placement", {}).get("house")
    d9_seventh_lord_strength = d9.get("7th_lord", {}).get("sign_strength")
    d9_ninth_sign = d9.get("9th_house", {}).get("sign")
    d9_ninth_occupants = d9.get("9th_house", {}).get("occupants", [])
    d9_ninth_lord = d9.get("9th_lord", {}).get("lord")
    d9_ninth_lord_house = d9.get("9th_lord", {}).get("placement", {}).get("house")
    d9_ninth_lord_strength = d9.get("9th_lord", {}).get("sign_strength")
    d9_venus = d9.get("venus", {})
    d9_venus_house = d9_venus.get("house")
    d9_venus_strength = d9_venus.get("sign_strength")

    if d9_fifth_occupants:
        supportive_signals.append(f"D9 5th house occupants: {', '.join(d9_fifth_occupants)}.")
    if d9_seventh_occupants:
        supportive_signals.append(f"D9 7th house occupants: {', '.join(d9_seventh_occupants)}.")
    if d9_ninth_occupants:
        supportive_signals.append(f"D9 9th house occupants: {', '.join(d9_ninth_occupants)}.")
    _collect_lord_signals(
        lord_name=d9_fifth_lord,
        lord_house=d9_fifth_lord_house,
        lord_dignity=d9_fifth_lord_strength,
        house_label="D9 5th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=d9_seventh_lord,
        lord_house=d9_seventh_lord_house,
        lord_dignity=d9_seventh_lord_strength,
        house_label="D9 7th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=d9_ninth_lord,
        lord_house=d9_ninth_lord_house,
        lord_dignity=d9_ninth_lord_strength,
        house_label="D9 9th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="venus",
        dignity=d9_venus_strength,
        house_num=d9_venus_house,
        chart_label="D9",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    relationship_significators = sorted(
        signal for signal in {"venus", "moon", "jupiter", fifth_lord_name, seventh_lord_name} if signal
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
            "primary_houses": ["5", "7"],
            "primary_lords": [lord for lord in (fifth_lord_name, seventh_lord_name) if lord],
            "key_significators": ["venus", "moon", "jupiter"],
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_5th_house": fifth_house,
            "d1_7th_house": seventh_house,
            "d1_5th_lord": fifth_lord,
            "d1_7th_lord": seventh_lord,
            "d1_venus": d1.get("venus", {}),
            "d1_moon": d1.get("moon", {}),
            "d1_jupiter": d1.get("jupiter", {}),
            "d9_5th_house_sign": d9_fifth_sign,
            "d9_5th_house_occupants": d9_fifth_occupants,
            "d9_5th_lord": {
                "lord": d9_fifth_lord,
                "house": d9_fifth_lord_house,
                "sign_strength": d9_fifth_lord_strength,
            },
            "d9_7th_house_sign": d9_seventh_sign,
            "d9_7th_house_occupants": d9_seventh_occupants,
            "d9_7th_lord": {
                "lord": d9_seventh_lord,
                "house": d9_seventh_lord_house,
                "sign_strength": d9_seventh_lord_strength,
            },
            "d9_9th_house_sign": d9_ninth_sign,
            "d9_9th_house_occupants": d9_ninth_occupants,
            "d9_9th_lord": {
                "lord": d9_ninth_lord,
                "house": d9_ninth_lord_house,
                "sign_strength": d9_ninth_lord_strength,
            },
            "d9_venus": d9_venus,
            "current_dasha_stack": current_stack,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "For love-life questions, emphasize relationship pattern and quality before timing.",
            "Keep timing discussion to likely windows, not exact promises.",
            "Use only the structured facts and signals provided.",
        ],
        "metadata": metadata,
    }


def _marriage_timing_features(evidence: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    d1 = evidence.get("marriage_timing.d1", {})
    d9 = evidence.get("marriage_timing.d9", {})
    dashas = evidence.get("marriage_timing.dashas", {})
    transits = evidence.get("marriage_timing.transits", {})

    seventh_house = d1.get("7th_house", {})
    seventh_lord = d1.get("7th_lord", {})
    seventh_lord_name = seventh_lord.get("lord")
    seventh_lord_house = seventh_lord.get("lord_placement", {}).get("house")
    venus_house_d1 = d1.get("venus", {}).get("house")
    d9_fifth_lord = d9.get("5th_lord", {}).get("lord")
    d9_fifth_lord_house = d9.get("5th_lord", {}).get("placement", {}).get("house")
    d9_fifth_lord_strength = d9.get("5th_lord", {}).get("sign_strength")
    d9_seventh_lord = d9.get("7th_lord", {}).get("lord")
    d9_seventh_lord_house = d9.get("7th_lord", {}).get("placement", {}).get("house")
    d9_seventh_lord_strength = d9.get("7th_lord", {}).get("sign_strength")
    d9_venus = d9.get("venus", {})
    d9_venus_house = d9_venus.get("house")

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
        lord_dignity=None,
        house_label="7th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="venus",
        dignity=None,
        house_num=venus_house_d1,
        chart_label="D1",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=d9_seventh_lord,
        lord_house=d9_seventh_lord_house,
        lord_dignity=d9_seventh_lord_strength,
        house_label="D9 7th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_lord_signals(
        lord_name=d9_fifth_lord,
        lord_house=d9_fifth_lord_house,
        lord_dignity=d9_fifth_lord_strength,
        house_label="D9 5th lord",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )
    _collect_planet_signals(
        planet_name="venus",
        dignity=d9_venus.get("sign_strength"),
        house_num=d9_venus_house,
        chart_label="D9",
        supportive_signals=supportive_signals,
        challenging_signals=challenging_signals,
    )

    current_stack = [
        period.get("lords", [])
        for _, period in sorted(dashas.get("current_periods", {}).items())
        if isinstance(period, dict)
    ]
    flattened_current_stack = [lord for lords in current_stack for lord in lords]
    relationship_significators = sorted(
        signal for signal in {"venus", "jupiter", seventh_lord_name, d9_seventh_lord} if signal
    )
    current_overlap = sorted(set(flattened_current_stack) & set(relationship_significators))
    windows = _supportive_mahadasha_windows(
        {"sequence": dashas.get("sequence", [])},
        set(relationship_significators),
    )
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
            "key_significators": ["venus"],
            "supportive_dasha_overlap": current_overlap,
        },
        "structured_facts": {
            "d1_marriage_indicators": d1,
            "vimshottari_timing": dashas,
            "d9_marriage_confirmation": d9,
            "d9_5th_lord": {
                "lord": d9_fifth_lord,
                "house": d9_fifth_lord_house,
                "sign_strength": d9_fifth_lord_strength,
            },
            "d9_7th_lord": {
                "lord": d9_seventh_lord,
                "house": d9_seventh_lord_house,
                "sign_strength": d9_seventh_lord_strength,
            },
            "d9_venus": d9_venus,
            "optional_jupiter_saturn_transits": transits,
            "supportive_mahadasha_windows": windows,
        },
        "supportive_signals": supportive_signals,
        "challenging_signals": challenging_signals,
        "model_guidance": [
            "Use D1 7th house and Venus with D9 5th/7th confirmation, Vimshottari timing, and optional Jupiter-Saturn transits.",
            "Do not introduce extra charts or extra marriage factors not present in the structured facts.",
            "Prefer timing windows over a single certain date.",
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
    direct_stack = [
        value
        for value in (
            dashas.get("current_mahadasha"),
            dashas.get("current_antardasha"),
            dashas.get("current_pratyantardasha"),
        )
        if value
    ]
    if direct_stack:
        return direct_stack

    current_periods = dashas.get("current_periods", {})
    stack: list[str] = []
    for period_name in ("mahadasha", "antardasha", "pratyantardasha"):
        lords = current_periods.get(period_name, {}).get("lords", [])
        if lords:
            stack.append(lords[-1])
    return stack


def _career_transit_window_summary(window: dict[str, Any]) -> dict[str, Any]:
    snapshots = window.get("snapshots", [])
    if not snapshots:
        return {}

    target_totals = {
        "jupiter_to_10th": 0,
        "saturn_to_10th": 0,
        "rahu_to_10th": 0,
        "jupiter_to_11th": 0,
        "saturn_to_11th": 0,
        "jupiter_to_2nd": 0,
        "saturn_to_2nd": 0,
    }
    for snapshot in snapshots:
        major_planets = snapshot.get("major_planets", {})
        for planet_name, prefix in (("jupiter", "jupiter"), ("saturn", "saturn"), ("rahu", "rahu")):
            planet_data = major_planets.get(planet_name, {})
            targets = planet_data.get("targets", {})
            if targets.get("10th_house_sign", {}).get("occupies") or targets.get("10th_house_sign", {}).get("aspects"):
                key = f"{prefix}_to_10th"
                if key in target_totals:
                    target_totals[key] += 1
            if planet_name in {"jupiter", "saturn"} and (
                targets.get("11th_house_sign", {}).get("occupies")
                or targets.get("11th_house_sign", {}).get("aspects")
            ):
                target_totals[f"{prefix}_to_11th"] += 1
            if planet_name in {"jupiter", "saturn"} and (
                targets.get("2nd_house_sign", {}).get("occupies")
                or targets.get("2nd_house_sign", {}).get("aspects")
            ):
                target_totals[f"{prefix}_to_2nd"] += 1

    strongest = sorted(
        (
            {"signal": key, "months": value}
            for key, value in target_totals.items()
            if value
        ),
        key=lambda item: item["months"],
        reverse=True,
    )[:5]

    return {
        "requested_range": window.get("requested_range", {}),
        "request_source": window.get("request_source", "unknown"),
        "snapshot_count": window.get("snapshot_count", len(snapshots)),
        "strongest_repeating_transit_links": strongest,
    }


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


def _planet_house_map(chart: dict[str, Any]) -> dict[str, dict[str, Any]]:
    placements: dict[str, dict[str, Any]] = {}
    for planet_name, planet_data in chart.get("planets", {}).items():
        if not isinstance(planet_data, dict):
            continue
        placements[planet_name] = {
            "house": planet_data.get("house"),
            "sign": planet_data.get("sign"),
            "nakshatra": planet_data.get("nakshatra"),
            "pada": planet_data.get("pada"),
        }
    return placements
