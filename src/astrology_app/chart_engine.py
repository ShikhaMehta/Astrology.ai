from __future__ import annotations

from dataclasses import asdict
from importlib import import_module

from .models import BirthInput


class PyHoraNotInstalledError(RuntimeError):
    pass


class PyHoraChartEngine:
    """
    Adapter for the open-source PyHora/JHora-style engine.

    This file intentionally isolates all third-party dependency logic so the
    rest of your app does not depend on a specific library's API directly.
    """

    def __init__(self) -> None:
        self._module = self._load_pyhora_module()

    def _load_pyhora_module(self):
        candidates = ("pyhora", "jhora")
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
        """
        Placeholder that returns normalized structure.

        TODO: Replace this with real calls to the selected open-source library.
        """
        return {
            "source": "pyhora-adapter",
            "input": asdict(birth_input),
            "charts": {
                "d1": {},
                "d9": {},
            },
            "dashas": {},
            "nakshatras": {},
            "notes": [
                "Adapter skeleton is ready.",
                "Next step: map real PyHora outputs into this normalized shape.",
            ],
        }
