# 🏃 Running Performance Analyzer - Next Steps

## ✅ What We've Accomplished So Far

### Phase 1: Project Setup & Data Ingestion (COMPLETED ✓)

#### Infrastructure

- [x] Project structure with proper folder organisation
- [x] Git repository initialised and configured
- [x] Python virtual environment (Python 3.11.9 via pyenv)
- [x] All core dependencies installed
- [x] Environment configuration with `.env` file
- [x] Docker Compose configuration for future Airflow deployment

#### Data Ingestion Pipeline

- [x] **Garmin Connect API Integration**
  - `ingestion/garmin_connector.py` — full-featured API connector
  - Session management (saves/loads sessions to avoid re-login)
  - Fetches activities (distance, pace, HR, elevation, `event_type` for race detection)
  - Fetches daily health (steps, sleep, HRV, stress, body battery)
  - Error handling and logging with loguru

- [x] **DuckDB Database Layer (Bronze)**
  - `ingestion/duckdb_manager.py` — database manager
  - Bronze layer tables: `raw_garmin_activities` (30 cols), `raw_garmin_daily_health` (24 cols)
  - Upsert logic (insert new, skip duplicates)
  - Migration: `migrate_add_event_type()` — added `event_type` column for race detection

- [x] **Ingestion Scripts**
  - `ingestion/ingest_garmin.py` — main ingestion script with CLI (`--days`, `--initial`, `--mode`)
  - `ingestion/config.py` — Pydantic configuration management
  - `ingestion/utils.py` — utility functions
  - `scripts/query_data.py` — data exploration script

---

### Phase 2: Data Transformation with dbt (COMPLETED ✓)

#### dbt Project Setup

- [x] dbt project initialised with DuckDB adapter
- [x] `dbt_project.yml` and `profiles.yml` configured
- [x] Sources defined in `_sources.yml`

#### Silver Layer (Staging Models)

- [x] `stg_garmin_activities.sql` — 482-line model with:
  - Pace zones, HR zones, effort levels, training load (TRIMP)
  - Race detection (event_type-first strategy — avoids false positives on distance)
  - Race distance categorisation (5K/10K/Half/Marathon/Ultra) with GPS-drift tolerances
  - Terrain classification
- [x] `stg_garmin_health.sql` — sleep, HRV, stress, body battery cleaning

#### Intermediate Layer

- [x] `int_unified_activities.sql` — merges sources, standardises activity types

#### Gold Layer (Marts)

- [x] `mart_activity_performance.sql` — per-activity analytics
- [x] `mart_training_summary.sql` — weekly aggregations with rolling averages
  - Columns: `rolling_4wk_avg_distance_km`, `rolling_4wk_avg_training_load`
  - HR zone distribution: `pct_zone1_easy` → `pct_zone5_max`
- [x] `mart_health_trends.sql` — daily health with 7/28-day rolling averages, recovery score, training readiness
- [x] `mart_race_performance.sql` — race history, PR tracking, pace analysis, readiness context

#### Data Quality

- [x] Schema tests across all layers (not_null, unique, accepted_values, relationships)
- [x] High test pass rate (46/47 on initial run)
- [x] Race detection bug fixed (event_type-first, removed distance-based false positives)

#### Critical schema facts (for reference in future sessions)

```
mart_training_summary:    week_start_date, total_distance_km, total_training_load,
                          avg_pace_min_per_km (NOT average_pace_min_per_km),
                          pct_zone1_easy, pct_zone2_moderate, pct_zone3_tempo,
                          pct_zone4_threshold, pct_zone5_max,
                          rolling_4wk_avg_distance_km, rolling_4wk_avg_training_load

mart_health_trends:       date (not health_date), total_sleep_hours, hrv_numeric,
                          resting_heart_rate, average_stress_level,
                          recovery_score, training_readiness

mart_race_performance:    race_date, race_distance_category,
                          pace_min_per_km (NOT average_pace_min_per_km),
                          finish_time_formatted (H:MM:SS), is_personal_record,
                          performance_rating, race_readiness_score
```

---

### Phase 3: Streamlit Dashboard (COMPLETED ✓)

#### Infrastructure

- [x] Separate virtual environment `venv_streamlit` with Streamlit 1.45.0
  - Downgraded from 1.54.0 to fix DuckDB 1.4.4 Arrow serialisation error
  - All pages use `st.session_state` instead of `@st.cache_data`
- [x] Modular architecture:
  - `utils/database.py` — data loading functions (fetchall() pattern, no Arrow)
  - `utils/formatting.py` — pace, time, distance formatters
  - `utils/constants.py` — Garmin-inspired colour palette, HR zones, activity types
  - `components/metrics.py` — reusable metric cards
  - `components/charts.py` — reusable Plotly chart components

#### Pages Built

- [x] `0_📊_Dashboard.py` — home page (light theme, gradient hero, all-time stats, recovery badge)
- [x] `pages/1_📈_Training_Analysis.py` — training load, pace, HR zones, scatter
- [x] `pages/2_🏃_Race_Performance.py` — race history, PRs, pace progression
- [x] `pages/3_❤️_Health.py` — sleep, HRV, stress, Body Battery, recovery score

#### Known data limitation

Health data only goes back to Feb 8, 2026. To sync more history:

```bash
python -m ingestion.ingest_garmin --days 90
cd dbt_project && dbt run
```

---

### Phase 4: AI Coach Integration (COMPLETED ✓)

#### Architecture decisions

- **Interaction mode**: One-shot analysis (Generate button → full report)
- **Context window**: Last 4 weeks training + last 7 days health
- **Alerts**: Deterministic thresholds computed locally (no API cost), shown above LLM response
- **Language**: English throughout
- **Pedagogy**: Expander showing exact context sent to Claude (portfolio-friendly)
- **Jargon rule**: All technical terms must be explained inline on first use

#### Files created

- [x] `ai_engine/__init__.py`
- [x] `ai_engine/llm_analyzer.py` — core engine with three responsibilities:
  - `build_coaching_context()` — aggregates 3 DataFrames into a typed dataclass
  - `calculate_alerts()` — 5 deterministic checks (ACWR, HRV trend, sleep, recovery, goal gap)
  - `get_coaching_analysis()` — calls Claude API, returns `(markdown, model_name)` tuple
- [x] `ai_engine/prompts/coach_analysis.txt` — system prompt enforcing 4-section structure + jargon rule
- [x] `streamlit_app/pages/4_🤖_AI_Coach.py` — Streamlit page (inputs → alerts → expander → LLM response)

#### Key technical learnings

- `database.py` uses `fetchall()` which returns all columns as Python `object` dtype.
  `.mean()` on object-dtype string columns concatenates instead of averaging.
  Fix: `_col_mean()` helper uses `pd.to_numeric(..., errors="coerce")` before `.mean()`.
- `load_dotenv()` must be called at module import time, not inside the function,
  to ensure `ANTHROPIC_API_KEY` is in `os.environ` before the Anthropic client is instantiated.
- Use `os.getenv()` (returns `None`) not `os.environ[]` (raises `KeyError`) for optional env vars.
- `get_coaching_analysis()` returns a `tuple[str, str]` (response, model_name) so the
  Streamlit footer can display exactly which model version generated the analysis.

#### Real column names (fixed during Phase 4)

- `mart_training_summary.avg_pace_min_per_km` (not `average_pace_min_per_km`)
- `mart_race_performance.pace_min_per_km` (not `average_pace_min_per_km`)

#### ACWR thresholds used for alerts

- < 0.8: under-training (no alert — positive signal noted in LLM context)
- 0.8–1.3: optimal zone (no alert)
- > 1.3: caution 🟡
- > 1.5: danger 🔴 (high injury risk)

---

## 🎯 Next Steps — Roadmap

### Phase 5: Orchestration with Airflow (NEXT 🎯)

#### Objective

Automate daily data sync and dbt transformations so the dashboard always shows fresh data
without manual intervention.

#### Tasks

- [ ] Start Airflow: `docker-compose up -d`
- [ ] `airflow/dags/garmin_ingestion.py` — daily at 6 AM, fetch last 7 days → load to bronze
- [ ] `airflow/dags/dbt_orchestration.py` — `dbt run` + `dbt test` after ingestion succeeds
- [ ] Email/Slack alert on pipeline failure

---

### Phase 6: Advanced Features (Future)

- [ ] Strava integration (alternative/complementary data source)
- [ ] RAG for running knowledge base (LlamaIndex / LangGraph)
- [ ] ML injury risk prediction model
- [ ] Streamlit Cloud deployment (free tier — public portfolio link)
- [ ] GitHub Actions CI/CD (dbt test on push)

---

## 📁 Current Project Structure

```
running-performance-analyzer/
├── .env                              ✅ Configured
├── .gitignore                        ✅ Configured
├── docker-compose.yml                ✅ Configured (Airflow ready)
├── requirements.txt                  ✅ Installed
│
├── ingestion/                        ✅ COMPLETE
│   ├── config.py
│   ├── utils.py
│   ├── garmin_connector.py
│   ├── duckdb_manager.py
│   ├── ingest_garmin.py
│   └── test_connector.py
│
├── dbt_project/                      ✅ COMPLETE
│   ├── models/
│   │   ├── staging/                  ✅ stg_garmin_activities, stg_garmin_health
│   │   ├── intermediate/             ✅ int_unified_activities
│   │   └── marts/                    ✅ 4 gold layer marts
│   └── tests/
│
├── streamlit_app/                    ✅ COMPLETE
│   ├── 0_📊_Dashboard.py             ✅ Home page
│   ├── pages/
│   │   ├── 1_📈_Training_Analysis.py ✅
│   │   ├── 2_🏃_Race_Performance.py  ✅
│   │   ├── 3_❤️_Health.py            ✅
│   │   └── 4_🤖_AI_Coach.py          ✅
│   ├── components/
│   │   ├── metrics.py                ✅
│   │   └── charts.py                 ✅
│   └── utils/
│       ├── database.py               ✅
│       ├── formatting.py             ✅
│       └── constants.py              ✅
│
├── ai_engine/                        ✅ COMPLETE (Phase 4)
│   ├── __init__.py
│   ├── llm_analyzer.py
│   └── prompts/
│       └── coach_analysis.txt
│
├── airflow/                          ⏳ TODO: Phase 5
│   └── dags/
│
├── data/
│   └── duckdb/
│       └── running_analytics.duckdb  ✅ Active
│
└── scripts/
    └── query_data.py                 ✅
```

---

## 🚀 How to Run

```bash
# Activate Streamlit environment
source venv_streamlit/bin/activate

# Sync latest Garmin data (add --days 90 to backfill health history)
python -m ingestion.ingest_garmin --days 7

# Rebuild dbt gold layer
cd dbt_project && dbt run && cd ..

# Launch dashboard
streamlit run "streamlit_app/0_📊_Dashboard.py"
# → http://localhost:8501
```

---

## 🎓 Success Criteria for Job Applications

Your project now demonstrates:

- ✅ **Analytics Engineering**: dbt medallion architecture, data modelling, testing
- ✅ **Data Engineering**: Garmin API integration, DuckDB pipeline, incremental loads
- ✅ **Data Analytics**: SQL aggregations, rolling averages, recovery scoring
- ✅ **Data Visualisation**: Streamlit + Plotly multi-page dashboard
- ✅ **AI Engineering**: Claude API integration, prompt engineering, context compression
- ⏳ **Orchestration**: Airflow DAGs, scheduling ← _Phase 5_

### Portfolio talking points (ready to use)

- "Built end-to-end data pipeline: Garmin Connect API → DuckDB medallion architecture → dbt transformations → Streamlit dashboard"
- "Implemented race detection using Garmin's event_type field — fixed false positives that distance-based heuristics produced"
- "Calculated custom recovery score (0–100) from sleep, HRV, resting HR, stress and Body Battery using dbt SQL"
- "Built 5-page interactive analytics dashboard with Plotly charts and Garmin-inspired design"
- "Resolved Streamlit ↔ DuckDB Arrow serialisation incompatibility by switching to session_state caching"
- "Integrated Claude API for AI coaching: designed token-efficient context compression (aggregates not raw rows), deterministic alert layer separate from LLM, structured 4-section prompt with jargon policy"

---

## 💡 Starting the Next Session

Share this file at the start of a new Claude conversation, then say:

```
I'm working on a running analytics portfolio project.
Phases 1–4 are complete (Garmin ingestion → dbt → Streamlit dashboard → AI Coach).
Now I want to build Phase 5: Airflow orchestration.

Here's my NEXT_STEPS.md: [paste this file]
```
