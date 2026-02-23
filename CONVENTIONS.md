# Conventions

Naming rules, patterns to follow or avoid, and standards adopted for this project.

---

## File & Directory Naming

| Type | Convention | Example |
|------|-----------|---------|
| Python modules | `snake_case.py` | `garmin_connector.py`, `duckdb_manager.py` |
| Python classes | `PascalCase` | `GarminConnector`, `DuckDBManager`, `CoachingContext` |
| Streamlit pages | `N_emoji_Title.py` | `1_📈_Training_Analysis.py` |
| Markdown docs | `UPPER_SNAKE_CASE.md` | `NEXT_STEPS.md`, `PROJECT_STRUCTURE.md` |
| Config files | `lowercase.yml` | `profiles.yml`, `dbt_project.yml` |
| Notebooks | `NN_description.ipynb` | `01_data_exploration.ipynb` |

---

## Python Naming

### Variables
- DataFrames always use the `_df` suffix: `activities_df`, `health_df`, `race_df`
- Booleans use the `is_` or `has_` prefix: `is_race`, `has_weather`, `_authenticated`
- Single records use the singular: `activity`, `event` (not `activities_item`)
- Raw API payloads keep short names: `raw_activities`, `weather_data`

### Functions & Methods
- Public utilities: verb + noun, descriptive (`calculate_pace`, `meters_to_kilometers`, `safe_divide`)
- Private methods: prefixed with `_` (`_ensure_authenticated`, `_fetch_weather_for_activity`, `_transform_activities`)
- Data loaders (Streamlit): `load_*_data()` (`load_training_data`, `load_health_data`)
- Database helpers: verb + entity (`insert_activities`, `save_coaching_analysis`, `delete_analysis`)

### Configuration Objects
- Named after their domain: `garmin_config`, `database_config`, `app_config`
- Instantiated at module level, not inside functions

---

## Database Naming

### Table Prefixes by Layer

| Layer | Prefix | Example |
|-------|--------|---------|
| Bronze (raw) | `raw_garmin_*` | `raw_garmin_activities` |
| Silver (staging) | `stg_garmin_*` | `stg_garmin_activities` |
| Intermediate | `int_*` | `int_unified_activities` |
| Gold (marts) | `mart_*` | `mart_training_summary` |

### Column Naming Rules
- Units always appended: `distance_km`, `duration_minutes`, `elevation_gain_m`, `wind_speed_ms`
- Percentage columns: `pct_zone1_easy`, `sleep_deep_pct`, `weather_humidity_pct`
- Boolean flags: `is_race`, `is_personal_record`, `subscribed`
- Audit columns: `inserted_at`, `updated_at` (TIMESTAMP)
- Primary keys: singular entity name (`activity_id`, `event_uuid`), or date (`date`, `week_start_date`, `race_date`)

### Critical Column Names (easy to get wrong)
- `avg_pace_min_per_km` — in `mart_training_summary` (NOT `average_pace_min_per_km`)
- `pace_min_per_km` — in `mart_race_performance` (NOT `average_pace_min_per_km`)
- `date` — primary key in `mart_health_trends` (NOT `health_date`)
- `week_start_date` — primary key in `mart_training_summary` (DATE, always a Monday)
- `hrv_numeric` — extracted numeric HRV value in `mart_health_trends` (NOT `hrv_avg`)

---

## dbt Model Conventions

- All models use CTEs, never nested subqueries
- CTE pattern: `source_data → cleaned → final`
- Every column includes a comment with its unit and description
- Mart models materialize as `TABLE` (not `VIEW`), for query performance
- Staging models materialize as `VIEW`
- Window functions always specify the frame explicitly: `ROWS BETWEEN N PRECEDING AND CURRENT ROW`
- Division always wrapped in `NULLIF(..., 0)` to avoid zero-division errors

---

## Environment Variables

| Category | Pattern | Example |
|----------|---------|---------|
| API credentials | `SERVICE_FIELD` | `GARMIN_EMAIL`, `ANTHROPIC_API_KEY` |
| Database paths | `SERVICE_PATH` | `DUCKDB_PATH` |
| Feature flags | `ENABLE_*` | `ENABLE_AUTO_BACKUP`, `ENABLE_RAG` |
| Sync settings | `*_DAYS` | `INITIAL_SYNC_DAYS`, `DAILY_SYNC_DAYS` |
| Runner profile | `RUNNER_*` | `RUNNER_AGE`, `RUNNER_MAX_HR` |

---

## Commit Messages

Format: `type: short description`

Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`

Always use present tense and describe what changed and why at a high level. Example:
```
feat: Implement date normalization for database queries and enhance context display in analyses
```

---

## Patterns to Follow

- **Explicit column lists in SQL inserts** — never `INSERT INTO ... SELECT *`. Explicit lists survive schema evolution.
- **CTE-based staging** — break transformations into named, sequential CTEs for readability and debugging.
- **Weighted pace averages** — `SUM(pace * distance) / NULLIF(SUM(distance), 0)` so longer runs carry more weight.
- **Race detection priority** — check `event_type = 'race'` first; fall back to distance heuristics only if null.
- **Aggregated context for LLM** — send computed metrics (4-week avg, 7-day avg) to Claude, not raw rows.
- **Deterministic alerts before LLM** — ACWR, HRV, sleep thresholds are computed locally and shown unconditionally.
- **Session state for Streamlit caching** — store DataFrames in `st.session_state` to avoid Arrow serialization issues.
- **Graceful degradation on non-critical failures** — weather fetch failures return `None` and let ingestion continue.
- **Date normalization on load** — call `_normalize_dates(df)` after every DuckDB query to ensure `datetime.date` types throughout.

## Patterns to Avoid

- `@st.cache_data` for DataFrames — causes Arrow serialization errors with DuckDB 1.4.x. Use `st.session_state` instead.
- `SELECT *` in mart models — leads to column name ambiguity and breaks on schema changes.
- JOIN operations in mart models — flatten data at the staging level; aggregate separately and reshape rather than joining marts.
- Implicit type casting — always use explicit `CAST(col AS TYPE)` in SQL.
- Detecting races by distance alone — produces false positives on long training runs; always check `event_type` first.
- Sending raw activity rows to the LLM — excessive token usage and no better output; pre-aggregate before building the prompt.
