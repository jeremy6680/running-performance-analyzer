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
mart_training_summary:    rolling_4wk_avg_distance_km, rolling_4wk_avg_training_load
                          pct_zone1_easy, pct_zone2_moderate, pct_zone3_tempo,
                          pct_zone4_threshold, pct_zone5_max
mart_health_trends:       date (not health_date), total_sleep_hours, hrv_numeric,
                          average_stress_level, recovery_score, training_readiness
mart_race_performance:    race_date, finish_time_formatted (H:MM:SS), is_personal_record,
                          performance_rating, race_readiness_score
```

---

### Phase 3: Streamlit Dashboard (COMPLETED ✓)

#### Infrastructure
- [x] Separate virtual environment `venv_streamlit` with Streamlit 1.45.0
  - Downgraded from 1.54.0 to fix DuckDB 1.4.4 Arrow serialisation error
  - All pages use `st.session_state` instead of `@st.cache_data`
- [x] Modular architecture:
  - `utils/database.py` — data loading functions
  - `utils/formatting.py` — pace, time, distance formatters
  - `utils/constants.py` — Garmin-inspired colour palette, HR zones, activity types
  - `components/metrics.py` — reusable metric cards
  - `components/charts.py` — reusable Plotly chart components

#### Pages Built
- [x] `0_📊_Dashboard.py` — home page
  - Gradient hero title, data range badge
  - All-time stats row (total distance, runs, time, PRs)
  - Today's recovery status with readiness badge
  - Navigation cards linking to all 4 sub-pages
  - Light Garmin-inspired theme (no dark sidebar override)

- [x] `pages/1_📊_Dashboard.py` — weekly overview
  - Recent activities table, key metric cards
  - Weekly/monthly distance trends

- [x] `pages/2_📈_Training_Analysis.py` — training load & pace
  - Weekly training load (TRIMP) bar chart + 4-week rolling avg
  - Distance & pace dual-axis chart + 4-week rolling avg
  - HR zone distribution bar chart with 80/20 rule assessment
  - Distance vs duration scatter, coloured by effort level (toggle-able)
  - Toggles: `Show 4-week rolling avg` / `Show effort level on scatter`

- [x] `pages/3_🏃_Race_Performance.py` — race history & PRs
  - Career summary (total races, PRs, best pace)
  - Race history table with emoji PR indicators
  - Pace progression scatter (PR lines per distance category)
  - PR cards per distance
  - Race readiness & training context charts

- [x] `pages/4_❤️_Health.py` — health & recovery
  - Sleep trends bar chart (colour-coded) + 7-day avg + sleep stage breakdown
  - Resting HR & HRV side-by-side charts
  - Stress levels & Body Battery range charts
  - Recovery score timeline with coloured markers + readiness breakdown
  - Daily steps chart
  - Data range info banner (shows when selected period exceeds available data)
  - Toggle: `Show 7-day rolling avg`

#### Bug fixes applied
- `pages/2_📈_Training_Analysis.py` — rolling avg lines were never drawn because the page
  checked for `rolling_4wk_avg_distance` / `rolling_4wk_avg_load` (wrong). Corrected to
  `rolling_4wk_avg_distance_km` / `rolling_4wk_avg_training_load` (real mart column names).
  Also renamed `Show effort annotations` → `Show effort level on scatter` and wired it to
  actually toggle the scatter colour column.
- `0_📊_Dashboard.py` — duplicate 🏃 emoji in H1 title removed (`APP_TITLE` already contains the emoji;
  the HTML template was prepending a second one).
- `pages/4_❤️_Health.py` — period filter appeared broken because all date ranges returned
  the same data. Root cause: health data only starts Feb 8, 2026. Added a blue info banner
  that appears whenever the selected period extends beyond the earliest available date,
  explaining the gap and showing the sync command.

#### Known data limitation
Health data only goes back to Feb 8, 2026. To sync more history:
```bash
python -m ingestion.ingest_garmin --days 90
cd dbt_project && dbt run
```

---

## 🎯 Next Steps — Roadmap

### Phase 4: AI Coach Integration (NEXT 🎯)

#### Objective
Add AI-powered coaching recommendations using Claude API (Anthropic).

#### Tasks

**4.1 - LLM Integration Setup**
- [ ] Create `ai_engine/llm_analyzer.py`
- [ ] Set up Anthropic Claude API client
- [ ] Create prompt templates in `ai_engine/prompts/`

**4.2 - Prompt Engineering**
- [ ] `training_recommendations.txt` — weekly training advice
- [ ] `injury_prevention.txt` — risk assessment based on load trends
- [ ] `race_strategy.txt` — race-specific coaching
- [ ] `recovery_advice.txt` — rest and nutrition suggestions

**4.3 - AI Coach Page**
File: `streamlit_app/pages/5_🤖_AI_Coach.py`
- [ ] User inputs: race goal (10K/half/marathon), target time
- [ ] Fetch last 12 weeks from `mart_training_summary` + `mart_health_trends`
- [ ] Build structured context for LLM
- [ ] Call Claude API and display recommendations in clear sections

**4.4 - Context building (gold layer data → LLM prompt)**
```python
context = f"""
Recent Training (12 weeks):
- Avg weekly distance: {avg_distance} km
- Avg pace: {avg_pace} min/km
- Training load trend: {load_trend}
- HR zone distribution: {easy_pct}% easy / {hard_pct}% hard

Health (7 days):
- Avg resting HR: {rhr} bpm  |  Avg HRV: {hrv} ms
- Avg sleep: {sleep}h  |  Avg stress: {stress}/100
- Current training readiness: {readiness}

Goal: {race_distance} in {target_time}
"""
```

#### Key resources
- [Anthropic Claude API Docs](https://docs.anthropic.com/)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)

---

### Phase 5: Orchestration with Airflow (1 week)

#### Objective
Automate daily data sync and dbt transformations.

#### Tasks
- [ ] Start Airflow: `docker-compose up -d`
- [ ] `airflow/dags/garmin_ingestion.py` — daily at 6 AM, fetch + load to bronze
- [ ] `airflow/dags/dbt_orchestration.py` — `dbt run` + `dbt test` after ingestion
- [ ] Email alerts for pipeline failures

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
│   ├── garmin_connector.py           ✅ (includes event_type)
│   ├── duckdb_manager.py             ✅ (includes migrate_add_event_type)
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
│   ├── 0_📊_Dashboard.py             ✅ Home page (light theme)
│   ├── pages/
│   │   ├── 1_📊_Dashboard.py         ✅
│   │   ├── 2_📈_Training_Analysis.py ✅
│   │   ├── 3_🏃_Race_Performance.py  ✅
│   │   └── 4_❤️_Health.py            ✅
│   ├── components/
│   │   ├── metrics.py                ✅
│   │   └── charts.py                 ✅
│   └── utils/
│       ├── database.py               ✅
│       ├── formatting.py             ✅
│       └── constants.py              ✅
│
├── ai_engine/                        ⏳ TODO: Phase 4
│   ├── llm_analyzer.py
│   └── prompts/
│
├── airflow/                          ⏳ TODO: Phase 5
│   └── dags/
│
├── data/
│   └── duckdb/
│       └── running_analytics.duckdb  ✅ Active (23 activities, ~10 days health)
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
- ⏳ **AI Engineering**: Claude API integration, prompt engineering ← *Phase 4*
- ⏳ **Orchestration**: Airflow DAGs, scheduling ← *Phase 5*

### Portfolio talking points (ready to use)
- "Built end-to-end data pipeline: Garmin Connect API → DuckDB medallion architecture → dbt transformations → Streamlit dashboard"
- "Implemented race detection using Garmin's event_type field — fixed false positives that distance-based heuristics produced"
- "Calculated custom recovery score (0–100) from sleep, HRV, resting HR, stress and Body Battery using dbt SQL"
- "Built 4-page interactive analytics dashboard with Plotly charts and Garmin-inspired design"
- "Resolved Streamlit ↔ DuckDB Arrow serialisation incompatibility by switching to session_state caching"

---

## 💡 Starting the Next Session

Share this file at the start of a new Claude conversation, then say:

```
I'm working on a running analytics portfolio project.
Phases 1–3 are complete (Garmin ingestion → dbt → Streamlit dashboard).
Now I want to build Phase 4: the AI Coach page using Claude API.

Here's my NEXT_STEPS.md: [paste this file]
```
