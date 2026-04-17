from __future__ import annotations

import json

from astrology_app.chart_engine import PyHoraNotInstalledError, build_chart_engine
from astrology_app.interpretation import build_interpretation_context, build_llm_prompt
from astrology_app.models import BirthInput
from astrology_app.question_router import categorize_question, select_relevant_chart_keys
from astrology_app.session_store import SessionStore
from astrology_app.validation import ValidationError, normalize_and_validate_birth_input


def collect_birth_input() -> BirthInput:
    print("Enter birth details for Vedic chart generation")
    dob = input("Date of birth (YYYY-MM-DD): ").strip()
    tob = input(
        "Time of birth (HH:MM, 24-hour local time at place of birth): "
    ).strip()
    place = input("Place of birth (City, State, Country or City, Country): ").strip()
    timezone = input(
        "Timezone (IANA e.g. Asia/Kolkata; leave blank or enter best guess to auto-infer): "
    ).strip()
    return BirthInput(
        date_of_birth=dob,
        time_of_birth=tob,
        birth_place=place,
        timezone=timezone,
    )


def main() -> None:
    session = SessionStore()
    birth_input = collect_birth_input()
    question = input("Ask your astrology question: ").strip()

    try:
        birth_input = normalize_and_validate_birth_input(birth_input)
    except ValidationError as exc:
        print("\n[Input validation error]")
        print(str(exc))
        return

    # now shows timezone source so user knows if it was inferred
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

    session.set("birth_input", birth_input)
    session.set("chart_package", chart_package)
    session.set("question", question)

    category = categorize_question(question)
    relevant_keys = select_relevant_chart_keys(category)
    interpretation_context = build_interpretation_context(
        chart_package=chart_package,
        question=question,
        category=category,
        keys=relevant_keys,
    )
    llm_prompt = build_llm_prompt(interpretation_context)
    session.set("interpretation_context", interpretation_context)

    print("\nChart package (normalized):")
    print(json.dumps(chart_package, indent=2))
    print("\nInterpretation context (selected evidence):")
    print(json.dumps(interpretation_context, indent=2))
    print("\nLLM prompt preview:")
    print(llm_prompt)
    print("\nSession-only storage is active. Data is in memory only.")


if __name__ == "__main__":
    main()