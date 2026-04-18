from __future__ import annotations

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
        f"Available evidence keys: {evidence_keys}\n"
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


def _get_by_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current
