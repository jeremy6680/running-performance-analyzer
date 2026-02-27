# Running Performance Analyzer - Next Steps

## What We've Accomplished So Far

### Phase 1: Project Setup & Data Ingestion (COMPLETE)

#### Infrastructure

- [x] Project structure with proper folder organisation
- [x] Git repository initialised and configured
- [x] Python virtual environment (Python 3.11.9 via pyenv)
- [x] All core dependencies installed
- [x] Environment configuration with `.env` file
- [x] Docker Compose configuration for Airflow deployment

#### Data Ingestion Pipeline

- [x] **Garmin Connect API Integration**
  - `ingestion/garmin_connector.py` -- full-featured API connector
  - Session management (saves/loads sessions to avoid re-login)
  - Fetches activities (distance, pace, HR, elevation, `event_type` for race detection)
  - Fetches daily health (steps, sleep, HRV, stress, body battery)
  - Fetches calendar race events (upcoming races)
  - Error handling and logging with loguru

- [x] **DuckDB Database Layer (Bronze)**
  - `ingestion/duckdb_manager.py` -- database manager
  - Bronze layer tables: `raw_garmin_activities`, `raw_garmin_daily_health`, `raw_garmin_calendar_events`
  - Upsert logic (insert new, skip duplicates)
  - Two-phase weather back-fill: activities inserted first, weather enriched separately so a failed weather call never loses an activity row

- [x] **Ingestion Scripts**
  - `ingestion/ingest_garmin.py` -- main ingestion script with CLI (`--days`, `--initial`, `--mode`)
  - `ingestion/config.py` -- Pydantic configuration management
  - `ingestion/utils.py` -- utility functions
  - `scripts/query_data.py` -- data exploration script

---

### Phase 2: Data Transformation with dbt (COMPLETE)

#### dbt Project Setup

- [x] dbt project initialised with DuckDB adapter
- [x] `dbt_project.yml` and `profiles.yml` configured
- [x] Sources defined in `_sources.yml`

#### Silver Layer (Staging Models)

- [x] `stg_garmin_activities.sql` -- 482-line model with:
  - Pace zones, HR zones, effort levels, training load (TRIMP)
  - Race detection: `event_type = 'race'` checked first; distance-band fallback only if null
  - Race distance categorisation (5K/10K/Half/Marathon/Ultra) with GPS-drift tolerances
  - Terrain classification
- [x] `stg_garmin_health.sql` -- sleep, HRV, stress, body battery cleaning

#### Intermediate Layer

- [x] `int_unified_activities.sql` -- merges sources, standardises activity types

#### Gold Layer (Marts)

- [x] `mart_activity_performance.sql` -- per-activity analytics
- [x] `mart_training_summary.sql` -- weekly aggregations with rolling averages
  - Columns: `rolling_4wk_avg_distance_km`, `rolling_4wk_avg_training_load`
  - HR zone distribution: `pct_zone1_easy` -> `pct_zone5_max`
- [x] `mart_health_trends.sql` -- daily health with 7/28-day rolling averages, recovery score, training readiness
- [x] `mart_race_performance.sql` -- race history, PR tracking, pace analysis, readiness context

#### Data Quality

- [x] Schema tests across all layers (not_null, unique, accepted_values, relationships)
- [x] 171 tests, 97-100% pass rate
- [x] Race detection bug fixed (event_type-first, removed distance-based false positives)

#### Critical schema facts (do not guess these column names)

```
mart_training_summary:    week_start_date, total_distance_km, total_training_load,
                          avg_pace_min_per_km (NOT average_pace_min_per_km),
                          pct_zone1_easy, pct_zone2_moderate, pct_zone3_tempo,
                          pct_zone4_threshold, pct_zone5_max,
                          rolling_4wk_avg_distance_km, rolling_4wk_avg_training_load

mart_health_trends:       date (NOT health_date), total_sleep_hours, hrv_numeric,
                          resting_heart_rate, average_stress_level,
                          recovery_score, training_readiness

mart_race_performance:    race_date, race_distance_category,
                          pace_min_per_km (NOT average_pace_min_per_km),
                          finish_time_formatted (H:MM:SS), is_personal_record,
                          performance_rating, race_readiness_score
```

---

### Phase 3: Streamlit Dashboard (COMPLETE)

#### Infrastructure

- [x] Separate virtual environment `venv_streamlit` with Streamlit 1.45.0
  - Downgraded from 1.54.0 to fix DuckDB 1.4.4 Arrow serialisation error
  - All pages use `st.session_state` instead of `@st.cache_data`
  - Date columns normalised to `datetime.date` via `_normalize_dates(df)` on every query
- [x] Modular architecture:
  - `utils/database.py` -- data loading functions (fetchall() pattern, no Arrow)
  - `utils/formatting.py` -- pace, time, distance formatters
  - `utils/constants.py` -- Garmin-inspired colour palette, HR zones, activity types
  - `components/metrics.py` -- reusable metric cards
  - `components/charts.py` -- reusable Plotly chart components

#### Pages Built

- [x] `0_Dashboard.py` -- home page (light theme, gradient hero, all-time stats, recovery badge)
- [x] `pages/1_Training_Analysis.py` -- training load, pace, HR zones, scatter
- [x] `pages/2_Race_Performance.py` -- race history, PRs, pace progression
- [x] `pages/3_Health.py` -- sleep, HRV, stress, Body Battery, recovery score

#### Known data limitation

Health data only goes back to ~February 2026. To sync more history:

```bash
python -m ingestion.ingest_garmin --days 365
cd dbt_project && dbt run
```

---

### Phase 4: AI Coach Integration (COMPLETE)

#### Architecture decisions

- **Interaction mode**: One-shot analysis (Generate button -> full report)
- **Context window**: Last 4 weeks training + last 7 days health + current weather (Open-Meteo)
- **Alerts**: Deterministic thresholds computed locally (no API cost), shown above LLM response
- **Language**: English throughout
- **Pedagogy**: Expander showing exact context sent to Claude (portfolio-friendly)
- **Jargon rule**: All technical terms explained inline on first use

#### Files created

- [x] `ai_engine/__init__.py`
- [x] `ai_engine/llm_analyzer.py` -- core engine with three responsibilities:
  - `build_coaching_context()` -- aggregates 3 DataFrames into a typed dataclass
  - `calculate_alerts()` -- 5 deterministic checks (ACWR, HRV trend, sleep, recovery, goal gap)
  - `get_coaching_analysis()` -- calls Claude API, returns `(markdown, model_name)` tuple
- [x] `ai_engine/prompts/coach_analysis.txt` -- system prompt enforcing 4-section structure + jargon rule
- [x] `streamlit_app/pages/4_AI_Coach.py` -- Streamlit page (inputs -> alerts -> expander -> LLM response)

#### Enhancements added after initial implementation

- [x] **Weather integration** -- Open-Meteo API added to coaching context (temperature, precipitation,
      wind) so Claude can factor environmental conditions into recommendations.
- [x] **Saved analyses** -- AI coaching reports are persisted across sessions for review.

#### Key technical learnings

- `database.py` uses `fetchall()` which returns all columns as Python `object` dtype.
  `.mean()` on object-dtype columns concatenates instead of averaging.
  Fix: `_col_mean()` helper uses `pd.to_numeric(..., errors="coerce")` before `.mean()`.
- `load_dotenv()` must be called at module import time, not inside the function,
  to ensure `ANTHROPIC_API_KEY` is in `os.environ` before the Anthropic client is instantiated.
- Use `os.getenv()` (returns `None`) not `os.environ[]` (raises `KeyError`) for optional env vars.
- `get_coaching_analysis()` returns a `tuple[str, str]` (response, model_name) so the
  Streamlit footer can display exactly which model version generated the analysis.

#### ACWR thresholds used for alerts

- < 0.8: under-training (no alert -- positive signal noted in LLM context)
- 0.8-1.3: optimal zone (no alert)
- > 1.3: caution
- > 1.5: danger (high injury risk)

---

### Phase 5: Airflow Orchestration (COMPLETE)

#### Architecture decisions

- **Two DAGs**: `garmin_ingestion` and `dbt_transformation` are separate DAGs linked by `TriggerDagRunOperator`
  so that dbt can also be triggered independently (e.g. to rebuild transformations without re-fetching data)
- **dbt inside Docker**: dbt is installed in the Airflow container via `airflow/airflow-requirements.txt`
  and called as a subprocess with explicit `--profiles-dir` flag
- **Module mounting**: `ingestion/` and `ai_engine/` folders are mounted at `/opt/airflow/modules/`
  and added to `sys.path` at task runtime (not at DAG parse time, to avoid import errors)
- **Credential injection**: env vars from docker-compose override `.env` values inside the container;
  `GARMIN_SESSION_FILE` is remapped to `/opt/airflow/data/garmin_session.json`

#### Files created

- [x] `airflow/dags/garmin_ingestion_dag.py`
  - Schedule: daily at 6 AM Europe/Paris (`0 6 * * *`)
  - Task 1: `fetch_garmin_data` -- runs `ingest_garmin_data(days=7)` via `PythonOperator`
  - Task 2: `trigger_dbt_transformations` -- kicks off `dbt_transformation` DAG on success
  - Retries once after 5 minutes on failure
- [x] `airflow/dags/dbt_transformation_dag.py`
  - Schedule: `None` (triggered only, not scheduled)
  - Task 1: `dbt_run` -- `dbt run` via subprocess with `_run_dbt_command()` helper
  - Task 2: `dbt_test` -- `dbt test` via subprocess; runs only if `dbt_run` succeeds
  - dbt executable located dynamically (`/home/airflow/.local/bin/dbt` -> PATH fallback)
- [x] `airflow/airflow-requirements.txt` -- includes `dbt-core`, `dbt-duckdb`

#### Key technical learnings

- Import ingestion modules inside task functions (not at DAG parse time): Airflow parses all DAGs
  on startup; if `from ingestion.ingest_garmin import ...` is at module level, a missing dependency
  crashes the entire scheduler. Importing inside the callable defers the import to task runtime.
- `TriggerDagRunOperator` with `reset_dag_run=True` allows the dbt DAG to be re-triggered on the
  same day without raising a `DagRunAlreadyExists` error.
- `wait_for_completion=False` on the trigger operator means ingestion completes without waiting for
  dbt -- the two DAGs run concurrently in Airflow's task graph, which is the intended behaviour.
- `catchup=False` on both DAGs prevents Airflow from scheduling and running all missed runs
  since `start_date` when first deployed.

---

## Next Steps -- Roadmap

### Phase 6: Advanced Features (Future)

- [ ] Strava integration (alternative/complementary data source)
- [ ] ML injury risk prediction model
- [ ] RAG for running knowledge base (LlamaIndex / LangGraph)
- [ ] Streamlit Cloud deployment (free tier -- public portfolio link)
- [ ] GitHub Actions CI/CD (dbt test on push, linting)
- [ ] Email/Slack alert on Airflow pipeline failure

---

## Current Project Structure

```
running-performance-analyzer/
├── .env                              Configured
├── .gitignore                        Configured
├── docker-compose.yml                Configured (Airflow live)
├── requirements.txt                  Installed
├── CONVENTIONS.md                    Naming rules, SQL patterns, patterns to avoid
├── DECISIONS.md                      Technical decision log with rationale
├── KNOWN_ISSUES.md                   Bug workarounds and gotchas
│
├── ingestion/                        COMPLETE
│   ├── config.py
│   ├── utils.py
│   ├── garmin_connector.py
│   ├── duckdb_manager.py
│   └── ingest_garmin.py
│
├── dbt_project/                      COMPLETE
│   └── models/
│       ├── staging/                  stg_garmin_activities, stg_garmin_health
│       ├── intermediate/             int_unified_activities
│       └── marts/                    4 gold layer marts (171 tests)
│
├── streamlit_app/                    COMPLETE
│   ├── 0_Dashboard.py
│   └── pages/
│       ├── 1_Training_Analysis.py
│       ├── 2_Race_Performance.py
│       ├── 3_Health.py
│       └── 4_AI_Coach.py
│
├── ai_engine/                        COMPLETE
│   ├── llm_analyzer.py
│   └── prompts/coach_analysis.txt
│
├── airflow/                          COMPLETE (Phase 5)
│   └── dags/
│       ├── garmin_ingestion_dag.py   Daily at 6 AM, triggers dbt on success
│       └── dbt_transformation_dag.py dbt run + dbt test, triggered only
│
└── data/duckdb/running_analytics.duckdb
```

---

## How to Run

```bash
# Activate main environment
source venv/bin/activate

# Sync latest Garmin data
python -m ingestion.ingest_garmin --days 7

# Rebuild dbt gold layer
cd dbt_project && dbt run && dbt test && cd ..

# Launch dashboard
source venv_streamlit/bin/activate
streamlit run "streamlit_app/0_Dashboard.py"
# -> http://localhost:8501

# Start Airflow (for automated daily runs)
docker-compose up -d
# -> http://localhost:8080
```

---

## Success Criteria for Job Applications

Your project now demonstrates:

- **Analytics Engineering**: dbt medallion architecture, data modelling, 171 data quality tests
- **Data Engineering**: Garmin API integration, DuckDB pipeline, incremental loads
- **Data Analytics**: SQL aggregations, rolling averages, custom recovery scoring
- **Data Visualisation**: Streamlit + Plotly multi-page dashboard
- **AI Engineering**: Claude API integration, prompt engineering, context compression
- **Orchestration**: Airflow DAGs, scheduling, DAG chaining

### Portfolio talking points

- "Built end-to-end data pipeline: Garmin Connect API -> DuckDB medallion architecture -> dbt transformations -> Streamlit dashboard"
- "Implemented race detection using Garmin's event_type field -- fixed false positives that distance-based heuristics produced"
- "Calculated custom recovery score (0-100) from sleep, HRV, resting HR, stress and Body Battery using dbt SQL"
- "Built 5-page interactive analytics dashboard with Plotly charts and Garmin-inspired design"
- "Resolved Streamlit/DuckDB Arrow serialisation incompatibility by switching to session_state caching"
- "Integrated Claude API for AI coaching: token-efficient context compression, deterministic alert layer separate from LLM, structured 4-section prompt with jargon policy"
- "Added weather context (Open-Meteo API) to AI coaching so Claude factors environmental conditions into training recommendations"
- "Built Airflow DAG pipeline: garmin_ingestion triggers dbt_transformation on success, both with retry logic and detailed task logging"

---
