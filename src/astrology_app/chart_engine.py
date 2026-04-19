from __future__ import annotations

from dataclasses import asdict
import os
from importlib import import_module
from typing import Protocol

from .models import BirthInput


class PyHoraNotInstalledError(RuntimeError):
    pass


class ChartEngine(Protocol):
    def generate_chart_package(self, birth_input: BirthInput) -> dict:
        ...


class MockChartEngine:
    """Fallback chart engine for local development and testing."""

    def generate_chart_package(self, birth_input: BirthInput) -> dict:
        return _build_placeholder_chart_package(
            birth_input=birth_input,
            source="mock-engine",
            status="mock-data-for-development",
            notes=[
                "Using mock chart engine.",
                "Switch ASTROLOGY_ENGINE=jhora to use PyJHora adapter.",
            ],
        )


class PyJHoraChartEngine:
    """
    Adapter for the open-source PyHora/JHora-style engine.

    This file intentionally isolates all third-party dependency logic so the
    rest of your app does not depend on a specific library's API directly.
    """

    def __init__(self) -> None:
        self._module = self._load_pyjhora_module()

    def _load_pyjhora_module(self):
        candidates = ("jhora", "pyhora")
        for module_name in candidates:
            try:
                return import_module(module_name)
            except ModuleNotFoundError:
                continue

        raise PyHoraNotInstalledError(
            "PyHora/JHora module not found. Install the open-source project first, "
            "then wire the exact import path in chart_engine.py."
        )

    def generate_chart_package(self, birth_input: BirthInput) -> dict:
        try:
            from .pyjhora_adapter import generate_pyjhora_chart_package
        except ModuleNotFoundError as exc:
            missing = exc.name or "required dependency"
            raise PyHoraNotInstalledError(
                "Real chart generation is not available because "
                f"'{missing}' is missing. Install the optional JHora runtime "
                "dependencies or set ASTROLOGY_ENGINE=mock to run without them."
            ) from exc

        return generate_pyjhora_chart_package(birth_input)


def build_chart_engine() -> ChartEngine:
    engine_name = os.getenv("ASTROLOGY_ENGINE", "auto").strip().lower()
    if engine_name in ("", "auto"):
        if _pyjhora_runtime_available():
            return PyJHoraChartEngine()
        return MockChartEngine()
    if engine_name == "mock":
        return MockChartEngine()
    if engine_name == "jhora":
        return PyJHoraChartEngine()
    raise ValueError(
        "Unsupported ASTROLOGY_ENGINE value. Use 'auto', 'jhora', or 'mock'."
    )


def _pyjhora_runtime_available() -> bool:
    try:
        import_module("swisseph")
    except ModuleNotFoundError:
        return False

    for module_name in ("jhora", "pyhora"):
        try:
            import_module(module_name)
            return True
        except ModuleNotFoundError:
            continue
    return False


def _build_placeholder_chart_package(
    birth_input: BirthInput,
    source: str,
    status: str,
    notes: list[str],
) -> dict:
    chart_keys = [
        "d1",
        "d2",
        "d3",
        "d4",
        "d6",
        "d7",
        "d8",
        "d9",
        "d10",
        "d12",
        "d16",
        "d20",
        "d24",
        "d27",
        "d30",
        "d40",
        "d45",
        "d60",
    ]
    placeholder_chart = {
        "ascendant": {
            "sign": "aries",
            "longitude_in_sign_degrees": 0.0,
            "house": 1,
        },
        "planets": {},
    }
    return {
        "source": source,
        "input": asdict(birth_input),
        "metadata": {
            "ayanamsha": "lahiri",
            "dasha_system": "vimshottari",
            "charts_included": chart_keys,
            "status": status,
        },
        "charts": {key: placeholder_chart for key in chart_keys},
        "derived": {
            "houses": {},
            "house_lords": {},
            "dignities": {},
            "aspects": {},
            "conjunctions": [],
        },
        "dashas": {
            "current_mahadasha": "moon",
            "current_antardasha": "venus",
            "current_pratyantardasha": "mars",
            "sequence": [],
        },
        "sudarshana_chakra": {
            "current_cycle": {
                "reference": {"running_year_number": 1, "completed_years": 0},
                "lagna_chart": [],
                "moon_chart": [],
                "sun_chart": [],
                "retrograde_planets": [],
            }
        },
        "transits": {
            "current": {
                "as_of": {
                    "timezone": birth_input.timezone,
                },
                "chart": placeholder_chart,
                "retrograde_planets": [],
            }
        },
        "nakshatras": {
            "moon": {"name": "rohini", "pada": 2},
        },
        "notes": notes,
    }
