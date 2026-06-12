from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import asdict, is_dataclass
from typing import Any

from astrology_app.chart_engine import build_chart_engine
from astrology_app.export_utils import export_session_artifacts
from astrology_app.interpretation import (
    build_interpretation_context,
    build_llm_prompt,
    generate_interpretation_answer,
)
from astrology_app.llm_openai import (
    OpenAIConfigurationError,
    OpenAIRequestError,
    generate_openai_answer,
    openai_is_configured,
)
from astrology_app.models import BirthInput
from astrology_app.chart_catalog import ALL_DIVISIONAL_CHART_KEYS
from astrology_app.question_router import (
    categorize_question,
    select_comprehensive_chart_keys,
    select_relevant_chart_keys,
)
from astrology_app.validation import normalize_and_validate_birth_input


def resolve_requested_chart_keys(
    *,
    requested_chart_keys: list[str] | None,
    comprehensive_reading: bool = False,
) -> list[str]:
    normalized = [
        value.strip().lower()
        for value in (requested_chart_keys or [])
        if str(value).strip()
    ]
    if not comprehensive_reading:
        return normalized

    merged: list[str] = []
    seen: set[str] = set()
    for key in (*ALL_DIVISIONAL_CHART_KEYS, *normalized):
        if key not in seen:
            seen.add(key)
            merged.append(key)
    return merged


def resolve_evidence_keys(
    *,
    category,
    comprehensive_reading: bool = False,
) -> list[str]:
    if comprehensive_reading:
        return select_comprehensive_chart_keys()
    return select_relevant_chart_keys(category)


def generate_reading_session(
    *,
    birth_input: BirthInput,
    question: str,
    client_context: str | None = None,
    answer_style: str | None = None,
    requested_chart_keys: list[str] | None = None,
    prediction_window: dict[str, Any] | None = None,
    comprehensive_reading: bool = False,
    use_openai: bool = False,
) -> dict[str, Any]:
    """Run the chart, evidence, local answer, prompt, and export pipeline once."""
    question = question.strip()
    client_context = (client_context or "").strip()
    if not question:
        raise ValueError("Question is required.")

    supplied_birth_input = birth_input
    normalized_birth_input = normalize_and_validate_birth_input(birth_input)
    engine = build_chart_engine()
    chart_package = engine.generate_chart_package(normalized_birth_input)
    resolved_prediction_window = resolve_prediction_window(
        question=question,
        config=prediction_window,
    )
    if resolved_prediction_window:
        attach_requested_transit_window(
            chart_package=chart_package,
            birth_input=normalized_birth_input,
            prediction_window=resolved_prediction_window,
        )

    category = categorize_question(question)
    relevant_keys = resolve_evidence_keys(
        category=category,
        comprehensive_reading=comprehensive_reading,
    )
    normalized_requested_keys = resolve_requested_chart_keys(
        requested_chart_keys=requested_chart_keys,
        comprehensive_reading=comprehensive_reading,
    )
    user_details = {
        "birth_input_supplied": _to_jsonable(supplied_birth_input),
        "birth_input_normalized": _to_jsonable(normalized_birth_input),
        "question": question,
        "known_facts": client_context,
        "answer_style": answer_style,
        "comprehensive_reading": comprehensive_reading,
        "requested_chart_keys": normalized_requested_keys,
        "prediction_window_requested": prediction_window or {},
        "prediction_window_used": resolved_prediction_window or {},
    }
    interpretation_context = build_interpretation_context(
        chart_package=chart_package,
        question=question,
        category=category,
        keys=relevant_keys,
        extra_chart_keys=normalized_requested_keys,
        comprehensive_reading=comprehensive_reading,
    )
    interpretation_answer = generate_interpretation_answer(interpretation_context)
    llm_prompt = build_llm_prompt(interpretation_context, birth_input=normalized_birth_input)
    openai_answer = _maybe_generate_openai_answer(
        birth_input=normalized_birth_input,
        question=question,
        category=category.value,
        client_context=client_context,
        user_details=user_details,
        interpretation_context=interpretation_context,
        use_openai=use_openai,
    )
    export_paths = export_session_artifacts(
        birth_input=normalized_birth_input,
        question=question,
        chart_package=chart_package,
        interpretation_context=interpretation_context,
        interpretation_answer=interpretation_answer,
        llm_prompt=llm_prompt,
        openai_answer=openai_answer,
        client_context=client_context,
        answer_style=answer_style,
        user_details=user_details,
    )
    ai_prompt = export_paths["prompt"].read_text(encoding="utf-8")

    return {
        "birth_input": _to_jsonable(normalized_birth_input),
        "question": question,
        "client_context": client_context,
        "category": category.value,
        "chart_source": chart_package.get("source"),
        "chart_status": chart_package.get("metadata", {}).get("status", "ready"),
        "notes": chart_package.get("notes", []),
        "interpretation_context": interpretation_context,
        "interpretation_answer": interpretation_answer,
        "openai_answer": openai_answer,
        "llm_prompt": ai_prompt,
        "raw_llm_prompt": llm_prompt,
        "answer_style": answer_style,
        "comprehensive_reading": comprehensive_reading,
        "requested_chart_keys": normalized_requested_keys,
        "prediction_window": resolved_prediction_window,
        "export_paths": {key: str(path) for key, path in export_paths.items()},
    }


def resolve_prediction_window(
    *,
    question: str,
    config: dict[str, Any] | None,
) -> dict[str, str] | None:
    if isinstance(config, dict):
        start_value = str(config.get("start_date", "")).strip()
        end_value = str(config.get("end_date", "")).strip()
        step = str(config.get("step", "monthly")).strip().lower() or "monthly"
        if start_value and end_value:
            return {
                "start_date": _normalize_window_boundary(start_value, boundary="start"),
                "end_date": _normalize_window_boundary(end_value, boundary="end"),
                "step": step,
                "source": str(config.get("source", "query_config")),
            }
    return infer_prediction_window_from_question(question)


def infer_prediction_window_from_question(question: str) -> dict[str, str] | None:
    month_range = _infer_month_range_from_question(question)
    if month_range:
        return month_range

    years = re.findall(r"\b(19\d{2}|20\d{2}|21\d{2})\b", question)
    if not years:
        return None
    if len(years) == 1:
        year = int(years[0])
        return {
            "start_date": f"{year:04d}-01-01",
            "end_date": f"{year:04d}-12-31",
            "step": "monthly",
            "source": "question_year",
        }

    first_year = int(years[0])
    last_year = int(years[1])
    start_year = min(first_year, last_year)
    end_year = max(first_year, last_year)
    return {
        "start_date": f"{start_year:04d}-01-01",
        "end_date": f"{end_year:04d}-12-31",
        "step": "monthly",
        "source": "question_year_range",
    }


def attach_requested_transit_window(
    *,
    chart_package: dict[str, Any],
    birth_input: BirthInput,
    prediction_window: dict[str, str],
) -> None:
    if chart_package.get("source") != "pyjhora-adapter":
        return

    from astrology_app.pyjhora_adapter import build_requested_transit_window

    transits = chart_package.setdefault("transits", {})
    transits["requested_window"] = {
        **build_requested_transit_window(
            birth_input,
            start_date=prediction_window["start_date"],
            end_date=prediction_window["end_date"],
            step=prediction_window.get("step", "monthly"),
        ),
        "request_source": prediction_window.get("source", "unknown"),
    }


def _maybe_generate_openai_answer(
    *,
    birth_input: BirthInput,
    question: str,
    category: str,
    client_context: str | None,
    user_details: dict[str, Any],
    interpretation_context: dict[str, Any],
    use_openai: bool,
) -> str | None:
    if not use_openai or not openai_is_configured():
        return None

    try:
        return generate_openai_answer(
            question=question,
            category=category,
            reading_input=interpretation_context.get("reading_input", {}),
            evidence=interpretation_context.get("evidence", {}),
            client_context=client_context,
            birth_input=_to_jsonable(birth_input),
            user_details=user_details,
        )
    except (OpenAIConfigurationError, OpenAIRequestError) as exc:
        return f"[OpenAI unavailable] {exc}"


def _infer_month_range_from_question(question: str) -> dict[str, str] | None:
    match = re.search(
        r"\b(0?[1-9]|1[0-2])\s*/\s*((?:19|20|21)\d{2})\s*[-\u2013\u2014]\s*"
        r"(0?[1-9]|1[0-2])\s*/\s*((?:19|20|21)\d{2})\b",
        question,
    )
    if not match:
        return None

    start_month, start_year, end_month, end_year = (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
    )
    start_marker = (start_year, start_month)
    end_marker = (end_year, end_month)
    if end_marker < start_marker:
        start_month, start_year, end_month, end_year = (
            end_month,
            end_year,
            start_month,
            start_year,
        )

    return {
        "start_date": f"{start_year:04d}-{start_month:02d}-01",
        "end_date": _month_end_date(end_year, end_month),
        "step": "monthly",
        "source": "question_month_year_range",
    }


def _normalize_window_boundary(value: str, *, boundary: str) -> str:
    if re.fullmatch(r"(?:19|20|21)\d{2}-\d{2}-\d{2}", value):
        return value

    match = re.fullmatch(r"(0?[1-9]|1[0-2])\s*/\s*((?:19|20|21)\d{2})", value)
    if not match:
        raise ValueError(
            "Prediction window dates must use YYYY-MM-DD or M/YYYY, "
            "for example 2009-03-01 or 3/2009."
        )

    month = int(match.group(1))
    year = int(match.group(2))
    if boundary == "start":
        return f"{year:04d}-{month:02d}-01"
    return _month_end_date(year, month)


def _month_end_date(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value
