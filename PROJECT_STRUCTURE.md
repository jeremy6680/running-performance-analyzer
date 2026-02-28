# Running Performance Analyzer — Project Structure

## Overview

Full annotated folder tree reflecting the current state of the project (Phases 1-4 complete).

---

## Folder Tree

```
running-performance-analyzer/
|
|-- README.md                              # Project overview and portfolio summary
|-- SETUP_GUIDE.md                         # Developer onboarding (how to run the project)
|-- NEXT_STEPS.md                          # Detailed implementation log and roadmap
|-- PROJECT_STRUCTURE.md                   # This file
|
|-- docker-compose.yml                     # Airflow + service orchestration
|-- .env.example                           # Environment variable template (copy to .env)
|-- .gitignore                             # Git exclusions (credentials, data, venvs)
|-- requirements.txt                       # Streamlit Cloud runtime deps (minimal)
|-- requirements-pipeline.txt              # Pipeline deps: ingestion, dbt, Airflow
|-- requirements-dev.txt                   # All deps + dev tools (includes the two above)
|
|-- ingestion/                             # DATA INGESTION LAYER
|   |-- __init__.py
|   |-- config.py                          # Pydantic config (reads .env, validates credentials)
|   |-- garmin_connector.py                # Garmin Connect API wrapper (activities + health)
|   |-- duckdb_manager.py                  # Bronze layer: creates tables, upsert logic
|   |-- ingest_garmin.py                   # CLI entry point (--days, --initial, --mode)
|   |-- utils.py                           # Shared utilities (date helpers, data cleaning)
|   `-- test_connector.py                  # Basic connector smoke tests
|
|-- dbt_project/                           # TRANSFORMATION LAYER (SQL / dbt)
|   |-- dbt_project.yml                    # dbt project config (name, model paths, vars)
|   |-- profiles.yml                       # DuckDB connection profile
|   |-- packages.yml                       # External dbt packages
|   `-- models/
|       |-- _sources.yml                   # Raw DuckDB table declarations
|       |-- staging/                       # SILVER LAYER — cleaned and typed data
|       |   |-- schema.yml                 # Column tests and documentation
|       |   |-- stg_garmin_activities.sql  # 482-line model: pace zones, HR zones, TRIMP,
|       |   |                              #   race detection, terrain classification
|       |   `-- stg_garmin_health.sql      # Sleep, HRV, stress, body battery cleaning
|       |-- intermediate/                  # Joins and pre-aggregations
|       |   |-- schema.yml
|       |   `-- int_unified_activities.sql # Merges sources, standardises activity types
|       `-- marts/                         # GOLD LAYER — analytics-ready tables
|           |-- schema.yml
|           |-- mart_activity_performance.sql  # Per-activity metrics
|           |-- mart_training_summary.sql      # Weekly aggregations + rolling 4-week averages
|           |-- mart_health_trends.sql         # Daily health with 7/28-day rolling averages,
|           |                                  #   recovery score, training readiness
|           `-- mart_race_performance.sql      # Race history, PRs, readiness context
|
|-- streamlit_app/                         # PRESENTATION LAYER
|   |-- 0_Dashboard.py                     # Home page: recovery status, weekly stats, hero section
|   |-- pages/
|   |   |-- 1_Training_Analysis.py         # Training load, pace trends, HR zones, scatter plots
|   |   |-- 2_Race_Performance.py          # Race history, personal records, pace progression
|   |   |-- 3_Health.py                    # Sleep, HRV, stress, body battery, recovery score
|   |   `-- 4_AI_Coach.py                  # Claude API coaching page + saved analyses
|   |-- components/
|   |   |-- __init__.py
|   |   |-- metrics.py                     # Reusable metric card components
|   |   `-- charts.py                      # Reusable Plotly chart components
|   |-- utils/
|   |   |-- __init__.py
|   |   |-- database.py                    # DuckDB data loading (fetchall pattern, no Arrow)
|   |   |-- formatting.py                  # Pace, time, distance formatters
|   |   `-- constants.py                   # Colour palette, HR zone definitions
|   |-- .streamlit/
|   |   `-- config.toml                    # Streamlit theme and server settings
|   `-- requirements.txt                   # Streamlit-specific deps (Streamlit 1.45.0 pinned)
|
|-- ai_engine/                             # AI / LLM LAYER
|   |-- __init__.py
|   |-- llm_analyzer.py                    # Core engine:
|   |                                      #   build_coaching_context() — aggregates 3 DataFrames
|   |                                      #   calculate_alerts() — 5 deterministic thresholds
|   |                                      #   get_coaching_analysis() — calls Claude API
|   `-- prompts/
|       `-- coach_analysis.txt             # System prompt: 4-section structure + jargon policy
|
|-- airflow/                               # ORCHESTRATION LAYER (Phase 5 — in progress)
|   |-- dags/                              # TODO: garmin_ingestion.py, dbt_orchestration.py
|   |-- plugins/                           # Custom Airflow operators (if needed)
|   `-- requirements.txt                   # Airflow-specific Python deps
|
|-- scripts/
|   `-- query_data.py                      # Ad-hoc DuckDB exploration helper
|
|-- tests/                                 # AUTOMATED TESTS
|   |-- __init__.py
|   |-- test_ingestion.py                  # Garmin connector + DuckDB manager tests
|   |-- test_transformations.py            # Business logic tests
|   `-- test_ai_engine.py                  # LLM analyzer tests
|
|-- data/
|   |-- duckdb/
|   |   `-- running_analytics.duckdb       # Main DuckDB file (versioned in Git)
|   |-- raw/                               # Temporary raw files (git ignored)
|   `-- exports/                           # CSV/Excel exports (git ignored)
|
`-- notebooks/                             # Exploratory Jupyter notebooks
    |-- 01_data_exploration.ipynb
    `-- 02_garmin_api_testing.ipynb
```

---

## Data Flow

```
1. INGESTION (Python / Airflow)
   Garmin Connect API
     --> garmin_connector.py
       --> duckdb_manager.py
         --> raw_garmin_activities (Bronze)
         --> raw_garmin_daily_health (Bronze)

2. TRANSFORMATION (dbt)
   Bronze --> stg_garmin_activities (Silver)
           --> stg_garmin_health (Silver)
             --> int_unified_activities
               --> mart_training_summary (Gold)
               --> mart_race_performance (Gold)
               --> mart_health_trends (Gold)
               --> mart_activity_performance (Gold)

3. PRESENTATION (Streamlit)
   Gold marts --> database.py (fetchall)
                --> Pandas DataFrames
                  --> Plotly charts / metric cards

4. AI COACHING (Claude API)
   Gold marts --> build_coaching_context()
               --> calculate_alerts() [deterministic, no API cost]
               --> get_coaching_analysis() [Claude API]
                 --> Markdown coaching report
```

---

## Key Schema Reference

These are the actual column names in the gold layer (important — do not guess).

```
mart_training_summary:
  week_start_date, total_distance_km, total_training_load,
  avg_pace_min_per_km,                         -- NOT average_pace_min_per_km
  pct_zone1_easy, pct_zone2_moderate, pct_zone3_tempo,
  pct_zone4_threshold, pct_zone5_max,
  rolling_4wk_avg_distance_km, rolling_4wk_avg_training_load

mart_health_trends:
  date,                                        -- NOT health_date
  total_sleep_hours, hrv_numeric, resting_heart_rate,
  average_stress_level, recovery_score, training_readiness

mart_race_performance:
  race_date, race_distance_category,
  pace_min_per_km,                             -- NOT average_pace_min_per_km
  finish_time_formatted,                       -- format: H:MM:SS
  is_personal_record, performance_rating, race_readiness_score
```

---

## Environment Notes

| Virtual Env      | Use for                        | Key constraint                     |
| ---------------- | ------------------------------ | ---------------------------------- |
| `venv`           | ingestion, dbt, scripts, tests | Requires Python 3.11.9 (not 3.12+) |
| `venv_streamlit` | Streamlit dashboard            | Streamlit 1.45.0 (Arrow compat)    |

Two envs are required because Streamlit 1.54+ conflicts with DuckDB 1.4.4 via PyArrow.
