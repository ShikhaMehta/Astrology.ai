# Astrology.ai

Astrology.ai is a desktop-first Python CLI for Vedic astrology chart generation and AI-assisted interpretation.

The app collects birth details and a question, validates and normalizes the location/timezone, generates Vedic chart evidence through a pluggable chart engine, selects the chart slices relevant to the question, builds a compact interpretation context, optionally asks OpenAI for an answer, and saves the session as readable and machine-readable exports.

## What It Does

- Generates normalized Vedic chart packages from birth date, birth time, birthplace, and timezone.
- Uses a real PyJHora-backed engine when available, with a mock fallback for setup-light runs.
- Resolves birth location through geocoding and infers timezone when possible.
- Routes questions into categories such as career, relationships, family, health, spiritual, timing, personality, and general.
- Builds compact evidence bundles so AI prompts use only relevant chart factors instead of dumping the entire chart tree.
- Produces a deterministic local interpretation summary from the structured evidence.
- Optionally calls OpenAI when `OPENAI_API_KEY` is set.
- Saves each run into `exports/` as JSON, Markdown, and a copy/paste prompt file.

## Current Status

The current app is a working CLI evidence and interpretation pipeline, not just a scaffold.

- Engine selection is adapter-driven: `auto`, `jhora`, or `mock`.
- The real engine computes D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30, D40, D45, and D60 when PyJHora is available.
- D1 entries include nakshatra and pada.
- Derived features include houses, house lords, dignities, aspects, conjunctions, ashtakavarga summary, and special conditions where available.
- Timing evidence includes Vimshottari dasha sequence and current maha, antara, and pratyantara periods.
- Current transits are included in the real chart package.
- Relationship timing includes yearly Jupiter/Saturn style transit support.
- Scripted runs can attach a requested transit ephemeris window for career-style prediction ranges.

## Compact Evidence for AI

Large raw chart exports can confuse an LLM, especially for health, relationship, career, and timing questions. The app therefore trims each category into a smaller evidence bundle before building `reading_input`, OpenAI payloads, and prompt exports.

Compact bundles preserve high-signal chart factors, current dasha periods, nearby dasha context, and question-specific structured facts. Full lifetime antardasha and pratyantardasha tables are intentionally excluded from compact prompt paths unless a focused feature asks for them.

The app also supports small requested evidence additions:

- `comprehensive_reading: true` in `bin/run_saved_query.py` includes every divisional chart (`d1` through `d60`) plus full derived, dasha, transit, and sudarshana evidence instead of a category-compact bundle.
- `requested_chart_keys` in `bin/run_saved_query.py` can include extra full chart sections such as `["d3", "d9", "d12"]`; charts already represented by the selected evidence are skipped to avoid duplicate paste payloads.
- If the question names a specific chart/factor, such as `D1 5th lord Saturn nakshatra`, the app adds a compact `requested.query_focus` block.
- Scripted prediction windows can add a monthly, weekly, or daily transit ephemeris window.

## Local Setup

1. Install Python 3.11+.
2. Create and activate a virtual environment:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
3. Install the project:
   - `python -m pip install --upgrade pip`
   - `python -m pip install -e .`
   - `python -m pip install -r requirements.txt`
4. Install the real-engine extras when you want PyJHora:
   - `python -m pip install -e ".[jhora]"`
   - If needed, install the vendored PyJHora wheel from `vendor/wheels/`.

PyJHora may require Swiss Ephemeris data under `jhora/data/ephe`. On Windows, Python 3.11 is the recommended baseline because newer Python versions can be higher-friction for `pyswisseph`.

## Running the App

Interactive CLI:

```powershell
$env:ASTROLOGY_ENGINE="jhora"
python -m astrology_app.main
```

Local web app:

```powershell
$env:ASTROLOGY_ENGINE="jhora"
python -m astrology_app.web
```

Then open `http://127.0.0.1:8000`. The web app keeps the current human-in-the-loop flow:
it generates chart evidence, a local interpretation, and a copy/paste AI prompt, but it
does not call DeepSeek directly.

Scripted run:

```powershell
$env:ASTROLOGY_ENGINE="jhora"
python bin/run_saved_query.py
```

Mock mode:

```powershell
$env:ASTROLOGY_ENGINE="mock"
python -m astrology_app.main
```

## Engine Selection

- `ASTROLOGY_ENGINE=auto`: uses PyJHora if dependencies are available, otherwise falls back to mock.
- `ASTROLOGY_ENGINE=jhora`: requires the real PyJHora runtime and fails with setup guidance if unavailable.
- `ASTROLOGY_ENGINE=mock`: uses deterministic placeholder data for development.

## OpenAI Answers

OpenAI integration is optional. If `OPENAI_API_KEY` is set, the CLI sends the selected evidence and structured reading input to the OpenAI Responses API.

Optional environment variables:

- `OPENAI_API_KEY`: enables OpenAI answers.
- `OPENAI_MODEL`: overrides the default model, currently `gpt-4.1-mini`.

If OpenAI is not configured, the app still generates the local interpretation answer, prompt preview, and exports.

## Input Notes

- Date format: `YYYY-MM-DD`.
- Time format: `HH:MM`, interpreted as local birth time at the birthplace.
- Place accepts `City, Country` or `City, State, Country`.
- Timezone accepts IANA names such as `Asia/Kolkata` and common aliases such as `IST`.
- If timezone is blank, validation attempts to infer it from the resolved location.

## Scripted Runs

Edit `QUERY_CONFIG` in `bin/run_saved_query.py` when you want repeatable runs without answering prompts.

Supported fields:

- `date_of_birth`
- `time_of_birth`
- `birth_place`
- `timezone`
- `question`
- `client_context`
- `answer_style`
- `comprehensive_reading`
- `requested_chart_keys`
- optional `prediction_window`

Example prediction window:

```python
"prediction_window": {
    "start_date": "2026-01-01",
    "end_date": "2027-12-31",
    "step": "monthly",
}
```

If no explicit `prediction_window` is set, the script can infer a monthly window from a year or year range in the question.
It also understands month/year ranges such as `3/2009-12/2013`, which become `2009-03-01` through `2013-12-31`. When a requested window is present, it is included in the selected evidence even for non-career questions.

Use `client_context` for known facts that should calibrate the reading, such as "financially comfortable, owns home, not struggling" or "career started in 2021." This helps the AI reconcile mixed chart evidence instead of defaulting to generic textbook assumptions.

Use `answer_style` when you want the exported prompt to ask DeepSeek for a specific shape, such as a concise chronological timeline instead of a detailed prose reading.

## Exports

Each run clears old session exports and writes a fresh set into `exports/`:

- `*_session.json`: compact machine-readable session payload.
- `*_session.md`: readable session summary.
- `*_session_for_ai.txt`: constrained prompt for copy/paste use.

The export intentionally records evidence scope so the AI answer does not imply missing factors were analyzed.

## Project Layout

- `bin/run_saved_query.py`: editable scripted runner for fixed birth details and questions.
- `src/astrology_app/main.py`: interactive CLI entry point.
- `src/astrology_app/web.py`: local browser UI for collecting birth details and preparing readings.
- `src/astrology_app/pipeline.py`: shared one-session pipeline used by the web app.
- `src/astrology_app/chart_engine.py`: engine selection and adapter boundary.
- `src/astrology_app/pyjhora_adapter.py`: PyJHora to normalized chart package.
- `src/astrology_app/validation.py`: input validation, geocoding, and timezone resolution.
- `src/astrology_app/question_router.py`: keyword question classification and evidence-key selection.
- `src/astrology_app/interpretation.py`: evidence extraction, compact contexts, and prompt building.
- `src/astrology_app/question_features.py`: question-specific structured feature extraction.
- `src/astrology_app/llm_openai.py`: optional OpenAI Responses API integration.
- `src/astrology_app/export_utils.py`: JSON, Markdown, and prompt exports.
- `src/astrology_app/session_store.py`: in-memory session state.
- `src/astrology_app/models.py`: shared dataclasses and question category enum.

## Privacy Model

The app has no account system and no database. Runtime session state is in memory only, and export files are local to the project workspace.
