# Astrology.ai

Desktop-first Python CLI for Vedic astrology chart generation and AI-ready interpretation context.

## Current Status

The app now supports:

- session-only CLI flow
- input validation with place geocoding and timezone inference
- adapter-based engine selection
- real PyJHora chart generation
- mock fallback when the real runtime is unavailable
- question routing and evidence selection for later LLM interpretation

When the real engine is active, the app computes:

- divisional charts: `D1`, `D2`, `D3`, `D4`, `D7`, `D9`, `D10`, `D12`, `D16`, `D20`, `D24`, `D27`, `D30`, `D40`, `D45`, `D60`
- nakshatras
- Vimshottari dasha summary
- derived D1 features:
  - house occupancies
  - house lords
  - dignities
  - graha drishti
  - conjunctions

## Engine Modes

The app supports three engine modes via `ASTROLOGY_ENGINE`:

- `auto`
  - default
  - uses the real PyJHora engine if its runtime dependencies are available
  - otherwise falls back to `mock`
- `jhora`
  - forces the real PyJHora engine
  - useful for verifying setup
- `mock`
  - always uses placeholder chart data

PowerShell examples:

```powershell
$env:ASTROLOGY_ENGINE="auto"
python -m astrology_app.main
```

```powershell
$env:ASTROLOGY_ENGINE="jhora"
python -m astrology_app.main
```

```powershell
$env:ASTROLOGY_ENGINE="mock"
python -m astrology_app.main
```

## Recommended Local Setup

Python `3.11` is currently the most reliable choice on Windows for the real engine.

### 1. Create and activate a venv

```powershell
py -3.11 -m venv .venv311
.venv311\Scripts\Activate.ps1
python --version
```

### 2. Upgrade pip

```powershell
python -m pip install --upgrade pip
```

### 3. Install the project

```powershell
python -m pip install -e .
```

### 4. Install the real-engine dependencies

```powershell
python -m pip install ".[jhora]"
python -m pip install pytz tzdata python-dateutil
```

Notes:

- `pyswisseph` is required by PyJHora for Swiss Ephemeris support.
- On Python `3.13` on Windows, `pyswisseph` may try to build from source and require Microsoft C++ Build Tools.
- Using Python `3.11` avoids most of that friction.

## Verify Real Chart Generation

Run:

```powershell
$env:ASTROLOGY_ENGINE="jhora"
python -m astrology_app.main
```

You are using the real engine when the printed chart package contains:

```text
"source": "pyjhora-adapter"
```

If it contains:

```text
"source": "mock-engine"
```

then the app is still using placeholder data.

## Runtime Notes

- Birth place is geocoded through OpenStreetMap Nominatim.
- Timezone can be entered manually or inferred from the geocoded coordinates.
- Birth time is interpreted as local civil time at the birthplace.
- Data is kept in memory only for the current session.

## Project Layout

- `src/astrology_app/main.py`
  - CLI entry point
- `src/astrology_app/validation.py`
  - input validation, geocoding, timezone resolution
- `src/astrology_app/geocoding_utils.py`
  - geocoding and timezone inference helpers
- `src/astrology_app/chart_engine.py`
  - engine selection and adapter boundary
- `src/astrology_app/pyjhora_adapter.py`
  - PyJHora to normalized chart package mapping
- `src/astrology_app/question_router.py`
  - question categorization and evidence selection
- `src/astrology_app/interpretation.py`
  - interpretation context and prompt preview builder
- `src/astrology_app/session_store.py`
  - in-memory session state
- `src/astrology_app/models.py`
  - shared typed models

## Current Limitations

- no GUI yet
- no direct LLM call yet
- no persistence or accounts
- no automated tests yet
- no transit layer yet
- no yoga detection yet

The app currently prepares high-signal astrology evidence for interpretation, but does not yet generate the final AI reading itself.

## OpenAI Integration

The app can now call OpenAI using the structured `reading_input` object instead of the full raw chart JSON.

Set your API key in PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

Optional model override:

```powershell
$env:OPENAI_MODEL="gpt-4.1-mini"
```

Then run:

```powershell
python -m astrology_app.main
```

If `OPENAI_API_KEY` is set, the CLI will print:

- `Interpretation answer:` from the local rule-based layer
- `OpenAI answer:` from the OpenAI Responses API

The saved session export will also include `openai_answer`.
