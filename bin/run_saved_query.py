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
from astrology_app.question_router import categorize_question, select_relevant_chart_keys
from astrology_app.validation import ValidationError, normalize_and_validate_birth_input


# Edit this block, then run:
# python bin/run_saved_query.py
QUERY_CONFIG = {
    "date_of_birth": "1968-11-17",
    "time_of_birth": "08:10",
    "birth_place":  "Parmanandpur, Bihar, India",
    "timezone": "Asia/Kolkata",
    "question": "how is this man relationship with kids and wife",
    # Optional: add extra full charts into the selected evidence bundle.
    # Example: ["d3", "d9", "d12"]
    "requested_chart_keys": [],
}


def main() -> None:
    birth_input = BirthInput(
        date_of_birth=QUERY_CONFIG["date_of_birth"],
        time_of_birth=QUERY_CONFIG["time_of_birth"],
        birth_place=QUERY_CONFIG["birth_place"],
        timezone=QUERY_CONFIG.get("timezone", ""),
    )
    question = QUERY_CONFIG["question"].strip()
    requested_chart_keys = [
        value.strip().lower()
        for value in QUERY_CONFIG.get("requested_chart_keys", [])
        if str(value).strip()
    ]

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

    category = categorize_question(question)
    relevant_keys = select_relevant_chart_keys(category)
    interpretation_context = build_interpretation_context(
        chart_package=chart_package,
        question=question,
        category=category,
        keys=relevant_keys,
        extra_chart_keys=requested_chart_keys,
    )
    interpretation_answer = generate_interpretation_answer(interpretation_context)
    llm_prompt = build_llm_prompt(interpretation_context)

    openai_answer = None
    if openai_is_configured():
        try:
            openai_answer = generate_openai_answer(
                question=question,
                category=category.value,
                reading_input=interpretation_context.get("reading_input", {}),
                evidence=interpretation_context.get("evidence", {}),
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
