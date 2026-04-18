from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


EXPORT_DIR = Path("exports")


def export_session_artifacts(
    *,
    birth_input: Any,
    question: str,
    chart_package: dict[str, Any],
    interpretation_context: dict[str, Any],
    interpretation_answer: str,
    llm_prompt: str,
    openai_answer: str | None,
) -> dict[str, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    _delete_existing_exports()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    place = _slugify(getattr(birth_input, "birth_place", "unknown_place"))
    base_name = f"{timestamp}_{place}_session"
    json_path = EXPORT_DIR / f"{base_name}.json"
    markdown_path = EXPORT_DIR / f"{base_name}.md"
    prompt_path = EXPORT_DIR / f"{base_name}_for_ai.txt"

    payload = {
        "saved_at_local": datetime.now().isoformat(timespec="seconds"),
        "birth_input": _to_jsonable(birth_input),
        "question": question,
        "chart_package": chart_package,
        "interpretation_context": interpretation_context,
        "interpretation_answer": interpretation_answer,
        "openai_answer": openai_answer,
        "llm_prompt": llm_prompt,
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(
        _build_readable_export(payload),
        encoding="utf-8",
    )
    prompt_path.write_text(
        _build_prompt_export(payload),
        encoding="utf-8",
    )

    return {
        "json": json_path.resolve(),
        "markdown": markdown_path.resolve(),
        "prompt": prompt_path.resolve(),
    }


def _build_readable_export(payload: dict[str, Any]) -> str:
    birth_input = payload.get("birth_input", {})
    interpretation_context = payload.get("interpretation_context", {})
    reading_input = interpretation_context.get("reading_input", {})
    scope_lines = _evidence_scope_lines(payload)

    lines = [
        "# Astrology Session Export",
        "",
        f"Saved: {payload.get('saved_at_local', '')}",
        "",
        "## Birth Input",
        f"- Date of birth: {birth_input.get('date_of_birth', '')}",
        f"- Time of birth: {birth_input.get('time_of_birth', '')}",
        f"- Birth place: {birth_input.get('birth_place', '')}",
        f"- Timezone: {birth_input.get('timezone', '')}",
        f"- Timezone source: {birth_input.get('timezone_source', '')}",
        "",
        "## Question",
        payload.get("question", ""),
        "",
        "## Interpretation Answer",
        payload.get("interpretation_answer", ""),
        "",
        "## Evidence Scope",
        *scope_lines,
        "",
    ]

    openai_answer = payload.get("openai_answer")
    if openai_answer:
        lines.extend(
            [
                "## OpenAI Answer",
                openai_answer,
                "",
            ]
        )

    lines.extend(
        [
            "## Reading Input",
            "```json",
            json.dumps(reading_input, indent=2),
            "```",
            "",
            "## Interpretation Context",
            "```json",
            json.dumps(interpretation_context, indent=2),
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def _build_prompt_export(payload: dict[str, Any]) -> str:
    interpretation_context = payload.get("interpretation_context", {})
    reading_input = interpretation_context.get("reading_input", {})
    question = payload.get("question", "")
    question_type = reading_input.get("question_type", "general")
    confidence = reading_input.get("confidence", "unknown")
    supportive_signals = reading_input.get("supportive_signals", [])
    challenging_signals = reading_input.get("challenging_signals", [])
    structured_facts = reading_input.get("structured_facts", {})
    model_guidance = reading_input.get("model_guidance", [])
    scope_lines = _evidence_scope_lines(payload)

    lines = [
        "Use the Vedic astrology evidence below to answer the user's question.",
        "Use only the supplied evidence.",
        "Do not invent extra chart factors, yogas, doshas, transits, or unsupported timing claims.",
        "Do not make deterministic statements.",
        "If evidence is mixed or weak, say so clearly.",
        "Treat missing layers listed under 'Evidence scope' as intentional limits of this dataset.",
        "Do not tell the user to add transits or other missing factors unless you mention them briefly under Limits.",
        "",
        f"Question: {question}",
        "",
        f"Question type: {question_type}",
        f"Confidence hint: {confidence}",
        "",
        "Evidence scope:",
        *scope_lines,
        "",
        "Supportive signals:",
        _bullet_block(supportive_signals),
        "",
        "Challenging signals:",
        _bullet_block(challenging_signals),
        "",
        "Structured facts:",
        json.dumps(structured_facts, indent=2),
        "",
        "Guidance:",
        _bullet_block(model_guidance),
        "",
        "Answer in this format:",
        "1. Summary",
        "2. Key evidence",
        "3. Timing windows",
        "4. Confidence",
        "5. Limits",
        "",
    ]
    return "\n".join(lines)


def _delete_existing_exports() -> None:
    for pattern in ("*_session.json", "*_session.md", "*_session_for_ai.txt"):
        for path in EXPORT_DIR.glob(pattern):
            path.unlink(missing_ok=True)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()
    return normalized or "unknown_place"


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _bullet_block(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _evidence_scope_lines(payload: dict[str, Any]) -> list[str]:
    interpretation_context = payload.get("interpretation_context", {})
    reading_input = interpretation_context.get("reading_input", {})
    chart_package = payload.get("chart_package", {})
    metadata = chart_package.get("metadata", {})
    charts_included = metadata.get("charts_included", [])
    evidence_keys = sorted(interpretation_context.get("evidence", {}).keys())

    included = [
        "Included: computed natal/divisional chart evidence from the current chart package.",
        f"Included charts: {', '.join(charts_included) if charts_included else 'only charts present in the attached data'}.",
        f"Included evidence keys: {', '.join(evidence_keys) if evidence_keys else 'none'}.",
        "Included timing layer: Vimshottari dasha sequence and current dasha stack when present.",
    ]

    if reading_input.get("ready_for_model"):
        included.append("Included structured features: question-specific extracted signals and structured facts.")
    else:
        included.append("Structured feature extractor status: this question does not yet have a dedicated extractor, so rely only on the provided evidence keys.")

    excluded = [
        "Not included: transits (gochara).",
        "Not included: annual charts / varshaphala.",
        "Not included: ashtakavarga, shadbala, or other strength systems unless explicitly shown in the data.",
        "Not included: event rectification or life-history confirmation.",
        "Not included: any chart factors not explicitly present in this export.",
    ]

    return [f"- {line}" for line in included + excluded]
