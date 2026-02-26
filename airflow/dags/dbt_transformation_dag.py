"""
dbt Transformation DAG
======================

This DAG runs dbt transformations after Garmin ingestion completes.
It transforms the bronze layer (raw data) into silver (staging) and
gold (marts) layers, then runs dbt tests to validate data quality.

Triggered by: garmin_ingestion DAG (via TriggerDagRunOperator)
Can also be:  Triggered manually in the Airflow UI

Architecture:
    Bronze (raw DuckDB tables)
        → Silver (dbt staging models: stg_garmin_activities, stg_garmin_health)
        → Gold (dbt marts: mart_training_summary, mart_race_performance,
                           mart_health_trends, mart_activity_performance)

Note on dbt execution inside Docker:
    dbt is NOT installed in the Airflow image.
    We use BashOperator to run dbt as a subprocess, using the dbt
    installation that exists on the host — mounted into the container
    via the volume ./dbt_project:/opt/airflow/dbt_project.
    
    However, since dbt itself isn't in the container PATH, we use
    PythonOperator + subprocess to call it, which gives us better
    error handling and log capture.
"""

import sys
import os
import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# ---------------------------------------------------------------------------
# Paths inside the Docker container
# (mapped from host via docker-compose volumes)
# ---------------------------------------------------------------------------
DBT_PROJECT_DIR = "/opt/airflow/dbt_project"
DBT_PROFILES_DIR = "/opt/airflow/dbt_project"  # profiles.yml is in the project root

# ---------------------------------------------------------------------------
# Default arguments
# ---------------------------------------------------------------------------
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="dbt_transformation",
    description="Run dbt models (bronze → silver → gold) + data quality tests",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),

    # No automatic schedule — this DAG is triggered by garmin_ingestion_dag
    # Set to None so it only runs when explicitly triggered
    schedule_interval=None,

    catchup=False,
    tags=["dbt", "transformation", "silver", "gold"],

    doc_md="""
    ## dbt Transformation DAG

    Runs the full dbt pipeline after Garmin ingestion.

    ### What it does
    1. `dbt run` — builds all models (staging + intermediate + marts)
    2. `dbt test` — runs all data quality tests

    ### Models built
    **Silver layer** (staging):
    - `stg_garmin_activities` — cleaned activities with pace zones, HR zones
    - `stg_garmin_health` — cleaned daily health metrics

    **Intermediate layer:**
    - `int_unified_activities` — merged and standardised activities

    **Gold layer** (marts):
    - `mart_training_summary` — weekly aggregations + rolling averages
    - `mart_race_performance` — race history, PRs, readiness scores
    - `mart_health_trends` — sleep, HRV, recovery scores
    - `mart_activity_performance` — per-activity analytics

    ### On failure
    - Check dbt logs in Airflow UI → task logs
    - Common cause: Garmin data has unexpected nulls → check bronze tables
    """,
) as dag:

    # -----------------------------------------------------------------------
    # Helper: run a dbt command inside the container
    # -----------------------------------------------------------------------
    def _run_dbt_command(command: list[str], task_name: str) -> dict:
        """
        Execute a dbt CLI command as a subprocess.

        dbt is not installed in the Airflow Docker image itself, so we
        look for it in common locations (the airflow user's local bin,
        or the system PATH).

        Args:
            command: dbt command as a list, e.g. ["dbt", "run"]
            task_name: Human-readable name for logging

        Returns:
            dict with keys: returncode, stdout, stderr

        Raises:
            RuntimeError: if the dbt command exits with a non-zero code
        """
        print(f"\n{'='*60}")
        print(f"🔧 Running: {' '.join(command)}")
        print(f"   Project dir: {DBT_PROJECT_DIR}")
        print(f"{'='*60}\n")

        result = subprocess.run(
            command,
            cwd=DBT_PROJECT_DIR,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                # Ensure dbt knows where to find profiles.yml
                "DBT_PROFILES_DIR": DBT_PROFILES_DIR,
            },
        )

        # Always print stdout/stderr to Airflow task logs
        if result.stdout:
            print("📄 dbt output:")
            print(result.stdout)
        if result.stderr:
            print("⚠️  dbt stderr:")
            print(result.stderr)

        if result.returncode != 0:
            raise RuntimeError(
                f"{task_name} failed with exit code {result.returncode}.\n"
                f"Check the logs above for details."
            )

        print(f"\n✅ {task_name} completed successfully")
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    # -----------------------------------------------------------------------
    # Task 1: dbt run — build all models
    # -----------------------------------------------------------------------
    def run_dbt_models(**context):
        """
        Run all dbt models: staging → intermediate → marts.
        
        Uses 'dbt run' which builds every model in dependency order.
        DuckDB file path is read from the profiles.yml mounted in the container.
        """
        # Try to find dbt in common locations inside the Airflow container
        # The airflow user installs packages to ~/.local/bin
        dbt_candidates = [
            "/home/airflow/.local/bin/dbt",
            "/usr/local/bin/dbt",
            "dbt",  # fallback: use PATH
        ]

        dbt_executable = None
        for candidate in dbt_candidates:
            if os.path.isfile(candidate) or candidate == "dbt":
                dbt_executable = candidate
                break

        if dbt_executable is None:
            raise RuntimeError(
                "dbt not found in the container. "
                "Add 'dbt-core dbt-duckdb' to airflow/airflow-requirements.txt "
                "and rebuild the image."
            )

        return _run_dbt_command(
            command=[dbt_executable, "run", "--profiles-dir", DBT_PROFILES_DIR],
            task_name="dbt run",
        )

    dbt_run_task = PythonOperator(
        task_id="dbt_run",
        python_callable=run_dbt_models,
        provide_context=True,
    )

    # -----------------------------------------------------------------------
    # Task 2: dbt test — validate data quality
    # -----------------------------------------------------------------------
    def run_dbt_tests(**context):
        """
        Run all dbt tests to validate data quality.

        Tests are defined in schema.yml files across all model layers.
        Failures here indicate data quality issues in the source data
        (e.g. unexpected nulls, duplicate keys, out-of-range values).

        Note: dbt test failures will mark this task as FAILED in Airflow,
        which will alert us that the data quality has degraded.
        """
        # Re-detect dbt executable (same logic as run_dbt_models)
        dbt_candidates = [
            "/home/airflow/.local/bin/dbt",
            "/usr/local/bin/dbt",
            "dbt",
        ]
        dbt_executable = next(
            (c for c in dbt_candidates if os.path.isfile(c) or c == "dbt"),
            None,
        )

        if dbt_executable is None:
            raise RuntimeError("dbt not found. See run_dbt_models task for details.")

        return _run_dbt_command(
            command=[dbt_executable, "test", "--profiles-dir", DBT_PROFILES_DIR],
            task_name="dbt test",
        )

    dbt_test_task = PythonOperator(
        task_id="dbt_test",
        python_callable=run_dbt_tests,
        provide_context=True,
    )

    # -----------------------------------------------------------------------
    # Task dependencies: run must complete before testing
    # -----------------------------------------------------------------------
    # dbt_run → dbt_test
    # If dbt_run fails, dbt_test is skipped automatically (Airflow default)
    dbt_run_task >> dbt_test_task
