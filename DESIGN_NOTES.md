# Astrology.ai Design Notes

This document reflects the codebase as it exists now, not just the original plan. Where the implementation and intended design diverge, both are called out explicitly.

## 1. Product Snapshot

`Astrology.ai` is currently a desktop-first Python CLI for Vedic astrology chart generation and AI-ready interpretation context building.

The current user flow is:

1. Collect birth date, birth time, birth place, and timezone from the CLI.
2. Validate and normalize the input.
3. Generate a normalized chart package through a pluggable chart engine.
4. Ask a free-form astrology question.
5. Route the question to a broad category.
6. Select the relevant chart slices for that category.
7. Build an interpretation context and a constrained LLM prompt preview.
8. Keep all session data in memory only.

The app does not yet call an LLM directly. It prepares the evidence package and prompt that a future model call would consume.

## 2. Current Scope

### Implemented

- CLI-only interaction in [`src/astrology_app/main.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/main.py)
- In-memory session storage in [`src/astrology_app/session_store.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/session_store.py)
- Adapter-based engine selection in [`src/astrology_app/chart_engine.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/chart_engine.py)
- Real PyJHora-backed chart generation path in [`src/astrology_app/pyjhora_adapter.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/pyjhora_adapter.py)
- Mock chart engine for local development
- Question categorization and evidence selection
- LLM-safe interpretation prompt scaffolding

### Not Implemented Yet

- Desktop GUI
- Web or mobile UI
- Direct LLM API integration
- Persistent storage or account system
- Automated tests
- Rich chart rendering
- Advanced feature extraction such as yogas, dignity analysis, house lords, or transit overlays

## 3. Architecture

The project uses a small core-oriented architecture:

- `main.py`
  - CLI entry point
  - orchestrates input, validation, engine call, routing, interpretation context, and JSON output
- `models.py`
  - shared domain types
  - currently includes `BirthInput` and `QuestionCategory`
- `validation.py`
  - validates user-entered birth data and resolves timezone rules
- `chart_engine.py`
  - adapter boundary
  - chooses `jhora` or `mock` based on `ASTROLOGY_ENGINE`
- `pyjhora_adapter.py`
  - converts third-party PyJHora output into the app's normalized chart package
- `question_router.py`
  - maps user questions into broad categories and relevant evidence keys
- `interpretation.py`
  - extracts selected evidence and builds a constrained prompt preview
- `session_store.py`
  - keeps session state in memory only
- `geocoding_utils.py`
  - intended helper module for geocoding and timezone inference, but not currently the effective path at runtime

## 4. Engine Strategy

Engine selection is environment-driven:

- `ASTROLOGY_ENGINE=jhora`
  - default
  - uses `PyJHoraChartEngine`
  - attempts to import `jhora` first, then `pyhora`
- `ASTROLOGY_ENGINE=mock`
  - uses placeholder chart data

This keeps the application code decoupled from the third-party astrology library API. That separation is already working and is one of the strongest design choices in the codebase.

## 5. Implemented Data Flow

The actual runtime flow is:

1. `main.collect_birth_input()` reads CLI fields into `BirthInput`.
2. `normalize_and_validate_birth_input()` validates date, time, place, and timezone.
3. `build_chart_engine()` chooses the engine implementation.
4. `engine.generate_chart_package()` returns a normalized chart package.
5. `SessionStore` holds `birth_input`, `chart_package`, `question`, and `interpretation_context`.
6. `categorize_question()` assigns a broad domain such as career or relationships.
7. `select_relevant_chart_keys()` chooses which chart sections matter for that domain.
8. `build_interpretation_context()` copies only those evidence slices.
9. `build_llm_prompt()` generates a safety-constrained prompt preview.

## 6. Current Input Contract

`BirthInput` currently contains:

- `date_of_birth`: `YYYY-MM-DD`
- `time_of_birth`: `HH:MM` local civil time
- `birth_place`: free-text place string
- `timezone`: IANA name or alias
- `timezone_source`: default field exists on the model, but current effective validation does not populate it
- `latitude`: default field exists on the model, but current effective validation does not populate it
- `longitude`: default field exists on the model, but current effective validation does not populate it

Important nuance:

- The model has been expanded for geocoding-aware validation.
- The active validation function currently returns only the core text fields and leaves `timezone_source`, `latitude`, and `longitude` at defaults.
- The real chart engine geocodes the place again inside `pyjhora_adapter.py`.

## 7. Validation Rules

### Effective Runtime Rules

Because `validation.py` contains duplicate function definitions, the later definitions win at import time. The effective behavior today is:

- Date must parse as `YYYY-MM-DD`
- Time must parse as `HH:MM`
- Place must contain at least one comma and at least two segments
- Timezone handling:
  - accepts aliases such as `IST`, `INDIA`, `UTC`, `GMT`
  - accepts raw IANA timezone strings
  - if blank, falls back only for a small country-default map:
    - India -> `Asia/Kolkata`
    - Nepal -> `Asia/Kathmandu`
    - Sri Lanka -> `Asia/Colombo`
    - Bhutan -> `Asia/Thimphu`
  - otherwise raises a validation error requiring manual timezone entry

### Intended But Not Currently Effective

There is also an earlier validation implementation in the same file that appears to be the intended direction:

- geocode the place first
- infer timezone from coordinates
- set `timezone_source`
- store `latitude` and `longitude` on `BirthInput`

That path is currently shadowed by later duplicate definitions and is not the runtime behavior.

## 8. Geocoding and Timezone Design

There are two geocoding-related paths in the repo:

- [`src/astrology_app/geocoding_utils.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/geocoding_utils.py)
  - wraps `geopy.Nominatim` and `timezonefinder`
  - intended for validation-time place resolution and timezone inference
- [`src/astrology_app/pyjhora_adapter.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/pyjhora_adapter.py)
  - performs its own `Nominatim` geocode during chart generation
  - calculates timezone offset at birth using `zoneinfo`

Current reality:

- Place geocoding definitely happens in `pyjhora_adapter.py`
- Timezone inference from coordinates is not currently active in validation
- `geocoding_utils.py` raises `ValidationError` but does not import it, so that module would error if invoked directly

## 9. Chart Package Contract

The app already has a meaningful normalized output contract.

Top-level structure:

- `source`
- `input`
- `metadata`
- `charts`
- `dashas`
- `nakshatras`
- `notes`

### Metadata

Current metadata includes:

- `ayanamsha_mode`: `LAHIRI` in the PyJHora path
- `dasha_system`: `vimshottari`
- `charts_included`: `["d1", "d9"]`
- `status`: `computed` or mock status
- `resolved_location`:
  - latitude
  - longitude
  - timezone offset at birth

### Charts

Each chart currently stores:

- `ascendant`
  - sign
  - longitude within sign
  - house
- `planets`
  - per-planet sign
  - longitude within sign
  - relative house from lagna
  - D1 also includes per-planet nakshatra and pada

Implemented charts:

- D1
- D9

Not yet included despite earlier planning:

- house lord mapping
- aspects
- yogas
- dignity evaluation
- additional vargas such as D10 or D7

### Nakshatras

`nakshatras` currently includes:

- `moon`
  - name
  - pada
- `by_planet`
  - per-planet nakshatra and pada

### Dashas

`dashas` currently includes:

- `current_mahadasha`
- `current_antardasha`
- `as_of`
  - julian day
  - note about timezone convention
- `sequence`
  - Mahadasha lord with start date components

## 10. Astrology Conventions Locked in Code

The code effectively locks several V1 conventions already:

- Ayanamsha: Lahiri
- Dasha system: Vimshottari
- Core charts: D1 and D9
- House numbering:
  - derived relative to lagna sign in serialized chart output
- Birth time interpretation:
  - local civil time in the resolved timezone

Still not formally represented in the normalized contract:

- house system naming
- aspect doctrine
- yoga catalog
- rectification or unknown-time policy

## 11. Question Routing Design

Question routing is keyword-based and intentionally simple.

Supported categories in `QuestionCategory`:

- personality
- career
- relationships
- family
- health
- spiritual
- timing
- general

Evidence selection by category is hard-coded:

- personality -> D1, D9, nakshatras
- career -> D1, D9, dashas
- relationships -> D1, D9, dashas, nakshatras
- family -> D1, dashas
- health -> D1, dashas
- spiritual -> D9, nakshatras, dashas
- timing -> dashas, D1
- general -> D1, D9, dashas, nakshatras

This is a useful V1 baseline, but it is still heuristic rather than astrology-rule driven.

## 12. Interpretation Layer

The interpretation layer is deliberately narrow and evidence-first.

`build_interpretation_context()`:

- receives the full chart package
- pulls only the requested dotted paths
- returns a smaller evidence bundle

`build_llm_prompt()` currently enforces:

- use only provided chart evidence
- state when evidence is insufficient
- avoid deterministic or fear-based claims
- explain uncertainty where relevant

This is a good safety-oriented design foundation for a future LLM integration.

## 13. Privacy and State

The privacy model is still session-only:

- no database
- no file persistence for user readings
- no account system
- `SessionStore` is simple in-memory state

What is not yet implemented:

- explicit expiry timeout
- manual clear-session command in the CLI
- logging redaction policy
- export flow

## 14. Dependencies

The codebase currently relies on:

- Python 3.11+
- `PyJHora==4.8.0`
- `geopy`
- `geocoder`
- `pyswisseph` at runtime for Swiss Ephemeris support
- `timezonefinder` is used by code but is not currently listed in `requirements.txt`

There is also a `vendor/wheels` directory containing:

- `pyjhora-4.8.0-py3-none-any.whl`
- `pyswisseph-2.10.3.2.tar.gz`

## 15. Strengths of the Current Design

- Clear adapter boundary around the astrology engine
- Reusable core modules that are mostly UI-agnostic
- A normalized chart package rather than leaking raw third-party structures
- Session-only privacy posture
- Early evidence-selection layer before interpretation
- Built-in mock engine for development

## 16. Current Gaps and Risks

### Code/Design Drift

- `DESIGN_NOTES` originally described a future system, not the actual code.
- `README.md`, `models.py`, `validation.py`, and `pyjhora_adapter.py` are not fully aligned on where geocoding and timezone inference happen.

### Validation Inconsistency

- `validation.py` contains duplicate definitions for:
  - `normalize_and_validate_birth_input`
  - `_resolve_timezone`
- The later definitions override the earlier ones.
- This makes the intended geocoding-aware validation path inactive.

### Helper Module Bug

- `geocoding_utils.py` references `ValidationError` without importing it.

### Repeated Geocoding

- Place resolution is done inside the PyJHora adapter even though the model suggests it should happen during validation.
- That means validation and chart generation are not sharing one resolved location source of truth yet.

### Missing Structured Features

- No house lords
- No aspects
- No yogas
- No dignity states
- No transit layer
- No confidence or uncertainty metadata beyond prompt wording

### Operational Risk

- Geocoding depends on network access to OpenStreetMap Nominatim.
- Swiss Ephemeris setup may still be environment-sensitive, especially on Windows.

## 17. Recommended Design Direction

The cleanest next design step is to make validation and chart generation share one normalized resolved-input object.

Recommended target flow:

1. Validate date, time, and place text.
2. Resolve place once into latitude and longitude.
3. Infer or validate timezone once.
4. Store `timezone_source`, `latitude`, and `longitude` on `BirthInput`.
5. Pass the resolved input into the chart adapter without re-geocoding.
6. Keep the chart package focused on astrology output rather than duplicated location work.

That would remove the current split-brain behavior between `validation.py` and `pyjhora_adapter.py`.

## 18. Suggested Near-Term Milestones

### M1. Reconcile Input Resolution

- remove duplicate validation definitions
- fix `geocoding_utils.py`
- choose one authoritative geocoding/timezone path
- ensure `BirthInput` is fully populated before chart generation

### M2. Stabilize Output Contract

- decide whether `resolved_location` belongs in `input`, `metadata`, or both
- add house lords and aspects if needed for interpretation
- make D1/D9 structures consistent with the evidence router's needs

### M3. Add Direct Interpretation Execution

- plug in an LLM provider
- pass only `interpretation_context`, not the full raw chart package
- keep the current prompt safety rules

### M4. Add Tests

- validation tests
- question routing tests
- mock engine contract tests
- adapter smoke tests for normalized chart shape

## 19. Open Questions

- Should geocoding happen during validation only, or should the engine remain responsible for place resolution?
- Should timezone be mandatory for all non-single-timezone countries even if coordinate inference is available?
- How much astrology structure should be normalized in-house versus passed through from PyJHora?
- Is the next UI step a desktop GUI, or should the core now be exposed through a local API boundary first?

## 20. Bottom Line

The codebase is no longer just a scaffold. It already has a real end-to-end CLI pipeline, a working engine abstraction, PyJHora-backed D1/D9 and Vimshottari support, question routing, and an AI-ready evidence layer.

The main design work now is not inventing the architecture from scratch. It is reconciling the input-resolution path, locking the normalized data contract, and turning the current prompt-preview flow into a true interpretation pipeline.
