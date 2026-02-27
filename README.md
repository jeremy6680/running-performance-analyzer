# Running Performance Analyzer

**An AI-powered analytics platform for runners** that ingests training data from Garmin Connect,
transforms it using modern data engineering practices, and provides personalised insights
through LLM-based coaching.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![dbt](https://img.shields.io/badge/dbt-1.7-orange.svg)](https://www.getdbt.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.45-red.svg)](https://streamlit.io/)
[![Airflow](https://img.shields.io/badge/Airflow-2.8-green.svg)](https://airflow.apache.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [About](#about)

---

## Overview

This project demonstrates a complete **modern data stack** for personal running analytics:

1. **Data Ingestion**: Automated daily sync from Garmin Connect API (activities + health metrics)
2. **Data Transformation**: dbt models following medallion architecture (Bronze -> Silver -> Gold)
3. **Orchestration**: Airflow DAGs for pipeline automation
4. **Analytics**: Interactive Streamlit dashboard with Plotly visualisations
5. **AI Insights**: LLM-powered coaching using Claude API (Anthropic)
6. **Weather Context**: Open-Meteo API integration for contextual training recommendations

**Use Case**: As a runner, I want to understand my training patterns, track health metrics
(HR, HRV, VO2max), and receive data-driven recommendations to improve performance and prevent injuries.

**Target Audience**: Data engineers, analytics engineers, AI engineers, and data analysts
looking for a real-world portfolio project.

---

## Key Features

### Analytics Dashboard

- Weekly/monthly training volume trends
- Heart rate zone distribution
- Pace progression analysis
- Training load monitoring (TRIMP-based)
- Sleep, HRV, and recovery metrics

### AI-Powered Coaching

- Personalised training recommendations based on your last 4 weeks of data
- Deterministic alert layer (ACWR, HRV trend, sleep deficit) computed locally — no API cost
- Race performance predictions and goal gap analysis
- Analyses saved for future reference (session history)
- Transparent context window shown in UI (portfolio-friendly)

### Automated Data Pipeline

- Daily sync from Garmin Connect (activities + health metrics)
- Data quality tests with dbt (171 tests, 97-100% pass rate)
- Incremental models for efficiency
- Error handling and retry logic with loguru

### Advanced Metrics

- Rolling 4-week averages (distance, load, pace)
- Heart rate variability (HRV) trends
- Custom recovery score (0-100) from sleep + HRV + resting HR + stress + Body Battery
- Race detection using Garmin's `event_type` field (avoids false positives from distance heuristics)
- Terrain and pace zone classification

---

## Architecture

```
+----------------------------------------------------------+
|                  Presentation Layer                       |
|               (Streamlit Dashboard — 5 pages)            |
+----------------------------------------------------------+
                           |
+----------------------------------------------------------+
|                   Analytics Layer                         |
|               (dbt Marts — Gold Layer)                   |
|  mart_training_summary   mart_race_performance           |
|  mart_health_trends      mart_activity_performance       |
+----------------------------------------------------------+
                           |
+----------------------------------------------------------+
|                 Transformation Layer                      |
|             (dbt Staging/Intermediate — Silver)          |
|  stg_garmin_activities   stg_garmin_health               |
|  int_unified_activities                                   |
+----------------------------------------------------------+
                           |
+----------------------------------------------------------+
|                    Storage Layer                          |
|                (DuckDB — Bronze Layer)                   |
|  raw_garmin_activities   raw_garmin_daily_health         |
+----------------------------------------------------------+
                           ^
+----------------------------------------------------------+
|                   Ingestion Layer                         |
|              (Airflow DAGs + Python)                     |
|  Garmin Connect API      Open-Meteo API                  |
|  Data validation         Session management              |
+----------------------------------------------------------+
```

**Key Design Principles**:

- **Medallion Architecture**: Bronze (raw) -> Silver (cleaned) -> Gold (analytics)
- **Separation of Concerns**: Ingestion, transformation, and presentation are decoupled
- **Reproducibility**: All transformations in SQL/dbt, versioned in Git
- **Testability**: 171 dbt tests + pytest for data quality

---

## Tech Stack

| Layer               | Technologies              |
| ------------------- | ------------------------- |
| **Orchestration**   | Apache Airflow, Docker    |
| **Data Warehouse**  | DuckDB 1.4                |
| **Transformation**  | dbt-core, SQL             |
| **Data Processing** | Python 3.11, Pandas       |
| **Visualisation**   | Streamlit 1.45, Plotly    |
| **AI/LLM**          | Anthropic Claude API      |
| **API Integration** | garminconnect, Open-Meteo |
| **Config**          | Pydantic, python-dotenv   |
| **Logging**         | loguru                    |
| **Testing**         | pytest, dbt tests         |
| **CI/CD**           | GitHub Actions (planned)  |

---

## Getting Started

See **[SETUP_GUIDE.md](SETUP_GUIDE.md)** for full installation instructions.

### Quick start

```bash
# 1. Clone and configure
git clone https://github.com/yourusername/running-performance-analyzer.git
cd running-performance-analyzer
cp .env.example .env  # fill in GARMIN_EMAIL, GARMIN_PASSWORD, ANTHROPIC_API_KEY

# 2. Install dependencies (two envs required — see SETUP_GUIDE.md)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Fetch initial data (90 days recommended)
python -m ingestion.ingest_garmin --days 90
cd dbt_project && dbt run && cd ..

# 4. Launch dashboard
source venv_streamlit/bin/activate
streamlit run "streamlit_app/0_Dashboard.py"
# Open http://localhost:8501
```

> **Important**: Two virtual environments are required due to a DuckDB/Streamlit PyArrow
> compatibility issue. See SETUP_GUIDE.md for details.

---

## Usage

### Daily data sync

```bash
source venv/bin/activate
python -m ingestion.ingest_garmin --days 7
cd dbt_project && dbt run
```

Or let Airflow handle it automatically (runs daily at 6 AM Europe/Paris).

### AI Coach

1. Go to the **AI Coach** page in Streamlit
2. Enter your race goal (10K, Half Marathon, Marathon) and target time
3. Click **Generate Recommendations**
4. Receive a personalised 4-section coaching report based on your last 4 weeks of data

### Direct database access

```bash
duckdb data/duckdb/running_analytics.duckdb
SELECT * FROM mart_training_summary ORDER BY week_start_date DESC LIMIT 10;
```

---

## Roadmap

### Phases 1-4: Core Platform (COMPLETE)

- [x] Garmin API integration with session management
- [x] DuckDB medallion architecture (Bronze/Silver/Gold)
- [x] dbt transformation layer with 171 data quality tests
- [x] 5-page Streamlit dashboard (training, race, health, AI coach)
- [x] Claude API integration with deterministic alert layer
- [x] Weather context via Open-Meteo API
- [x] Docker Compose configuration

### Phase 5: Orchestration (COMPLETE)

- [x] Airflow DAG for daily Garmin ingestion (6 AM Europe/Paris)
- [x] Airflow DAG for dbt run + dbt test (triggered on ingestion success)
- [ ] Failure alerting (email/Slack) -- Phase 6

### Phase 6: Advanced Features (Future)

- [ ] Strava integration
- [ ] ML injury risk prediction
- [ ] RAG for running knowledge base (LlamaIndex / LangGraph)
- [ ] Streamlit Cloud deployment
- [ ] GitHub Actions CI/CD

---

## Project Structure

```
running-performance-analyzer/
├── ingestion/              # Garmin API connector, DuckDB manager, config
├── dbt_project/            # dbt models (staging -> intermediate -> marts)
├── streamlit_app/          # 5-page Streamlit dashboard + components + utils
├── ai_engine/              # Claude API integration, prompts, coaching logic
├── airflow/                # Airflow DAGs (Phase 5)
├── scripts/                # Data exploration utilities
├── tests/                  # pytest unit and integration tests
├── data/duckdb/            # DuckDB database file
└── docker-compose.yml      # Airflow service orchestration
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the full annotated tree.

---

## About

**Author**: Jeremy Marchandeau
**LinkedIn**: [linkedin.com/in/jeremymarchandeau](https://linkedin.com/in/jeremymarchandeau)
**Email**: hey@jeremymarchandeau.com

**Context**: Built during my transition from web development (12 years, WordPress/PHP/JS)
to data and AI engineering. This project demonstrates proficiency across the full modern data stack:

- **Analytics Engineering**: dbt medallion architecture, data modelling, testing
- **Data Engineering**: API integration, DuckDB pipeline, incremental loads, Airflow
- **AI Engineering**: Claude API, prompt engineering, token-efficient context compression
- **Data Analytics**: SQL aggregations, rolling averages, custom scoring, Plotly visualisations
- **Orchestration**: Airflow DAG chaining, scheduling, Docker deployment

### Portfolio talking points

- "Built end-to-end pipeline: Garmin Connect API -> DuckDB medallion architecture -> dbt -> Streamlit"
- "Implemented race detection using Garmin's `event_type` field, eliminating false positives from distance heuristics"
- "Calculated custom recovery score (0-100) from sleep, HRV, resting HR, stress and Body Battery in SQL"
- "Resolved Streamlit/DuckDB Arrow serialisation incompatibility through separate virtual environments"
- "Designed token-efficient AI context (aggregates not raw rows), with deterministic alert layer separate from LLM"

---

## Acknowledgements

- [garminconnect](https://github.com/cyberjunky/python-garminconnect) for the Garmin API wrapper
- [dbt Labs](https://www.getdbt.com/) for the transformation framework
- [Anthropic](https://www.anthropic.com/) for Claude API
- [Open-Meteo](https://open-meteo.com/) for free weather API

---

**Built with care for runners and data enthusiasts**
