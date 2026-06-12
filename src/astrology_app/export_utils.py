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
    client_context: str | None = None,
    answer_style: str | None = None,
    user_details: dict[str, Any] | None = None,
) -> dict[str, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    _delete_existing_exports()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    place = _slugify(getattr(birth_input, "birth_place", "unknown_place"))
    base_name = f"{timestamp}_{place}_session"
    json_path = EXPORT_DIR / f"{base_name}.json"
    markdown_path = EXPORT_DIR / f"{base_name}.md"
    prompt_path = EXPORT_DIR / f"{base_name}_for_ai.txt"
    compact_chart_package = _compact_export_chart_package(
        chart_package=chart_package,
        interpretation_context=interpretation_context,
    )

    payload = {
        "saved_at_local": datetime.now().isoformat(timespec="seconds"),
        "birth_input": _to_jsonable(birth_input),
        "question": question,
        "client_context": client_context,
        "chart_package": compact_chart_package,
        "interpretation_context": _compact_export_interpretation_context(interpretation_context),
        "interpretation_answer": interpretation_answer,
        "openai_answer": openai_answer,
        "answer_style": answer_style,
        "user_details": user_details or {},
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
    ]
    client_context = str(payload.get("client_context") or "").strip()
    if client_context:
        lines.extend(
            [
                "## Known Life Context",
                client_context,
                "",
            ]
        )

    lines.extend(
        [
            "## Interpretation Answer",
            payload.get("interpretation_answer", ""),
            "",
            "## Evidence Scope",
            *scope_lines,
            "",
        ]
    )

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
        ]
    )

    return "\n".join(lines)


def _build_prompt_export(payload: dict[str, Any]) -> str:
    interpretation_context = payload.get("interpretation_context", {})
    reading_input = interpretation_context.get("reading_input", {})
    selected_evidence = _compact_prompt_evidence(
        payload.get("chart_package", {}).get("relevant_sections", {})
    )
    birth_input = payload.get("birth_input", {})
    question = payload.get("question", "")
    question_type = reading_input.get("question_type", "general")
    supportive_signals = reading_input.get("supportive_signals", [])
    challenging_signals = reading_input.get("challenging_signals", [])
    structured_facts = reading_input.get("structured_facts", {})
    scope_lines = _prompt_evidence_scope_lines(payload)
    answer_style = str(payload.get("answer_style") or "").strip()
    client_context = str(payload.get("client_context") or "").strip()
    user_details = payload.get("user_details", {})
    reading_date = str(payload.get("saved_at_local") or "").split("T", maxsplit=1)[0]

    lines = [
        "Please answer the user's astrology question using the birth details and chart evidence below.",
        "The birth details are supplied below.",
        "Please include details from both the past and the future when the chart evidence supports it.",
        "",
        f"Question: {question}",
        f"Reading date: {reading_date}",
        "",
        "Birth details:",
        f"- Date of birth: {birth_input.get('date_of_birth', '')}",
        f"- Time of birth: {birth_input.get('time_of_birth', '')}",
        f"- Birth place: {birth_input.get('birth_place', '')}",
        f"- Timezone: {birth_input.get('timezone', '')}",
        f"- Coordinates: {birth_input.get('latitude', '')}, {birth_input.get('longitude', '')}",
        "",
    ]
    if user_details:
        lines.extend(
            [
                "All user details supplied:",
                json.dumps(user_details, indent=2),
                "",
            ]
        )
    if client_context:
        lines.extend(
            [
                "Known life context / client facts:",
                client_context,
                "",
            ]
        )
    if answer_style:
        lines.extend(
            [
                "Answer style:",
                answer_style,
                "",
            ]
        )
    lines.extend(
        [
            f"Question type: {question_type}",
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
            "Selected evidence:",
            json.dumps(selected_evidence, indent=2),
            "",
            "Please organize the answer with past observations first, then future possibilities.",
            "",
        ]
    )
    return "\n".join(lines)


def _compact_prompt_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in evidence.items():
        if key.endswith(".transit_window") and isinstance(value, dict):
            compact[key] = _compact_prompt_transit_window(value)
        else:
            compact[key] = value
    return compact


def _compact_prompt_transit_window(window: dict[str, Any]) -> dict[str, Any]:
    snapshots = window.get("snapshots", [])
    highlighted = _highlight_transit_snapshots(snapshots, limit=18)
    return {
        "requested_range": window.get("requested_range", {}),
        "request_source": window.get("request_source", "unknown"),
        "reference_method": window.get("reference_method", ""),
        "natal_reference": window.get("natal_reference", {}),
        "snapshot_count": window.get("snapshot_count", len(snapshots)),
        "relationship_signal_summary": window.get("relationship_signal_summary", []),
        "prompt_compaction_note": (
            "Full monthly snapshots are retained in the JSON export. "
            "This AI prompt includes only the strongest relationship-relevant snapshots to reduce noise."
        ),
        "highlighted_snapshots": highlighted,
    }


def _highlight_transit_snapshots(
    snapshots: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    scored = [
        (_relationship_snapshot_score(snapshot), index, snapshot)
        for index, snapshot in enumerate(snapshots)
    ]
    strongest = [
        (score, index, snapshot)
        for score, index, snapshot in sorted(scored, key=lambda item: item[0], reverse=True)
        if score > 0
    ][:limit]
    return [
        _compact_highlighted_snapshot(snapshot, score)
        for score, _index, snapshot in sorted(strongest, key=lambda item: item[1])
    ]


def _compact_highlighted_snapshot(snapshot: dict[str, Any], score: int) -> dict[str, Any]:
    planets = snapshot.get("major_planets", {})
    return {
        "reference_date": snapshot.get("reference_date", {}),
        "score": score,
        "retrograde_planets": snapshot.get("retrograde_planets", []),
        "relationship_hits": {
            planet_name: _relationship_target_hits(planet_data.get("targets", {}))
            for planet_name, planet_data in planets.items()
            if _relationship_target_hits(planet_data.get("targets", {}))
        },
    }


def _relationship_snapshot_score(snapshot: dict[str, Any]) -> int:
    planets = snapshot.get("major_planets", {})
    weights = {
        ("jupiter", "5th_house_sign"): 3,
        ("jupiter", "7th_house_sign"): 4,
        ("jupiter", "venus_sign"): 4,
        ("saturn", "7th_house_sign"): 4,
        ("saturn", "venus_sign"): 4,
        ("rahu", "1st_house_sign"): 3,
        ("rahu", "7th_house_sign"): 3,
        ("ketu", "1st_house_sign"): 3,
        ("ketu", "7th_house_sign"): 3,
        ("mars", "7th_house_sign"): 2,
        ("mars", "venus_sign"): 2,
    }
    score = 0
    for (planet_name, target_key), weight in weights.items():
        targets = planets.get(planet_name, {}).get("targets", {})
        if _target_hit(targets, target_key):
            score += weight
    return score


def _relationship_target_hits(targets: dict[str, Any]) -> list[str]:
    hits = []
    for target_key in ("1st_house_sign", "5th_house_sign", "7th_house_sign", "venus_sign"):
        if _target_hit(targets, target_key):
            hits.append(target_key)
    return hits


def _target_hit(targets: dict[str, Any], target_key: str) -> bool:
    target = targets.get(target_key, {})
    return bool(target.get("occupies") or target.get("aspects"))


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


def _compact_export_chart_package(
    *,
    chart_package: dict[str, Any],
    interpretation_context: dict[str, Any],
) -> dict[str, Any]:
    evidence = interpretation_context.get("evidence", {})
    metadata = chart_package.get("metadata", {})
    compact = {
        "source": chart_package.get("source"),
        "input": chart_package.get("input", {}),
        "metadata": metadata,
        "relevant_sections": evidence,
    }
    notes = chart_package.get("notes", [])
    if notes:
        compact["notes"] = notes
    return compact


def _compact_export_interpretation_context(context: dict[str, Any]) -> dict[str, Any]:
    evidence = context.get("evidence", {})
    reading_input = context.get("reading_input", {})
    return {
        "question": context.get("question"),
        "category": context.get("category"),
        "evidence_keys": sorted(evidence.keys()),
        "reading_input": _compact_export_reading_input(reading_input),
    }


def _compact_export_reading_input(reading_input: dict[str, Any]) -> dict[str, Any]:
    compact = dict(reading_input)
    compact.pop("metadata", None)
    return compact


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
    evidence_keys = interpretation_context.get("evidence_keys", [])

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

    relevant_sections = chart_package.get("relevant_sections", {})
    transits = any(key.endswith(".transit_window") for key in relevant_sections)
    if transits:
        included.append(
            "Included transits: requested monthly transit ephemeris window for the specified prediction range."
        )
    else:
        included.append("Included transits: only the default current snapshot when explicitly shown in the selected evidence.")

    if any("ashtakavarga" in key for key in evidence_keys):
        included.append("Included strength/support layer: compact Ashtakavarga summary for relevant houses.")

    excluded = [
        "Not included: extra transit windows beyond those explicitly attached to this export.",
        "Not included: annual charts / varshaphala.",
        "Not included: shadbala or other strength systems unless explicitly shown in the data.",
        "Not included: event rectification or life-history confirmation.",
        "Not included: any chart factors not explicitly present in this export.",
    ]

    return [f"- {line}" for line in included + excluded]


def _prompt_evidence_scope_lines(payload: dict[str, Any]) -> list[str]:
    """Keep AI-facing scope positive so the answer does not become caveat-led."""
    return [
        line
        for line in _evidence_scope_lines(payload)
        if not line.startswith("- Not included:")
    ]
