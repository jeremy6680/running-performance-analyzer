# 🏃 Running Performance Analyzer - Next Steps

## ✅ What We've Accomplished So Far

### Phase 1: Project Setup & Data Ingestion (COMPLETED ✓)

#### Infrastructure

- [x] Project structure created with proper folder organization
- [x] Git repository initialized and configured
- [x] Python virtual environment with Python 3.11.9
- [x] All core dependencies installed (pandas, duckdb, dbt, streamlit, etc.)
- [x] Environment configuration with `.env` file
- [x] Docker Compose configuration for future Airflow deployment

#### Data Ingestion Pipeline

- [x] **Garmin Connect API Integration**
  - `ingestion/garmin_connector.py` - Full-featured API connector
  - Session management (saves/loads sessions to avoid re-login)
  - Fetches activities (runs with distance, pace, HR, elevation, etc.)
  - Fetches daily health (steps, sleep, HRV, stress, body battery, etc.)
  - Error handling and logging with loguru

- [x] **DuckDB Database Layer (Bronze)**
  - `ingestion/duckdb_manager.py` - Database manager
  - Bronze layer tables created:
    - `raw_garmin_activities` (29 columns with audit fields)
    - `raw_garmin_daily_health` (24 columns with audit fields)
  - Upsert logic (insert new, skip duplicates)
  - Query helper methods

- [x] **Ingestion Scripts**
  - `ingestion/ingest_garmin.py` - Main ingestion script
  - CLI with options (--days, --initial, --mode)
  - Successfully tested with real data

- [x] **Utilities**
  - `ingestion/config.py` - Configuration management with Pydantic
  - `ingestion/utils.py` - Utility functions (date handling, conversions, calculations)
  - `ingestion/test_connector.py` - Test script for API
  - `scripts/query_data.py` - Data exploration script

#### Current Data Status

```
✅ 3 activities ingested (last 7 days)
✅ 8 days of health data
✅ Database: data/duckdb/running_analytics.duckdb (fully functional)
```

---

## 🎯 Next Steps - Roadmap

### Phase 2: Data Transformation with dbt (2-3 weeks)

#### Objective

Transform raw data (bronze) into clean, analytics-ready datasets (silver/gold) using dbt.

#### Tasks

**2.1 - dbt Setup**

- [ ] Initialize dbt project: `dbt init dbt_project`
- [ ] Configure `profiles.yml` for DuckDB connection
- [ ] Set up `dbt_project.yml` with project configs
- [ ] Create `sources.yml` to reference bronze tables

**2.2 - Silver Layer (Staging Models)**
Create clean, typed, deduplicated versions of raw data.

Models to create:

- [ ] `stg_garmin_activities.sql`
  - Clean activity data
  - Add calculated fields (pace zones, effort levels)
  - Handle nulls and data quality issues
- [ ] `stg_garmin_health.sql`
  - Clean health metrics
  - Convert units (seconds to hours for sleep)
  - Add date dimensions

- [ ] `int_unified_activities.sql` (intermediate)
  - Merge activities from multiple sources (Garmin + Strava future)
  - Standardize activity types
  - Add business logic

**2.3 - Gold Layer (Marts)**
Create business-focused analytical models.

Models to create:

- [ ] `mart_training_analysis.sql`
  - Weekly aggregations (distance, time, load)
  - Rolling averages (4-week, 8-week)
  - Training load trends
  - Heart rate zone distribution
- [ ] `mart_race_performance.sql`
  - Race results only
  - PR (Personal Record) tracking
  - Race pace analysis
  - Performance trends over time
- [ ] `mart_health_trends.sql`
  - Sleep quality trends
  - HRV evolution
  - Resting heart rate trends
  - Recovery metrics
- [ ] `mart_ai_features.sql`
  - Feature engineering for AI/ML
  - Aggregated metrics for LLM context
  - Training readiness indicators

**2.4 - dbt Testing & Documentation**

- [ ] Add schema tests (not_null, unique, relationships)
- [ ] Add custom data tests (value ranges, logical checks)
- [ ] Write descriptions for all models and columns
- [ ] Generate dbt docs: `dbt docs generate && dbt docs serve`

**2.5 - dbt Deployment**

- [ ] Create `dbt run` command for full refresh
- [ ] Set up incremental models for efficiency
- [ ] Add post-hooks for data quality checks

#### Key dbt Commands

```bash
# Initialize dbt project
cd dbt_project
dbt init

# Run models
dbt run

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve

# Run specific model
dbt run --select stg_garmin_activities

# Run downstream models
dbt run --select +mart_training_analysis
```

#### Resources

- [dbt Documentation](https://docs.getdbt.com/)
- [dbt-duckdb Adapter](https://github.com/jwills/dbt-duckdb)
- [Medallion Architecture Guide](https://www.databricks.com/glossary/medallion-architecture)

---

### Phase 3: Streamlit Dashboard (1-2 weeks)

#### Objective

Create an interactive web dashboard to visualize running analytics and health metrics.

#### Tasks

**3.1 - Basic Dashboard Setup**

- [ ] Create `streamlit_app/app.py` (home page)
- [ ] Set up multi-page structure
- [ ] Configure Streamlit theme and layout
- [ ] Connect to DuckDB (read from gold layer)

**3.2 - Page 1: Overview Dashboard**
File: `streamlit_app/pages/1_📊_Dashboard.py`

- [ ] Key metrics cards (total distance, runs, avg HR)
- [ ] Recent activities table
- [ ] Weekly/monthly trends charts
- [ ] Interactive date range selector

**3.3 - Page 2: Training Analysis**
File: `streamlit_app/pages/2_📈_Training_Analysis.py`

- [ ] Training load chart (weekly, 4-week rolling)
- [ ] Pace progression over time
- [ ] Heart rate zone distribution
- [ ] Distance vs duration scatter plot
- [ ] Filters: activity type, date range

**3.4 - Page 3: Race Performance**
File: `streamlit_app/pages/3_🏃_Race_Performance.py`

- [ ] PR (Personal Record) tracker
- [ ] Race results table
- [ ] Pace comparison across races
- [ ] Goal vs actual performance

**3.5 - Page 4: Health & Recovery**
File: `streamlit_app/pages/4_❤️_Health.py`

- [ ] Sleep trends (hours, quality)
- [ ] Resting heart rate evolution
- [ ] HRV chart (when available)
- [ ] Stress levels over time
- [ ] Body Battery (charge/drain)

**3.6 - Components & Styling**

- [ ] Create reusable chart components (`components/charts.py`)
- [ ] Create metric cards (`components/metrics.py`)
- [ ] Apply custom CSS for better design
- [ ] Add Garmin-like color scheme

#### Key Streamlit Concepts

```python
# Cache data loading
@st.cache_data
def load_data():
    conn = duckdb.connect(DB_PATH)
    return conn.execute("SELECT * FROM mart_training_analysis").df()

# Interactive widgets
date_range = st.date_input("Select date range")
activity_type = st.selectbox("Activity type", ["All", "Running", "Cycling"])

# Charts with Plotly
import plotly.express as px
fig = px.line(df, x='week', y='distance_km')
st.plotly_chart(fig, use_container_width=True)
```

#### Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [Plotly Documentation](https://plotly.com/python/)
- [Streamlit Gallery](https://streamlit.io/gallery) for inspiration

---

### Phase 4: AI Coach Integration (1-2 weeks)

#### Objective

Add AI-powered coaching recommendations using Claude API.

#### Tasks

**4.1 - LLM Integration Setup**

- [ ] Create `ai_engine/llm_analyzer.py`
- [ ] Set up Claude API client (Anthropic)
- [ ] Create prompt templates in `ai_engine/prompts/`

**4.2 - Prompt Engineering**
Create specialized prompts for different use cases:

- [ ] `training_recommendations.txt` - Weekly training advice
- [ ] `injury_prevention.txt` - Risk assessment
- [ ] `race_strategy.txt` - Race-specific coaching
- [ ] `recovery_advice.txt` - Rest and nutrition

**4.3 - AI Coach Page**
File: `streamlit_app/pages/5_🤖_AI_Coach.py`

- [ ] User inputs: race goal (10K, half, marathon), target time
- [ ] Fetch recent training data from gold layer
- [ ] Build context for LLM (last 12 weeks, health trends)
- [ ] Call Claude API with structured prompt
- [ ] Display recommendations in clear sections

**4.4 - Advanced AI Features (Optional)**

- [ ] RAG (Retrieval Augmented Generation) for running knowledge base
- [ ] Multi-agent system (training agent, nutrition agent, recovery agent)
- [ ] Weekly automated email summaries
- [ ] Conversational interface (chatbot)

#### Example AI Prompt Structure

```python
context = f"""
Runner Profile:
- Age: 35, Weight: 70kg, Experience: 5 years
- Goal: Marathon in 3:30:00

Recent Training (12 weeks):
- Average weekly distance: {avg_distance} km
- Average pace: {avg_pace} min/km
- Training load trend: {load_trend}

Health Metrics (7 days):
- Average resting HR: {rhr} bpm
- Average HRV: {hrv} ms
- Sleep quality: {sleep_score}/100
- Stress level: {stress}/100

Question: Provide training recommendations for next 4 weeks.
"""
```

#### Resources

- [Anthropic Claude API Docs](https://docs.anthropic.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [Prompt Engineering Guide](https://www.promptingguide.ai/)

---

### Phase 5: Orchestration with Airflow (1 week)

#### Objective

Automate daily data sync and transformations.

#### Tasks

**5.1 - Airflow Setup (Docker)**

- [ ] Start Airflow: `docker-compose up -d`
- [ ] Access UI: http://localhost:8080
- [ ] Configure connections (DuckDB, Garmin)

**5.2 - Create DAGs**

- [ ] `airflow/dags/garmin_ingestion.py`
  - Schedule: Daily at 6 AM
  - Task 1: Fetch Garmin data
  - Task 2: Load to DuckDB bronze
- [ ] `airflow/dags/dbt_orchestration.py`
  - Schedule: After ingestion
  - Task 1: `dbt run` (all models)
  - Task 2: `dbt test` (data quality)
- [ ] `airflow/dags/weekly_report.py` (optional)
  - Schedule: Every Monday
  - Task: Generate AI summary email

**5.3 - Monitoring & Alerts**

- [ ] Set up email alerts for failures
- [ ] Add retry logic with exponential backoff
- [ ] Log monitoring dashboard

#### Sample DAG Structure

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

with DAG(
    'garmin_to_gold',
    schedule_interval='0 6 * * *',  # Daily at 6 AM
    start_date=datetime(2025, 2, 1),
    catchup=False,
) as dag:

    ingest = PythonOperator(
        task_id='ingest_garmin',
        python_callable=ingest_garmin_data,
    )

    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='cd dbt_project && dbt run',
    )

    ingest >> dbt_run
```

---

### Phase 6: Advanced Features (Future)

**Machine Learning**

- [ ] Predict race times based on training
- [ ] Injury risk prediction model
- [ ] Optimal training load calculator

**Additional Data Sources**

- [ ] Strava integration
- [ ] Apple Health integration
- [ ] Weather API (correlate conditions with performance)

**Social Features**

- [ ] Multi-user support
- [ ] Leaderboards
- [ ] Share achievements

**Mobile App**

- [ ] React Native app
- [ ] Push notifications
- [ ] Quick data entry

---

## 📁 Current Project Structure

```
running-performance-analyzer/
├── .env                           # ✅ Configured
├── .gitignore                     # ✅ Configured
├── docker-compose.yml             # ✅ Configured (Airflow ready)
├── requirements.txt               # ✅ Installed
├── requirements-minimal.txt       # ✅ Installed
│
├── airflow/                       # ⏳ TODO: Create DAGs
│   ├── dags/
│   └── requirements.txt
│
├── dbt_project/                   # 🎯 NEXT PHASE
│   ├── dbt_project.yml           # ⏳ TODO: Initialize
│   ├── models/
│   │   ├── staging/              # ⏳ TODO: Create
│   │   ├── intermediate/         # ⏳ TODO: Create
│   │   └── marts/                # ⏳ TODO: Create
│
├── ingestion/                     # ✅ COMPLETE
│   ├── config.py                 # ✅
│   ├── utils.py                  # ✅
│   ├── garmin_connector.py       # ✅
│   ├── duckdb_manager.py         # ✅
│   ├── ingest_garmin.py          # ✅
│   └── test_connector.py         # ✅
│
├── ai_engine/                     # ⏳ TODO: Phase 4
│   ├── llm_analyzer.py
│   └── prompts/
│
├── streamlit_app/                 # ⏳ TODO: Phase 3
│   ├── app.py
│   ├── pages/
│   └── components/
│
├── data/
│   └── duckdb/
│       └── running_analytics.duckdb  # ✅ 3 activities, 8 health records
│
├── scripts/                       # ✅ COMPLETE
│   └── query_data.py             # ✅
│
└── tests/                         # ⏳ TODO: Add unit tests
```

---

## 🚀 How to Continue

### Immediate Next Session (dbt)

**Before starting a new Claude conversation:**

1. Make sure latest code is committed to Git
2. Have `NEXT_STEPS.md` ready to share
3. Have your data synced and verified

**In new conversation, say:**

```
I'm working on a running analytics project. I've completed Phase 1
(data ingestion from Garmin to DuckDB). Now I need to create dbt
transformations (Phase 2).

Here's my NEXT_STEPS.md: [paste this file]

Current status:
- ✅ Garmin API → DuckDB bronze layer working
- ✅ 3 activities, 8 health records ingested
- 🎯 Need: dbt models (staging, intermediate, marts)

Please help me set up dbt and create the first staging models.
```

### Weekly Workflow (Once Airflow is set up)

```bash
# Data will sync automatically via Airflow
# Just check the dashboard!

# Manual sync if needed:
python -m ingestion.ingest_garmin

# Query your data:
python scripts/query_data.py --stats

# View dashboard:
streamlit run streamlit_app/app.py
```

---

## 📚 Learning Resources

### dbt

- [dbt Courses](https://courses.getdbt.com/)
- [dbt Best Practices](https://docs.getdbt.com/guides/best-practices)
- [Analytics Engineering Guide](https://www.getdbt.com/analytics-engineering/)

### Streamlit

- [30 Days of Streamlit](https://30days.streamlit.app/)
- [Streamlit Cheat Sheet](https://docs.streamlit.io/library/cheatsheet)

### LLM / AI

- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook)
- [LangChain Tutorials](https://python.langchain.com/docs/tutorials)
- [Prompt Engineering Course](https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/)

### Data Engineering

- [Fundamentals of Data Engineering](https://www.oreilly.com/library/view/fundamentals-of-data/9781098108298/)
- [The Data Warehouse Toolkit](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/)

---

## 🎯 Success Criteria

### For Job Applications

Your completed project should demonstrate:

- ✅ **Analytics Engineering**: dbt transformations, medallion architecture, data modeling
- ✅ **Data Engineering**: API integration, orchestration, data pipelines
- ✅ **AI Engineering**: LLM integration, prompt engineering, RAG
- ✅ **Data Analytics**: SQL queries, visualizations, metrics

### GitHub README Should Include

- Project overview and motivation
- Architecture diagram
- Tech stack with logos
- Screenshots of dashboard
- Setup instructions
- Sample queries and outputs
- Link to live demo (Streamlit Cloud)

### Portfolio Talking Points

- "Built end-to-end data pipeline processing 1000+ activities"
- "Implemented medallion architecture with dbt for data transformation"
- "Created AI-powered coaching using Claude API with RAG"
- "Automated daily sync with Airflow orchestration"
- "Interactive dashboard with Streamlit and Plotly"

---

## ❓ Common Questions

**Q: Do I need to finish everything before applying for jobs?**
A: No! Even Phase 1 + 2 (ingestion + dbt) is impressive. Add phases incrementally.

**Q: Should I deploy this publicly?**
A: Yes! Deploy Streamlit to Streamlit Cloud (free). Makes your portfolio much stronger.

**Q: Can I use this for other sports?**
A: Absolutely! The architecture works for cycling, swimming, etc. Just adjust data sources.

**Q: How do I explain this to recruiters?**
A: "Built a personal analytics platform to demonstrate modern data engineering skills. Real-world use case with my own running data."

---

## 🙏 Good Luck!

You've built a solid foundation. The hard part (API integration, database setup) is done.

**Next up: dbt transformations** - this is where data engineering really shines!

Keep pushing, and remember: this project is your ticket to a data/AI engineering role! 🚀

---

**Questions? Issues?**

- Check dbt/Streamlit/Claude API documentation
- Use Claude for debugging help
- Join data engineering communities (dbt Slack, r/dataengineering)

**Happy coding!** 💪
