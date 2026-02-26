"""
Garmin Ingestion DAG
====================

This DAG fetches the last 7 days of data from Garmin Connect API
and loads it into the DuckDB bronze layer (raw_garmin_activities,
raw_garmin_daily_health, raw_garmin_calendar_events).

Schedule: Every day at 6:00 AM (Europe/Paris timezone)
Trigger:  Also triggers dbt_transformation_dag on success

Architecture note:
    This DAG runs INSIDE the Airflow Docker container.
    The ingestion Python modules are mounted at /opt/airflow/modules/
    and added to sys.path so they can be imported normally.

Usage:
    - Automatic: runs daily at 6 AM
    - Manual: click "Trigger DAG" in the Airflow UI
    - Backfill: use the Airflow CLI (airflow dags backfill)
"""

import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# ---------------------------------------------------------------------------
# Add our custom modules to Python path so they can be imported in tasks.
# The ingestion/ and ai_engine/ folders are mounted at /opt/airflow/modules/
# via docker-compose volumes.
# ---------------------------------------------------------------------------
MODULES_PATH = "/opt/airflow/modules"
if MODULES_PATH not in sys.path:
    sys.path.insert(0, MODULES_PATH)

# ---------------------------------------------------------------------------
# Default arguments applied to every task in this DAG
# ---------------------------------------------------------------------------
default_args = {
    # DAG owner (displayed in Airflow UI)
    "owner": "airflow",

    # Don't run missed schedules if Airflow was down
    "depends_on_past": False,

    # Send email on failure (requires SMTP config — disabled for now)
    "email_on_failure": False,
    "email_on_retry": False,

    # Retry once after 5 minutes if a task fails
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="garmin_ingestion",
    description="Fetch last 7 days from Garmin Connect → DuckDB bronze layer",
    default_args=default_args,

    # First run: yesterday (so it runs immediately on first deployment)
    start_date=datetime(2026, 1, 1),

    # Run every day at 6 AM Paris time
    # Cron syntax: minute hour day month weekday
    schedule_interval="0 6 * * *",

    # Timezone for the schedule (matches AIRFLOW__CORE__DEFAULT_TIMEZONE in docker-compose)
    # Note: Airflow stores all times in UTC internally; this is just for display
    # and schedule interpretation.

    # Don't run all missed runs since start_date when first deployed
    catchup=False,

    # Tags help filter DAGs in the UI
    tags=["garmin", "ingestion", "bronze"],

    # Useful metadata shown in the UI
    doc_md="""
    ## Garmin Ingestion DAG

    Fetches the **last 7 days** of Garmin Connect data and loads it into DuckDB.

    ### What it does
    1. Logs into Garmin Connect API (uses credentials from .env)
    2. Fetches activities (runs, workouts) with all metrics
    3. Fetches daily health data (steps, sleep, HRV, stress, body battery)
    4. Fetches calendar race events (upcoming races)
    5. Upserts everything into DuckDB bronze layer tables
    6. Triggers the dbt transformation DAG on success

    ### Tables written
    - `main_bronze.raw_garmin_activities`
    - `main_bronze.raw_garmin_daily_health`
    - `main_bronze.raw_garmin_calendar_events`

    ### On failure
    - Retries once after 5 minutes
    - Check logs in Airflow UI → Browse → Task Instances
    """,
) as dag:

    # -----------------------------------------------------------------------
    # Task 1: Fetch data from Garmin and load into DuckDB
    # -----------------------------------------------------------------------
    def run_garmin_ingestion(**context):
        """
        Main ingestion task.

        Imports and calls ingest_garmin_data() from our ingestion module.
        Uses XCom to push stats so downstream tasks can read them.

        Args:
            context: Airflow context dict (injected automatically by provide_context)
        
        Returns:
            dict: Ingestion statistics (activities_count, health_count, etc.)
        """
        # Import here (inside the task function) so Airflow doesn't try to
        # import at DAG-parse time, before sys.path is configured.
        from ingestion.ingest_garmin import ingest_garmin_data

        # Run the ingestion for the last 7 days
        # Using upsert mode: insert new records, skip duplicates
        stats = ingest_garmin_data(days=7, mode="upsert")

        # Log summary to Airflow task logs
        print(f"✅ Ingestion complete:")
        print(f"   Activities loaded:  {stats['activities_count']}")
        print(f"   Health records:     {stats['health_count']}")
        print(f"   Calendar events:    {stats.get('calendar_count', 0)}")
        print(f"   Duration:           {stats.get('duration_seconds', 0):.1f}s")

        # Return stats — Airflow automatically pushes the return value to XCom
        # so downstream tasks can access it via context['ti'].xcom_pull(...)
        return stats

    ingest_task = PythonOperator(
        task_id="fetch_garmin_data",
        python_callable=run_garmin_ingestion,
        # provide_context=True is the default in Airflow 2.x (kept for clarity)
        provide_context=True,
    )

    # -----------------------------------------------------------------------
    # Task 2: Trigger the dbt transformation DAG on success
    # -----------------------------------------------------------------------
    # TriggerDagRunOperator kicks off another DAG when this task runs.
    # The dbt DAG will run AFTER this ingestion completes successfully.
    # If ingestion fails, dbt will NOT be triggered (correct behaviour —
    # we don't want to transform incomplete data).
    trigger_dbt = TriggerDagRunOperator(
        task_id="trigger_dbt_transformations",
        trigger_dag_id="dbt_transformation",  # Must match dag_id in the dbt DAG
        wait_for_completion=False,  # Don't block — let dbt run independently
        reset_dag_run=True,         # Allow re-triggering if dbt DAG already ran today
    )

    # -----------------------------------------------------------------------
    # Task dependencies: ingestion must succeed before triggering dbt
    # -----------------------------------------------------------------------
    ingest_task >> trigger_dbt
