# Astrology App

Python astrology app project using open-source chart generation (PyHora/JHora style)
for Vedic charts and AI-assisted interpretation.

## Current Status

- Project scaffolded with a reusable chart-engine adapter.
- Session-only in-memory storage is included.
- Next step is wiring real PyHora function calls inside the adapter.

## Local Setup

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/).
2. Open PowerShell in this folder and create a venv:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
3. Install dependencies:
   - `python -m pip install --upgrade pip`
   - `python -m pip install -e .`
   - `python -m pip install -r requirements.txt`
4. Run the app:
   - `python -m astrology_app.main`

## Project Layout

- `src/astrology_app/main.py`: CLI entry point for user inputs.
- `src/astrology_app/chart_engine.py`: adapter boundary for open-source chart engine.
- `src/astrology_app/session_store.py`: in-memory session store (no long-term storage).
- `src/astrology_app/models.py`: typed input model.
