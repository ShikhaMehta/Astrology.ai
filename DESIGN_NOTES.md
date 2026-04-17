# Astrology.ai Design Notes

This document reflects the current codebase and the working local setup path that now produces real computed charts through PyJHora.

## 1. Product Snapshot

`Astrology.ai` is a desktop-first Python CLI for:

1. collecting birth details
2. validating and normalizing them
3. generating Vedic chart data through a pluggable engine
4. selecting question-relevant chart evidence
5. preparing a constrained interpretation context for a future LLM layer

The app does not yet call an LLM directly. It currently stops at evidence selection and prompt preview.

## 2. Current Working Architecture

Core modules:

- [`src/astrology_app/main.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/main.py)
  - CLI orchestration
- [`src/astrology_app/models.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/models.py)
  - `BirthInput`, `QuestionCategory`
- [`src/astrology_app/validation.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/validation.py)
  - validation, geocoding-driven timezone resolution, normalized input construction
- [`src/astrology_app/geocoding_utils.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/geocoding_utils.py)
  - Nominatim geocoding and `timezonefinder` lookup
- [`src/astrology_app/chart_engine.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/chart_engine.py)
  - engine selection and fallback behavior
- [`src/astrology_app/pyjhora_adapter.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/pyjhora_adapter.py)
  - real chart generation and normalization
- [`src/astrology_app/question_router.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/question_router.py)
  - question classification and evidence-path selection
- [`src/astrology_app/interpretation.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/interpretation.py)
  - evidence extraction and prompt scaffolding
- [`src/astrology_app/session_store.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/session_store.py)
  - session-only in-memory state

## 3. Engine Strategy

The engine layer is now explicitly three-mode:

- `ASTROLOGY_ENGINE=auto`
  - default
  - uses the real engine when dependencies are installed
  - falls back to `mock` when they are not
- `ASTROLOGY_ENGINE=jhora`
  - forces real PyJHora chart generation
- `ASTROLOGY_ENGINE=mock`
  - forces placeholder data

This adapter boundary is important because it keeps the rest of the application independent from PyJHora internals.

## 4. Input Resolution Flow

The effective runtime flow is now:

1. validate date format
2. validate time format
3. validate place structure
4. geocode the place with Nominatim
5. resolve timezone
   - use user-entered alias or IANA zone if valid
   - otherwise infer timezone from coordinates
6. return a fully populated `BirthInput` including:
   - `timezone_source`
   - `latitude`
   - `longitude`

This is a real improvement from the earlier duplicate-definition state in `validation.py`.

## 5. Current Data Flow

Actual runtime pipeline:

1. `collect_birth_input()`
2. `normalize_and_validate_birth_input()`
3. `build_chart_engine()`
4. `generate_chart_package()`
5. `categorize_question()`
6. `select_relevant_chart_keys()`
7. `build_interpretation_context()`
8. `build_llm_prompt()`

The final output shown to the user is:

- full normalized chart package
- selected interpretation context
- prompt preview

## 6. Chart Package Contract

Top-level keys:

- `source`
- `input`
- `metadata`
- `charts`
- `derived`
- `dashas`
- `nakshatras`
- `notes`

### `source`

Possible values:

- `mock-engine`
- `pyjhora-adapter`

### `input`

Now includes:

- `date_of_birth`
- `time_of_birth`
- `birth_place`
- `timezone`
- `timezone_source`
- `latitude`
- `longitude`

### `metadata`

Current real-engine metadata includes:

- `ayanamsha_mode: LAHIRI`
- `dasha_system: vimshottari`
- `charts_included`
- `status`
- `resolved_location`
  - latitude
  - longitude
  - timezone offset at birth

## 7. Real Chart Coverage

The real engine now computes these divisional charts:

- `D1`
- `D2`
- `D3`
- `D4`
- `D7`
- `D9`
- `D10`
- `D12`
- `D16`
- `D20`
- `D24`
- `D27`
- `D30`
- `D40`
- `D45`
- `D60`

Each normalized chart currently exposes:

- ascendant sign
- ascendant longitude in sign
- per-planet sign
- per-planet longitude in sign
- per-planet house relative to lagna

For `D1`, the planet entries also include:

- nakshatra
- pada

Non-core returned planet ids are safely ignored instead of crashing the adapter.

## 8. Derived D1 Features

The `derived` section now includes:

- `houses`
  - sign
  - occupants
  - graha drishti received
- `house_lords`
  - sign
  - lord
  - lord placement
- `dignities`
  - strength label from PyJHora matrices
  - derived dignity label
  - combustion flag
- `aspects`
  - graha drishti by planet
- `conjunctions`
  - multi-planet house conjunctions

This is the main bridge between raw chart generation and useful question-specific reasoning.

## 9. Dasha Support

Current dasha support is Vimshottari-based and now includes:

- `current_mahadasha`
- `current_antardasha`
- `current_pratyantardasha`
- Mahadasha sequence with start dates

This makes timing questions more useful than the earlier Maha-plus-Antara-only shape.

## 10. Question Routing

The question router is still keyword-based, but it now selects richer evidence slices.

Examples:

- career
  - `D1`, `D2`, `D10`, derived house lords, derived dignities, aspects, dashas
- family / children
  - `D1`, `D7`, `D12`, derived house lords, aspects, dashas
- spiritual
  - `D1`, `D9`, `D20`, house lords, nakshatras, dashas
- health
  - `D1`, `D30`, dignities, aspects, dashas

This is still heuristic routing, but it is materially better aligned with the actual chart package than before.

## 11. Privacy and State

The privacy model remains:

- session only
- no database
- no account system
- no persistent reading storage

`SessionStore` is still simple in-memory state.

Not implemented yet:

- TTL / expiration
- explicit clear-session command
- redacted structured logging
- export flow

## 12. Local Setup Reality

The practical local setup path that worked is:

- Python `3.11`
- virtual environment
- project installed editable
- optional `jhora` extras installed
- additional runtime packages needed on Windows:
  - `pytz`
  - `tzdata`
  - `python-dateutil`

Important note:

- Python `3.13` on Windows is currently high-friction for `pyswisseph`
- Python `3.11` is the recommended baseline for the real engine

## 13. Strengths

- clear engine abstraction
- real chart generation working end to end
- richer normalized contract than the original scaffold
- safe mock fallback
- better question-to-evidence routing
- validation now actually resolves place and timezone
- derived features bring the app closer to a usable interpretation layer

## 14. Remaining Gaps

Still missing or incomplete:

- direct LLM integration
- tests
- transit layer
- yoga detection
- richer confidence / uncertainty metadata
- GUI or web surface
- deeper question-specific feature extraction beyond the current derived layer

## 15. Design Risks

- geocoding depends on network access
- PyJHora runtime setup is still dependency-sensitive on Windows
- some evidence routing is still keyword-based rather than chart-rule based
- the adapter currently ignores non-core planets instead of exposing them in a controlled optional section

## 16. Recommended Next Steps

### Near-term

- add automated tests around:
  - validation
  - question routing
  - chart-package shape
  - mock vs real engine behavior
- update docs whenever runtime dependencies change
- add a smaller user-facing summary mode instead of only raw JSON

### Next feature layer

- transit support
- yoga detection
- more explicit child / marriage / career feature extraction
- direct LLM call using only `interpretation_context`

### Longer-term

- desktop or web UI
- saved sessions or export, if privacy policy changes
- configurable astrology conventions

## 17. Bottom Line

This project is no longer just a scaffold. It now has:

- working real chart generation
- multiple divisional charts
- derived D1 features
- richer dasha timing
- question-aware evidence selection
- a stable session-only CLI workflow

The main remaining design work is to turn this solid evidence pipeline into a true interpretation product with tests, transits, yogas, and an actual LLM-backed response layer.
