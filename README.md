# Astrology App

Python astrology app project using open-source chart generation (PyHora/JHora style)
for Vedic charts and AI-assisted interpretation.

## Current Status

- Project scaffolded with a reusable chart-engine adapter.
- Session-only in-memory storage is included.
- Engine selection is adapter-driven (`jhora` or `mock`) for future swap flexibility.
- With `ASTROLOGY_ENGINE=jhora`, the CLI computes **D1, D9**, **Vimśottari** (current Mahā + Antara, full Mahā sequence), and **nakṣatra/pada** from PyJHora, then builds **LLM evidence** from the selected slices (same session object you print as JSON).

### Compact Evidence for AI

- Large raw exports can confuse the LLM, especially for health, relationship, and timing-heavy questions.
- The app now trims those categories into compact evidence bundles before building `reading_input` and LLM prompts.
- Compact bundles keep the highest-signal chart factors plus current dasha periods, dasha sequence, and only nearby Mahadasha and Antardasha context.
- Full lifetime Antardasha and Pratyantardasha tables are intentionally excluded from compact prompt paths to reduce hallucination risk.

### Ephemeris + geocoding (real engine)

- PyJHora needs **Swiss Ephemeris** (`pyswisseph`). On Windows, Python 3.13 may need **Microsoft C++ Build Tools** to compile it from source if no wheel is available.
- Birth place is resolved to latitude/longitude via **OpenStreetMap Nominatim** (network required the first time you geocode a place).
- Copy Swiss Ephemeris data into `jhora/data/ephe` if PyJHora prompts you (see PyJHora docs).

## Local Setup

1. Install Python 3.11+ from [python.org](https://www.python.org/downloads/).
2. Open PowerShell in this folder and create a venv:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
3. Install dependencies:
   - `python -m pip install --upgrade pip`
   - `python -m pip install -e .`
   - `python -m pip install -r requirements.txt`
   - `python -m pip install pyswisseph` (Swiss Ephemeris; see note below if this fails on Windows)
   - `pip install timezonefinder geopy`
4. Run the app:
   - `$env:ASTROLOGY_ENGINE="jhora"`
   - `python -m astrology_app.main`

### Engine Selection

- Default engine: `jhora` (PyJHora adapter).
- Optional fallback: `mock` adapter.
- To force mock mode in PowerShell:
  - `$env:ASTROLOGY_ENGINE="mock"`
  - `python -m astrology_app.main`

## Input Notes (Current CLI)

- Place accepts `City, Country` or `City, State, Country` (zip/postal text is allowed).
- Timezone accepts IANA format like `Asia/Kolkata` and aliases like `IST`.
- If timezone is blank, the app infers it only for supported single-timezone countries
  (currently includes India).
- Birth time is interpreted as local time at the entered birthplace + resolved timezone.

## Project Layout

- `src/astrology_app/main.py`: CLI entry point for user inputs.
- `src/astrology_app/chart_engine.py`: adapter boundary for open-source chart engine.
- `src/astrology_app/pyjhora_adapter.py`: PyJHora → normalized chart package (D1/D9, dasha, nakṣatra).
- `src/astrology_app/interpretation.py`: builds LLM evidence + prompt text from selected chart keys.
- `src/astrology_app/session_store.py`: in-memory session store (no long-term storage).
- `src/astrology_app/models.py`: typed input model.
