# Decisions

A log of important technical choices and the reasoning behind each one.

---

## Architecture

### Medallion architecture (Bronze / Silver / Gold)

**Decision**: Organise data into three layers — raw ingestion (Bronze), cleaned staging (Silver), and analytics-ready marts (Gold).

**Why**: Separates concerns cleanly. The Bronze layer is an exact replica of what came from the API; it can always be re-transformed without re-fetching. Silver handles cleaning and type casting. Gold expresses business logic (weekly aggregates, PR detection, training load). Each layer can be debugged independently.

---

### DuckDB as the data warehouse

**Decision**: Use DuckDB (embedded, file-based) instead of PostgreSQL or SQLite.

**Why**: No server to run, no port to expose. The single `.duckdb` file lives in `data/duckdb/` and travels with the project. DuckDB handles analytical queries (window functions, aggregations over millions of rows) faster than SQLite, and its Python API returns Pandas DataFrames natively. The trade-off is that concurrent writers are not supported — acceptable for a single-user local project.

---

### dbt for transformations

**Decision**: Use dbt-core + dbt-duckdb rather than writing transformation logic in Python/Pandas.

**Why**: SQL transformations are version-controlled, testable (`dbt test`), and self-documenting. dbt's DAG ensures models run in the right order, and `ref()` makes dependencies explicit. Rerunning `dbt run` is idempotent. The alternative — Pandas pipelines — would mix transformation and application logic and make the data lineage opaque.

---

### No JOIN operations in mart models

**Decision**: Mart models do not join to other models. Data is flattened at the staging layer.

**Why**: Joins in mart models can silently explode row counts (fan-out) when the cardinality is unexpected. Keeping each mart self-contained makes them easier to query directly and to reason about. Where cross-domain context is needed (e.g., training load + health recovery on the same date), the Streamlit layer or the LLM prompt merges the already-aggregated results.

---

## Ingestion

### Session file persistence for Garmin auth

**Decision**: Serialize the Garmin Connect session to `data/garmin_session.json` and reuse it on the next run, falling back to a fresh login only if the session is expired or missing.

**Why**: Garmin rate-limits repeated logins. Reusing a valid session avoids unnecessary auth calls and speeds up scheduled runs. The session file is git-ignored.

---

### Two-phase upsert for weather data

**Decision**: Weather data is written in a separate pass: Phase 1 inserts new activities; Phase 2 back-fills `NULL` weather columns on existing rows.

**Why**: The Garmin weather endpoint is a secondary call per activity. If it fails or is skipped, the activity row is still inserted cleanly. The back-fill allows retrying weather enrichment later without re-ingesting activities. This avoids losing an activity record just because a non-critical enrichment step failed.

---

### Race detection priority: `event_type` first, distance heuristics second

**Decision**: An activity is tagged as a race if `event_type = 'race'` in the Garmin payload. Distance-based thresholds (e.g., 5K: 4.8–5.2 km) are used only as a fallback when `event_type` is null.

**Why**: Distance alone produced false positives — a 21 km long run would be misclassified as a half-marathon race. Garmin explicitly sets `event_type = 'race'` when the user registers an activity as a race in the app, making it the authoritative signal.

---

## AI Coach

### Deterministic alerts separate from LLM

**Decision**: ACWR, HRV drop, sleep deficit, and recovery score thresholds are computed locally in `calculate_alerts()` and displayed unconditionally. The Claude API is called separately for nuanced interpretation.

**Why**: Rule-based signals are cheap, instant, and predictable. Delegating binary threshold checks to an LLM adds latency and cost without improving accuracy. The LLM handles what it is actually good at: contextualizing patterns, suggesting training adjustments, and explaining trade-offs.

---

### Aggregated context only — no raw rows sent to Claude

**Decision**: The prompt sent to Claude contains only pre-aggregated metrics (4-week averages, 7-day averages, computed scores). Raw activity or health rows are never included.

**Why**: Token efficiency. A typical user has hundreds of activities; sending raw rows would consume most of the context window and degrade response quality. Aggregated metrics surface the patterns the coach needs to reason about, and the model produces equivalent or better output from them.

---

### `claude-opus-4-6` for coaching analysis

**Decision**: The coaching engine uses `claude-opus-4-6`, the highest-capability Claude model, rather than a faster/cheaper variant.

**Why**: Coaching advice requires nuanced reasoning across multiple data domains (training load, recovery, race timeline, weather). The quality difference between Opus and Haiku/Sonnet is material for this use case. Cost per analysis is acceptable for an on-demand, user-triggered action.

---

## Dashboard

### Streamlit for the UI

**Decision**: Use Streamlit rather than a custom web framework (Flask/FastAPI + React) or a BI tool (Grafana, Metabase).

**Why**: Streamlit lets you ship an interactive, multi-page dashboard in pure Python with no HTML/CSS/JS. For a personal analytics tool where iteration speed matters more than pixel-perfect design, it is the right trade-off. The multi-page layout (`pages/` directory) keeps each domain (training, health, races, AI coach) isolated.

---

### `st.session_state` for DataFrame caching instead of `@st.cache_data`

**Decision**: DataFrames are stored in `st.session_state` rather than decorated with `@st.cache_data`.

**Why**: `@st.cache_data` serializes data through Arrow. DuckDB 1.4.x returns objects that trigger a `field id: 100` Arrow serialization error. `st.session_state` stores objects in-process with no serialization step. The trade-off is that state is not shared across browser tabs, which is acceptable for a single-user tool. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for details.

---

### Date normalization on every database query

**Decision**: Every function that returns a DataFrame from DuckDB calls `_normalize_dates(df)`, which casts known date columns to `datetime.date`.

**Why**: DuckDB `DATE` columns can arrive as Python `datetime.date`, `str`, or `pandas.Timestamp` depending on how the query was assembled and which DuckDB version is running. Streamlit's `st.date_input` returns `datetime.date`. Mixing these types causes silent `TypeError` in comparisons and filters. Normalizing at the data layer prevents the issue from leaking into UI logic.

---

## Deployment

### Bring-your-own-key for the AI Coach on Streamlit Cloud

**Decision**: The Anthropic API key is never stored server-side. Users enter their own key at runtime via a `st.text_input(type="password")` field. The key lives only in `st.session_state` for the duration of the browser session.

**Why**: Storing a server-side API key on Streamlit Cloud would expose it to anyone with the app URL, with no rate limiting. Asking users to bring their own key eliminates financial risk entirely, keeps the demo freely accessible for everyone else, and is a stronger portfolio signal — it shows awareness of security trade-offs in multi-user deployments.

---

### Three-tier requirements file structure

**Decision**: Split Python dependencies across three files: `requirements.txt` (Streamlit Cloud runtime), `requirements-pipeline.txt` (ingestion, dbt, Airflow), and `requirements-dev.txt` (everything + dev tooling).

**Why**: Streamlit Cloud reads `requirements.txt` from the repo root and installs it verbatim. The previous monolithic file included Airflow, dbt, garminconnect, and great-expectations — packages that either conflict with the Streamlit Cloud environment or are simply unnecessary there. Splitting by concern keeps each environment lean and documents intent clearly: you know what is needed where just by reading the filename.

---

### Lazy instantiation of `GarminConfig` and `StravaConfig`

**Decision**: `GarminConfig` and `StravaConfig` are no longer instantiated at module level. They are created on first access via `get_garmin_config()` and `get_strava_config()` getter functions. `DatabaseConfig` and `AppConfig` (which have no required fields) remain eagerly instantiated.

**Why**: Pydantic `BaseSettings` validates required fields immediately on instantiation. `GarminConfig` requires `GARMIN_EMAIL` and `GARMIN_PASSWORD`. Any module that imports `from ingestion.config import database_config` would previously trigger `GarminConfig()` as a side effect, crashing with a `ValidationError` in any environment without Garmin credentials — including Streamlit Cloud, CI pipelines, and read-only dashboard deployments. Lazy instantiation defers the validation to the moment the credentials are actually needed.

---

## Tooling

### Two separate virtual environments (`venv` and `venv_streamlit`)

**Decision**: The Streamlit application has its own virtual environment, separate from the ingestion/dbt environment.

**Why**: Streamlit's dependency tree conflicts with some ingestion packages (particularly around protobuf and grpc versions pulled in by garminconnect and airflow). Isolating them prevents resolution failures and makes each environment smaller and faster to install.

---

### Pydantic for configuration management

**Decision**: All configuration is modelled with `pydantic-settings` `BaseSettings` classes, not raw `os.getenv()` calls scattered through the code.

**Why**: Pydantic validates types at startup — a missing `ANTHROPIC_API_KEY` raises a clear error before any API call is attempted, rather than failing silently at runtime. Configuration objects are also importable and testable.
