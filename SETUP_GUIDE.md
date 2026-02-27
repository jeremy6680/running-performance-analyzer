# Developer Setup Guide — Running Performance Analyzer

This guide explains how to get the project running on a fresh machine.

---

## Prerequisites

| Tool                    | Version | Notes                                             |
| ----------------------- | ------- | ------------------------------------------------- |
| Python                  | 3.11.9  | Use pyenv — Python 3.12+ has dependency conflicts |
| Docker & Docker Compose | Latest  | Required for Airflow orchestration                |
| DuckDB CLI              | 1.4.x   | Optional, for direct DB inspection                |
| Git                     | Any     | —                                                 |

---

## 1. Clone & configure environment

```bash
git clone https://github.com/yourusername/running-performance-analyzer.git
cd running-performance-analyzer

# Copy and fill in credentials
cp .env.example .env
nano .env
```

Required values in `.env`:

```
GARMIN_EMAIL=your@email.com
GARMIN_PASSWORD=yourpassword
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 2. Python environments

This project uses **two separate virtual environments** to avoid a DuckDB <-> Streamlit Arrow serialisation conflict.

### Main environment (ingestion + dbt)

```bash
# Install Python 3.11.9 via pyenv if needed
pyenv install 3.11.9
pyenv local 3.11.9

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Streamlit environment

```bash
python -m venv venv_streamlit
source venv_streamlit/bin/activate
pip install -r streamlit_app/requirements.txt
```

> **Why two envs?** Streamlit 1.54+ conflicts with DuckDB 1.4.4 via PyArrow.
> The Streamlit env pins Streamlit at 1.45.0 to avoid this entirely.

---

## 3. Initial data sync

```bash
source venv/bin/activate

# Fetch last 90 days (recommended for first run — includes health history)
python -m ingestion.ingest_garmin --days 90

# Run dbt transformations
cd dbt_project
dbt run
dbt test
cd ..
```

For ongoing daily use, just fetch 7 days:

```bash
python -m ingestion.ingest_garmin --days 7
```

---

## 4. Launch the dashboard

```bash
source venv_streamlit/bin/activate
streamlit run "streamlit_app/0_Dashboard.py"
# Open http://localhost:8501
```

---

## 5. Airflow orchestration (optional)

Airflow automates daily ingestion + dbt runs. Requires Docker.

```bash
# Generate a Fernet key for Airflow
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add result to .env: AIRFLOW_FERNET_KEY=...

# Set your UID (Linux/Mac only)
echo "AIRFLOW_UID=$(id -u)" >> .env

# Start services
docker-compose up -d

# First run only — wait for "Airflow initialization complete!"
docker-compose logs -f airflow-init

# Access Airflow UI: http://localhost:8080
```

To stop:

```bash
docker-compose down       # stop, keep data
docker-compose down -v    # stop and wipe volumes
```

---

## 6. Explore the database directly

```bash
duckdb data/duckdb/running_analytics.duckdb
```

Useful queries:

```sql
SHOW TABLES;
SELECT * FROM mart_training_summary ORDER BY week_start_date DESC LIMIT 5;
SELECT race_date, race_distance_category, finish_time_formatted FROM mart_race_performance;
```

---

## 7. Run tests

```bash
source venv/bin/activate

# Python unit tests
pytest tests/

# dbt data quality tests
cd dbt_project && dbt test
```

---

## Troubleshooting

| Problem                             | Fix                                                      |
| ----------------------------------- | -------------------------------------------------------- |
| `ModuleNotFoundError` on dbt        | Make sure you are in `venv`, not `venv_streamlit`        |
| Streamlit Arrow serialisation error | Make sure you are in `venv_streamlit` (Streamlit 1.45.0) |
| Garmin login fails                  | Delete `ingestion/.garmin_session` and retry             |
| DuckDB locked                       | Close any other process holding the `.duckdb` file       |
| Docker port conflict on 8080        | Change `AIRFLOW_PORT` in `.env`                          |
