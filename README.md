# 🏃 Running Performance Analyzer

**An AI-powered analytics platform for runners** that ingests training data from Garmin/Strava, transforms it using modern data engineering practices, and provides personalized insights through LLM-based coaching.

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![dbt](https://img.shields.io/badge/dbt-1.7-orange.svg)](https://www.getdbt.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31-red.svg)](https://streamlit.io/)
[![Airflow](https://img.shields.io/badge/Airflow-2.8-green.svg)](https://airflow.apache.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Screenshots](#screenshots)
- [Development](#development)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

This project demonstrates a complete **modern data stack** implementation for personal running analytics:

1. **Data Ingestion**: Automated daily sync from Garmin Connect API
2. **Data Transformation**: dbt models following medallion architecture (Bronze → Silver → Gold)
3. **Orchestration**: Airflow DAGs for pipeline automation
4. **Analytics**: Interactive Streamlit dashboard with Plotly visualizations
5. **AI Insights**: LLM-powered coaching using Claude API (Anthropic)

**Use Case**: As a runner, I want to understand my training patterns, track health metrics (HR, HRV, VO2max), and receive data-driven recommendations to improve performance and prevent injuries.

**Target Audience**: Data engineers, analytics engineers, AI engineers, and data analysts looking for a real-world portfolio project.

---

## ✨ Key Features

### 📊 Analytics Dashboard

- Weekly/monthly training volume trends
- Heart rate zone distribution
- Pace progression analysis
- Training load monitoring
- Sleep and recovery metrics

### 🤖 AI-Powered Coaching

- Personalized training recommendations based on your data
- Injury risk assessment using training load ratios
- Race performance predictions
- Nutrition and recovery suggestions

### 🔄 Automated Data Pipeline

- Daily sync from Garmin Connect (activities + health metrics)
- Data quality tests with dbt
- Incremental models for efficiency
- Error handling and retry logic

### 📈 Advanced Metrics

- Rolling 4-week averages (distance, load, pace)
- Heart rate variability (HRV) trends
- Training Stress Score (TSS) calculation
- VO2max progression tracking

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│                   (Streamlit Dashboard)                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     Analytics Layer                          │
│                  (dbt Marts - Gold Layer)                    │
│  • mart_training_analysis   • mart_race_performance          │
│  • mart_health_trends        • mart_ai_features              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Transformation Layer                        │
│                (dbt Staging - Silver Layer)                  │
│  • stg_garmin_activities   • stg_garmin_health               │
│  • int_unified_activities                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                           │
│                    (DuckDB - Bronze Layer)                   │
│  • raw_garmin_activities   • raw_garmin_daily_health         │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion Layer                           │
│                   (Airflow DAGs + Python)                    │
│  • Garmin Connect API   • Data validation                   │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Principles**:

- **Medallion Architecture**: Bronze (raw) → Silver (cleaned) → Gold (analytics)
- **Separation of Concerns**: Ingestion, transformation, presentation are decoupled
- **Reproducibility**: All transformations in SQL/dbt, versioned in Git
- **Testability**: dbt tests + pytest for data quality

---

## 🛠️ Tech Stack

| Layer               | Technologies                    |
| ------------------- | ------------------------------- |
| **Orchestration**   | Apache Airflow, Docker          |
| **Data Warehouse**  | DuckDB                          |
| **Transformation**  | dbt-core, SQL                   |
| **Data Processing** | Python, Pandas                  |
| **Visualization**   | Streamlit, Plotly               |
| **AI/LLM**          | Anthropic Claude API, LangChain |
| **API Integration** | garminconnect, requests         |
| **Testing**         | pytest, dbt tests               |
| **CI/CD**           | GitHub Actions (planned)        |

---

## 📁 Project Structure

```
running-performance-analyzer/
├── airflow/                    # Airflow DAGs and configuration
├── dbt_project/                # dbt models and tests
├── ingestion/                  # API connectors (Garmin, Strava)
├── ai_engine/                  # LLM analyzer and prompts
├── streamlit_app/              # Web dashboard (entry: 0_📊_Dashboard.py)
├── data/                       # DuckDB database
├── notebooks/                  # Jupyter notebooks for exploration
├── tests/                      # Unit and integration tests
├── docker-compose.yml          # Service orchestration
└── requirements.txt            # Python dependencies
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed documentation.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Garmin Connect account
- Anthropic API key (for AI features)

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/jeremy6680/running-performance-analyzer.git
   cd running-performance-analyzer
   ```

2. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env and add your credentials:
   # - GARMIN_EMAIL
   # - GARMIN_PASSWORD
   # - ANTHROPIC_API_KEY
   ```

3. **Create required directories**

   ```bash
   mkdir -p airflow/{dags,logs,plugins}
   mkdir -p data/{duckdb,raw,exports}
   ```

4. **Set Airflow UID** (Linux/Mac)

   ```bash
   echo -e "AIRFLOW_UID=$(id -u)" >> .env
   ```

5. **Start services with Docker Compose**

   ```bash
   docker-compose up -d
   ```

6. **Wait for initialization** (first time only)

   ```bash
   docker-compose logs -f airflow-init
   # Wait for "Airflow initialization complete!"
   ```

7. **Access the applications**
   - **Airflow UI**: http://localhost:8080 (login: admin/admin)
   - **Streamlit Dashboard**: http://localhost:8501

---

## 💡 Usage

### Initial Data Sync

1. **Trigger Garmin ingestion DAG** in Airflow UI
   - Go to http://localhost:8080
   - Find `garmin_to_duckdb` DAG
   - Click "Trigger DAG"
   - This will fetch your last 365 days of data

2. **Run dbt transformations**
   - The DAG automatically runs dbt after ingestion
   - Or manually: `docker-compose exec airflow-scheduler dbt run --project-dir /opt/airflow/dbt_project`

3. **Explore your data** in Streamlit
   - Open http://localhost:8501
   - Navigate through Dashboard, Training Analysis, AI Coach pages

### Daily Automated Sync

The `garmin_to_duckdb` DAG runs daily at 6 AM (configurable in `airflow/dags/garmin_ingestion.py`).

### AI Coach

1. Go to **🤖 AI Coach** page in Streamlit
2. Enter your race goal (10K, Half Marathon, Marathon)
3. Enter your target time
4. Click "Generate Recommendations"
5. Receive personalized training advice based on your data

---

## 📸 Screenshots

_Coming soon: Dashboard screenshots, Airflow DAG graph, dbt lineage_

---

## 🔧 Development

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=. --cov-report=html tests/
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint
ruff check .

# Type check
mypy ingestion/ ai_engine/
```

### dbt Development

```bash
# Navigate to dbt project
cd dbt_project

# Run models
dbt run

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

### Accessing DuckDB

```bash
# Install DuckDB CLI
pip install duckdb

# Connect to database
duckdb data/duckdb/running_analytics.duckdb

# Query data
SELECT * FROM mart_training_analysis LIMIT 10;
```

---

## 🗺️ Roadmap

### Phase 1: MVP ✅ (Current)

- [x] Garmin API integration
- [x] Basic dbt models
- [x] Streamlit dashboard
- [x] Airflow orchestration
- [x] AI Coach (basic)

### Phase 2: Enhanced Analytics

- [ ] Strava integration
- [ ] Advanced ML models (injury prediction, performance forecasting)
- [ ] Race strategy planner
- [ ] Weather correlation analysis

### Phase 3: Multi-User & Cloud

- [ ] User authentication
- [ ] Cloud deployment (AWS/GCP)
- [ ] BigQuery/Snowflake migration option
- [ ] API for third-party integrations

### Phase 4: Advanced AI

- [ ] RAG for running knowledge base
- [ ] Computer vision for form analysis (video upload)
- [ ] Multi-agent system for comprehensive coaching

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 👤 About

**Author**: Jeremy Marchandeau  
**LinkedIn**: [Jeremy Marchandeau](https://linkedin.com/in/jeremymarchandeau)  
**Email**: hey@jeremymarchandeau.com

**Context**: This project was built as part of my transition from web development to data/AI engineering. It demonstrates proficiency in:

- Analytics Engineering (dbt, data modeling)
- Data Engineering (Airflow, API integration, DuckDB)
- AI Engineering (LLM integration, prompt engineering)
- Data Analytics (SQL, Python, visualization)

---

## 🙏 Acknowledgments

- [garminconnect](https://github.com/cyberjunky/python-garminconnect) for the Garmin API wrapper
- [dbt Labs](https://www.getdbt.com/) for the transformation framework
- [Anthropic](https://www.anthropic.com/) for Claude API
- Running community for inspiration

---

## 📊 Project Stats

![GitHub stars](https://img.shields.io/github/stars/yourusername/running-performance-analyzer?style=social)
![GitHub forks](https://img.shields.io/github/forks/yourusername/running-performance-analyzer?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/yourusername/running-performance-analyzer?style=social)

---

**Built with ❤️ for runners and data enthusiasts**
