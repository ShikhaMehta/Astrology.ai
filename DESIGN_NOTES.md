# Astrology.ai Design Notes

Use this file to capture ideas, decisions, and open questions before coding.

## 1) Vision

- What problem am I solving?
- Who is the primary user?
- What should users be able to do in version 1?

Notes:


## 2) Scope (V1)

### Included in V1

- Input birth date, time, location
- Generate core Vedic charts using PyHora
- Ask questions and get AI interpretation

### Not Included in V1

- Example: multi-user accounts
- Example: long-term storage
- Example: payments

Notes:


## 3) Astrology Conventions to Use

- Ayanamsha:
- House system:
- Dasha system:
- Core charts in V1 (example: D1, D9):
- Yogas to include in V1:

Notes:


## 4) Input and Validation Design

### User Inputs

- Date of birth:
- Time of birth:
- Place of birth:
- Timezone (auto/manual):

### Validation Rules

- How to handle unknown birth time?
- How to handle ambiguous city names?
- How to handle invalid dates/timezones?

Notes:


## 5) Data Flow (High Level)

1. User inputs data
2. App validates and normalizes data
3. PyHora generates chart outputs
4. Feature extractor creates structured features
5. Question router selects relevant features
6. LLM interprets selected features
7. Response shown to user

Notes:


## 6) Internal Data Contract (Draft)

What key fields should be available for interpretation?

- Planetary positions:
- Houses and lords:
- Aspects:
- Nakshatras:
- Dasha periods:
- Yogas:

Notes:


## 7) Question Categories (Draft)

Potential categories:

- Personality and life direction
- Career and finances
- Marriage and relationships
- Family and children
- Health tendencies
- Spiritual growth
- Timing windows (dasha/transit-driven)

Notes:


## 8) AI Interpretation Rules

- Tone (traditional/spiritual/practical):
- Allowed claims:
- Avoided claims:
- How uncertainty should be expressed:
- How to cite chart evidence in responses:

Notes:


## 9) Privacy and Session-Only Policy

- Data stored only in memory during session
- No long-term database
- Session expiry timeout:
- Manual clear session action:
- Logging redaction strategy:
- Optional export behavior:

Notes:


## 10) UX Ideas

- CLI first or Web UI first?
- Single question mode vs guided reading mode
- Show chart evidence with each interpretation?
- How much detail per response?

Notes:


## 11) Risks and Mitigations

- Incorrect chart due to bad timezone/location
- Misinterpretation by LLM
- Overconfident or deterministic predictions
- User confusion around uncertainty

Notes:


## 12) Milestones

- M1: Finalize V1 scope and conventions
- M2: Finalize data schema and routing matrix
- M3: Build chart generation pipeline
- M4: Build interpretation pipeline
- M5: End-to-end test with known cases

Notes:


## 13) Open Questions

- Q1:
- Q2:
- Q3:


## 14) Architecture Decisions (Locked for Now)

- Platform strategy:
  - V1: Desktop app
  - V2: Web app
  - V3 (optional): Mobile app
- Core logic separation:
  - Astrology and AI logic must be UI-agnostic and reusable across desktop/web/mobile.
- Single source of truth:
  - One shared "core engine" for validation, chart generation, feature extraction, and interpretation context building.
- Adapter pattern for PyHora:
  - Wrap PyHora in an internal adapter module so the library can be replaced or upgraded without rewriting app logic.
- Session-only data policy:
  - No persistent storage of birth details or generated readings by default.
  - Keep data in memory only for active session.
- Privacy-first logging:
  - Redact or avoid logging personally identifying birth data.
- API-ready design from day one:
  - Even in desktop phase, structure modules as if they could be exposed by an API later.

Notes:


## 15) Week 1 Checklist (Design + Proof of Chart Pipeline)

Goal: prove we can take user inputs, generate correct charts with PyHora, and produce a clean internal data object that can later feed both a desktop UI and an LLM.

### Day 1: Define V1 Inputs + Output Contract

- Decide the minimum required inputs:
  - Date of birth (YYYY-MM-DD)
  - Time of birth (HH:MM, 24-hour)
  - Place of birth (city, region, country)
  - Timezone handling (auto from place vs manual override)
- Decide how to represent place internally:
  - Option A: store lat/long + timezone string
  - Option B: store place text + resolved lat/long/timezone
- Decide the internal output contract (what “chart package” contains):
  - D1 (Rasi): signs per house, planets per sign/house
  - D9 (Navamsa): same structure
  - Nakshatras (planet -> nakshatra/pada)
  - Vimshottari dasha (at least: maha dasha sequence + current period)
  - Metadata: ayanamsha, calculation settings, source (PyHora), timestamps (session only)

### Day 2: Lock Astrology Conventions (No Ambiguity)

- Ayanamsha: pick one (default suggestion: Lahiri) and stick to it for all outputs.
- House system / chart style: define how we display and store houses/signs (North Indian / South Indian only affects rendering, not core data).
- Dasha: confirm Vimshottari (V1).
- Divisional charts in V1: D1 + D9 only (add more later once the pipeline is stable).

### Day 3: Decide What “Extensive Charts” Means (V1 vs Later)

- V1 “extensive” = not “all charts”; it means “enough for good readings”:
  - D1 + D9
  - planetary dignities (own/exalt/debil etc. if available)
  - house lordships
  - aspects (as supported by engine)
  - dashas (timing)
- Later expansion candidates:
  - more divisional charts (D10, D7, D2, etc.)
  - transit layer
  - yoga detection
  - rectification support (birth time uncertainty)

### Day 4: Error Handling + Validation Policy

- Define validation outcomes:
  - Hard errors: missing/invalid date/time, cannot resolve place, impossible timezone
  - Soft warnings: unknown birth time accuracy, approximate location match, DST ambiguity
- Define “traceability” requirements:
  - Every generated reading must reference the key chart evidence used.
  - LLM is not allowed to invent chart facts; it only interprets provided facts.

### Day 5: Desktop MVP UX Sketch (Still No Implementation)

- Screen 1: Birth input form
- Button: Generate charts
- Output view:
  - “Raw data” tab (structured data)
  - “Human summary” tab (positions + dashas)
- Screen 2: Ask question
- Output: AI interpretation + evidence list

### Acceptance Criteria for Week 1 (So We Know We’re Done)

- We can describe a single deterministic pipeline:
  - inputs -> validation -> chart generation -> feature extraction -> question context -> interpretation
- We have a written internal output contract for the “chart package”.
- We have locked conventions (ayanamsha/dasha/charts) for V1.
- We have a clear definition of “extensive” for V1 vs later.


## 16) Session Handoff (Current Progress + Next Steps)

Use this section to resume quickly if the chat/session resets.

### Current Project State

- GitHub repo is connected and initial files are pushed.
- Design planning is complete through architecture and Week 1 checklist.
- Initial code scaffold is created (desktop-first, session-only approach).
- Python installation is currently in progress on local machine.

### Files Already Created (Code Scaffold)

- `src/astrology_app/main.py`
  - CLI input flow for DOB, time, place, timezone.
- `src/astrology_app/models.py`
  - `BirthInput` dataclass.
- `src/astrology_app/session_store.py`
  - in-memory only storage.
- `src/astrology_app/chart_engine.py`
  - adapter boundary for open-source engine (`pyhora` / `jhora` import candidates).
  - currently returns normalized placeholder chart package.
- `pyproject.toml`
  - package configuration with `src` layout.
- `requirements.txt`
  - placeholder notes pending final dependency list.

### What Is Done vs Not Done

- Done:
  - architecture direction locked (desktop -> web, reusable core)
  - session-only data policy decided
  - initial runnable app structure added
- Not done:
  - Python environment setup and first local run
  - installation and verification of selected open-source astrology package
  - real chart mapping (D1/D9/dasha/nakshatra) in adapter
  - question-routing + AI interpretation stage

### Immediate Next Steps (After Python Install Completes)

1. Verify Python:
   - `python --version` (or `py --version`)
2. Create environment:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
3. Install project package:
   - `python -m pip install --upgrade pip`
   - `python -m pip install -e .`
4. Run current scaffold:
   - `python -m astrology_app.main`
5. Install and validate open-source chart engine dependency (PyHora/JHora path to be finalized).
6. Replace placeholder output in `chart_engine.py` with real library calls and normalized mapping.

### Definition of Next Milestone

Milestone M3a is complete when:

- user can input DOB/time/place/timezone
- app successfully generates real D1 + D9 + dasha basics via open-source library
- output is normalized into internal chart-package format
- data remains in-memory only for current session

