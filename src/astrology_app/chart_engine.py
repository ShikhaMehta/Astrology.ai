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
        from .pyjhora_adapter import generate_pyjhora_chart_package

        return generate_pyjhora_chart_package(birth_input)


def build_chart_engine() -> ChartEngine:
    engine_name = os.getenv("ASTROLOGY_ENGINE", "jhora").strip().lower()
    if engine_name == "mock":
        return MockChartEngine()
    if engine_name == "jhora":
        return PyJHoraChartEngine()
    raise ValueError(
        "Unsupported ASTROLOGY_ENGINE value. Use 'jhora' or 'mock'."
    )


def _build_placeholder_chart_package(
    birth_input: BirthInput,
    source: str,
    status: str,
    notes: list[str],
) -> dict:
    return {
        "source": source,
        "input": asdict(birth_input),
        "metadata": {
            "ayanamsha": "lahiri",
            "dasha_system": "vimshottari",
            "charts_included": ["d1", "d9"],
            "status": status,
        },
        "charts": {
            "d1": {
                "ascendant_sign": "aries",
                "planets_by_house": {},
                "house_lords": {},
            },
            "d9": {
                "ascendant_sign": "libra",
                "planets_by_house": {},
                "house_lords": {},
            },
        },
        "dashas": {
            "current_mahadasha": "moon",
            "current_antardasha": "venus",
            "sequence": [],
        },
        "nakshatras": {
            "moon": {"name": "rohini", "pada": 2},
        },
        "notes": notes,
    }
