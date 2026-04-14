from __future__ import annotations

import json

from astrology_app.chart_engine import PyHoraChartEngine, PyHoraNotInstalledError
from astrology_app.models import BirthInput
from astrology_app.session_store import SessionStore


def collect_birth_input() -> BirthInput:
    print("Enter birth details for Vedic chart generation")
    dob = input("Date of birth (YYYY-MM-DD): ").strip()
    tob = input("Time of birth (HH:MM, 24-hour): ").strip()
    place = input("Place of birth (City, Country): ").strip()
    timezone = input("Timezone (e.g. America/Phoenix): ").strip()
    return BirthInput(
        date_of_birth=dob,
        time_of_birth=tob,
        birth_place=place,
        timezone=timezone,
    )


def main() -> None:
    session = SessionStore()
    birth_input = collect_birth_input()

    try:
        engine = PyHoraChartEngine()
        chart_package = engine.generate_chart_package(birth_input)
    except PyHoraNotInstalledError as exc:
        print("\n[Setup needed]")
        print(str(exc))
        return

    session.set("birth_input", birth_input)
    session.set("chart_package", chart_package)

    print("\nChart package (normalized):")
    print(json.dumps(chart_package, indent=2))
    print("\nSession-only storage is active. Data is in memory only.")


if __name__ == "__main__":
    main()
