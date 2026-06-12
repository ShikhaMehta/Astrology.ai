from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from astrology_app.chart_engine import PyHoraNotInstalledError, build_chart_engine
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
from astrology_app.pipeline import (
    attach_requested_transit_window,
    resolve_evidence_keys,
    resolve_prediction_window,
    resolve_requested_chart_keys,
)
from astrology_app.question_router import categorize_question
from astrology_app.validation import ValidationError, normalize_and_validate_birth_input


# Edit this block, then run:
# python bin/run_saved_query.py
QUERY_CONFIG = {
    "date_of_birth": "1988-07-09",
    "time_of_birth": "22:33",
    "birth_place": "Allahabad, Uttar Pradesh, India",
    "timezone": "",
    "question": "relationship with wife",
    "client_context": "",
    "answer_style": (
        "Start with past highs and lows, then future highs and lows. Sort each section by date/period. "
        "Only include major events, critical shifts, and practical updates. "
        "Prioritize dasha changes and repeated transit hits to 5th house, 7th house, Venus, "
        "and the 1st/7th axis. Avoid month-by-month detail unless a month is unusually important."
    ),
    # Set to True to include every divisional chart plus full derived/dasha/transit evidence.
    "comprehensive_reading": False,
    # Optional: add extra full charts into the selected evidence bundle.
    # Charts already represented by selected evidence are skipped to avoid duplicate paste payloads.
    "requested_chart_keys": [
        # "d1",
        # "d7",
        # "d3",
        # "d9",
        # "d10",
        # "d12",
        # "d16",
        # "d20",
        # "d60",
    ],
    # Optional: request a full transit ephemeris for a prediction window.
    # If omitted, YYYY-YYYY or M/YYYY-M/YYYY ranges in the question are inferred automatically.
    "prediction_window": {
        "start_date": "3/2023",  # also accepts YYYY-MM-DD
        "end_date": "12/2030",
        "step": "monthly",  # or "weekly", "daily"
    },
}


def main() -> None:
    birth_input = BirthInput(
        date_of_birth=QUERY_CONFIG["date_of_birth"],
        time_of_birth=QUERY_CONFIG["time_of_birth"],
        birth_place=QUERY_CONFIG["birth_place"],
        timezone=QUERY_CONFIG.get("timezone", ""),
    )
    question = QUERY_CONFIG["question"].strip()
    client_context = str(QUERY_CONFIG.get("client_context", "")).strip()
    comprehensive_reading = bool(QUERY_CONFIG.get("comprehensive_reading", False))
    requested_chart_keys = resolve_requested_chart_keys(
        requested_chart_keys=QUERY_CONFIG.get("requested_chart_keys"),
        comprehensive_reading=comprehensive_reading,
    )
    prediction_window = resolve_prediction_window(
        question=question,
        config=QUERY_CONFIG.get("prediction_window"),
    )

    try:
        birth_input = normalize_and_validate_birth_input(birth_input)
    except ValidationError as exc:
        print("\n[Input validation error]")
        print(str(exc))
        return

    print(
        f"\nUsing local birth time at '{birth_input.birth_place}' "
        f"with timezone '{birth_input.timezone}' "
        f"(source: {birth_input.timezone_source})."
    )

    try:
        engine = build_chart_engine()
        chart_package = engine.generate_chart_package(birth_input)
    except PyHoraNotInstalledError as exc:
        print("\n[Setup needed]")
        print(str(exc))
        return

    if prediction_window:
        attach_requested_transit_window(
            chart_package=chart_package,
            birth_input=birth_input,
            prediction_window=prediction_window,
        )

    category = categorize_question(question)
    relevant_keys = resolve_evidence_keys(
        category=category,
        comprehensive_reading=comprehensive_reading,
    )
    interpretation_context = build_interpretation_context(
        chart_package=chart_package,
        question=question,
        category=category,
        keys=relevant_keys,
        extra_chart_keys=requested_chart_keys,
        comprehensive_reading=comprehensive_reading,
    )
    interpretation_answer = generate_interpretation_answer(interpretation_context)
    llm_prompt = build_llm_prompt(interpretation_context, birth_input=birth_input)

    openai_answer = None
    if openai_is_configured():
        try:
            openai_answer = generate_openai_answer(
                question=question,
                category=category.value,
                reading_input=interpretation_context.get("reading_input", {}),
                evidence=interpretation_context.get("evidence", {}),
                birth_input={
                    "date_of_birth": birth_input.date_of_birth,
                    "time_of_birth": birth_input.time_of_birth,
                    "birth_place": birth_input.birth_place,
                    "timezone": birth_input.timezone,
                    "timezone_source": birth_input.timezone_source,
                    "latitude": birth_input.latitude,
                    "longitude": birth_input.longitude,
                },
            )
        except (OpenAIConfigurationError, OpenAIRequestError) as exc:
            openai_answer = f"[OpenAI unavailable] {exc}"

    export_paths = export_session_artifacts(
        birth_input=birth_input,
        question=question,
        chart_package=chart_package,
        interpretation_context=interpretation_context,
        interpretation_answer=interpretation_answer,
        llm_prompt=llm_prompt,
        openai_answer=openai_answer,
        client_context=client_context,
        answer_style=QUERY_CONFIG.get("answer_style"),
        user_details={
            "birth_input": {
                "date_of_birth": birth_input.date_of_birth,
                "time_of_birth": birth_input.time_of_birth,
                "birth_place": birth_input.birth_place,
                "timezone": birth_input.timezone,
                "timezone_source": birth_input.timezone_source,
                "latitude": birth_input.latitude,
                "longitude": birth_input.longitude,
            },
            "question": question,
            "known_facts": client_context,
            "answer_style": QUERY_CONFIG.get("answer_style"),
            "comprehensive_reading": comprehensive_reading,
            "requested_chart_keys": requested_chart_keys,
            "prediction_window": prediction_window or {},
        },
    )

    print("\nQuery config:")
    print(json.dumps(QUERY_CONFIG, indent=2))
    print("\nInterpretation context (selected evidence):")
    print(json.dumps(interpretation_context, indent=2))
    print("\nReading input (structured features):")
    print(json.dumps(interpretation_context.get("reading_input", {}), indent=2))
    print("\nInterpretation answer:")
    print(interpretation_answer)
    if openai_answer:
        print("\nOpenAI answer:")
        print(openai_answer)
    print("\nSaved session exports:")
    print(f"Readable: {export_paths['markdown']}")
    print(f"Raw JSON: {export_paths['json']}")
    print(f"Copy/Paste AI prompt: {export_paths['prompt']}")


if __name__ == "__main__":
    main()
