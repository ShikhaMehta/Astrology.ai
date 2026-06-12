# Astrology.ai Design Notes

This document reflects the current local codebase: a desktop-first Python CLI that turns birth details and a user question into Vedic chart evidence, compact interpretation input, optional OpenAI output, and local exports.

## 1. Product Snapshot

`Astrology.ai` is an evidence-first astrology assistant. Its core job is not to let an LLM freely reason over a huge raw chart dump. Instead, it computes a chart package, selects the evidence relevant to the question, extracts structured signals, and gives the model a constrained prompt with explicit scope limits.

Current user workflows:

1. Interactive CLI: `python -m astrology_app.main`
2. Scripted local runner: `python bin/run_saved_query.py`
3. Optional OpenAI answer when `OPENAI_API_KEY` is configured
4. Local exports in JSON, Markdown, and copy/paste prompt formats

## 2. Current Architecture

Core modules:

- [`src/astrology_app/main.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/main.py): interactive CLI orchestration.
- [`bin/run_saved_query.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/bin/run_saved_query.py): repeatable file-edited query runner.
- [`src/astrology_app/models.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/models.py): `BirthInput` and `QuestionCategory`.
- [`src/astrology_app/validation.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/validation.py): validation, geocoding-driven timezone resolution, normalized input construction.
- [`src/astrology_app/geocoding_utils.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/geocoding_utils.py): Nominatim geocoding and `timezonefinder` lookup.
- [`src/astrology_app/chart_engine.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/chart_engine.py): real/mock engine selection and fallback behavior.
- [`src/astrology_app/pyjhora_adapter.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/pyjhora_adapter.py): real chart generation and normalization.
- [`src/astrology_app/question_router.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/question_router.py): keyword category routing and evidence-path selection.
- [`src/astrology_app/interpretation.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/interpretation.py): compact evidence extraction and prompt scaffolding.
- [`src/astrology_app/question_features.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/question_features.py): structured reading input by question type.
- [`src/astrology_app/llm_openai.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/llm_openai.py): optional OpenAI Responses API call.
- [`src/astrology_app/export_utils.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/export_utils.py): compact export writer.
- [`src/astrology_app/session_store.py`](/c:/Users/Shikha/AstrologyApp/Astrology.ai/src/astrology_app/session_store.py): session-only in-memory state.

## 3. Runtime Flow

Interactive flow:

1. Collect birth details and question.
2. Normalize and validate date, time, place, and timezone.
3. Build the selected chart engine.
4. Generate the normalized chart package.
5. Categorize the question.
6. Select relevant chart/evidence keys.
7. Build the compact interpretation context.
8. Build structured `reading_input`.
9. Generate a deterministic local interpretation answer.
10. Build an LLM prompt preview.
11. Optionally call OpenAI.
12. Save compact exports.

Scripted flow is the same, but birth details and the question come from `QUERY_CONFIG`. The scripted runner can also attach `requested_chart_keys`, an `answer_style`, and an optional transit `prediction_window`; requested charts are appended only when that chart is not already represented in the selected evidence.

## 4. Engine Strategy

The engine layer has three modes:

- `ASTROLOGY_ENGINE=auto`: default behavior, uses PyJHora if available and falls back to mock.
- `ASTROLOGY_ENGINE=jhora`: forces the real PyJHora adapter and reports setup guidance if dependencies are missing.
- `ASTROLOGY_ENGINE=mock`: forces placeholder data for development.

The adapter boundary keeps the rest of the application independent from PyJHora internals.

## 5. Input Resolution

The normalized input path:

1. Validate date format.
2. Validate time format.
3. Validate place structure.
4. Geocode the place with Nominatim.
5. Resolve timezone from user input, alias, or coordinates.
6. Return `BirthInput` with `timezone_source`, `latitude`, and `longitude`.

Birth time is interpreted as local time at the resolved birthplace.

## 6. Chart Package Contract

Top-level real-engine keys include:

- `source`
- `input`
- `metadata`
- `charts`
- `derived`
- `dashas`
- `nakshatras`
- `transits`
- `sudarshana_chakra`
- `notes`

`source` values:

- `pyjhora-adapter`
- `mock-engine`

`metadata` includes ayanamsha mode, dasha system, included charts, runtime status, and resolved location details.

## 7. Real Chart Coverage

The real engine currently computes:

- D1, D2, D3, D4, D7, D9, D10, D12, D16, D20, D24, D27, D30, D40, D45, D60

Each normalized chart exposes:

- ascendant sign
- ascendant longitude in sign
- per-planet sign
- per-planet longitude in sign
- per-planet house relative to lagna

D1 planet entries also include nakshatra and pada. Unsupported/non-core planet IDs are ignored instead of crashing the adapter.

## 8. Derived Features

The `derived` section currently includes:

- houses with sign, occupants, and graha drishti received
- house lords and lord placements
- dignity labels and combustion flags
- graha drishti aspects by planet
- conjunction groups
- ashtakavarga summary where available
- special conditions such as gandanta where available

These features are the bridge between raw chart data and question-specific reasoning.

## 9. Timing and Transit Support

Timing layers currently include:

- Vimshottari current mahadasha
- current antardasha
- current pratyantardasha
- mahadasha sequence with dates
- compact nearby dasha windows for selected prompt paths

Transit layers currently include:

- current transit snapshot in the real chart package
- yearly relationship timing transit support
- scripted requested transit windows via `bin/run_saved_query.py`

Requested transit windows can be daily, weekly, or monthly. The scripted runner accepts exact dates and month/year ranges like `3/2009-12/2013`; month/year ranges are expanded to the first day of the starting month and the last day of the ending month. If a compact category path does not already expose the window, it is added as `requested.transit_window`. The compact career evidence path also summarizes repeated Jupiter, Saturn, and Rahu links to natal career/resource houses when such a window is attached.

## 10. Question Routing

The router is keyword-based and intentionally simple. It maps a question into:

- personality
- career
- relationships
- family
- health
- spiritual
- timing
- general

Each category selects evidence keys before `interpretation.py` compacts them into a smaller category-aware shape.

Examples:

- Career: D1, D2, D4, D9, D10, D60, derived houses/lords/dignities/aspects, ashtakavarga, special conditions, nakshatras, dashas.
- Relationships: D1, D7, D9, derived features, transits, nakshatras, dashas.
- Family: D1, D3, D7, D9, D12, derived features, dashas.
- Health: D1, D6, D8, D30, Sudarshana Chakra, transits, dashas.
- Spiritual: D1, D9, D20, house lords, nakshatras, dashas.

## 11. Interpretation and LLM Layer

There are three output layers:

1. `interpretation_answer`: deterministic local text generated from structured evidence.
2. `llm_prompt`: a copy/paste prompt preview with evidence scope and guardrails.
3. `openai_answer`: optional OpenAI answer when `OPENAI_API_KEY` is available.

The OpenAI call uses the Responses API and sends only the selected evidence and `reading_input`. It instructs the model to avoid invented placements, yogas, doshas, transits, deterministic claims, or unsupported exact timing.

## 12. Exports

Every run writes a compact export set under `exports/`:

- `*_session.json`: compact structured payload.
- `*_session.md`: readable summary.
- `*_session_for_ai.txt`: constrained prompt for external AI use.

Before writing a new session, the export utility deletes previous `*_session.*` files. Exports are local files only.

The export payload intentionally preserves evidence scope:

- included charts
- included evidence keys
- included timing layers
- included transit limits
- missing layers that should not be inferred

## 13. Privacy and State

The app has:

- no accounts
- no database
- no remote storage owned by the app
- in-memory runtime session state
- local export files in the project workspace

If OpenAI is configured, selected evidence is sent to the OpenAI API for the optional answer.

## 14. Local Setup Reality

Recommended baseline:

- Python 3.11
- virtual environment
- editable project install
- optional `jhora` extras for real chart generation

Windows notes:

- Python 3.13 can be high-friction for `pyswisseph`.
- `pytz`, `tzdata`, and `python-dateutil` may be needed by the PyJHora path.
- Geocoding requires network access for new places.

## 15. Strengths

- Real chart generation works end to end through PyJHora.
- The engine adapter makes mock/real switching straightforward.
- The normalized chart contract is richer than raw PyJHora output.
- Question-aware evidence compaction reduces hallucination risk.
- Exports make results auditable and reusable.
- Optional OpenAI integration is isolated and can fail gracefully.
- The scripted runner makes repeated chart questions fast to iterate.

## 16. Remaining Gaps

Known gaps:

- No automated tests are currently installed/running in this environment.
- Routing is keyword-based, not semantic.
- OpenAI model choice is environment-driven but still hardcoded to a default.
- Export deletion keeps only the latest session by design, which may not fit future history needs.
- Transit support exists, but deeper yoga, varshaphala, shadbala, and richer predictive systems are still incomplete or absent unless explicitly present in evidence.
- No GUI or web interface yet.

## 17. Recommended Next Steps

Near term:

- Add tests around validation, question routing, chart package shape, export scope, and OpenAI-off behavior.
- Add tests or fixtures for compact evidence paths by category.
- Document exact dependency setup for the local Windows environment.
- Consider preserving export history behind a config flag.

Next feature layer:

- Improve semantic question routing.
- Expand yoga and strength systems only when they can be surfaced with explicit evidence.
- Make transit-window support available from the interactive CLI, not only the scripted runner.
- Add a small desktop or web UI once the evidence contract stabilizes.

## 18. Bottom Line

The project is now a working local astrology evidence pipeline. It computes real Vedic chart data, distills that data into question-specific evidence, produces local and optional OpenAI interpretations, and saves compact scoped exports.

The next major engineering work is reliability: tests, dependency documentation, and tighter user-facing workflows around repeated sessions and prediction windows.
