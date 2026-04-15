from __future__ import annotations

from typing import Any

from astrology_app.models import QuestionCategory


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
    return context


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


def _get_by_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current
