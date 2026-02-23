# Known Issues

Known bugs, unresolved behaviors, and points to monitor. Investigated once — do not re-debug from scratch.

---

## Streamlit / DuckDB

### `@st.cache_data` causes Arrow serialization errors
**Symptom**: `RuntimeError: field id: 100` when Streamlit tries to cache a DataFrame returned by DuckDB 1.4.x.
**Root cause**: DuckDB's result objects are not fully compatible with Streamlit's Arrow-based serialization layer.
**Workaround**: All DataFrames are stored in `st.session_state` instead. Do not reintroduce `@st.cache_data` on functions that return DuckDB results until the upstream compatibility issue is resolved.
**Status**: Active workaround in place. Monitor DuckDB / Streamlit release notes for a fix.

---

### Date column type inconsistency
**Symptom**: Filters or comparisons involving date columns fail silently or raise `TypeError: can't compare datetime.date to Timestamp`.
**Root cause**: DuckDB `DATE` columns can arrive as `datetime.date`, `str`, or `pandas.Timestamp` depending on query path and driver version. Streamlit widgets return `datetime.date`. Mixing the two causes type errors.
**Workaround**: `_normalize_dates(df)` in `streamlit_app/utils/database.py` casts all known date columns to `datetime.date` after every query. The list of date columns is maintained in `_DATE_COLUMNS`.
**Status**: Active workaround. If you add a new date column to a mart, add it to `_DATE_COLUMNS` or date comparisons in the UI will break.

---

## Data Ingestion

### Health data history limited to ~February 2026
**Symptom**: `mart_health_trends` and related charts only show data from around February 2026, even though the Garmin account is older.
**Root cause**: Initial sync was run with the default `INITIAL_SYNC_DAYS` window, which did not reach further back.
**Fix**: Run `python -m ingestion.ingest_garmin --days 365` (or larger) to back-fill. Adjust `INITIAL_SYNC_DAYS` in `.env` before the next full sync.
**Status**: Data gap exists in production. Not a bug in the code — data was simply never fetched.

---

### Garmin session token expiry
**Symptom**: Ingestion fails with an authentication error on the first run after a period of inactivity, despite a session file existing.
**Root cause**: The Garmin Connect session serialized in `data/garmin_session.json` has a finite TTL. After expiry the connector attempts to reload the session and gets a 401.
**Workaround**: The connector catches the auth error and falls back to a fresh login using `GARMIN_EMAIL` / `GARMIN_PASSWORD`. If this also fails (e.g. account lockout after too many attempts), delete `data/garmin_session.json` and retry.
**Status**: Handled gracefully. Monitor if Garmin tightens rate-limiting policies.

---

### Weather back-fill may leave NULL weather columns indefinitely
**Symptom**: Some activities in `raw_garmin_activities` permanently have `NULL` weather columns even after re-running ingestion.
**Root cause**: Garmin's weather endpoint does not return data for all activities (e.g., indoor activities, very old activities, or activities in locations without weather coverage).
**Status**: Expected behavior. `weather_temp_c IS NULL` is a valid state — do not treat it as an error. The staging model handles NULLs with COALESCE.

---

## dbt Transformations

### Non-standard race distances produce NULL `race_distance_category`
**Symptom**: Races at 15K, 8K, trail distances, or other non-standard lengths appear in `mart_race_performance` with `race_distance_category = NULL`.
**Root cause**: The categorization logic uses fixed distance bands (5K: 4.8–5.2 km, 10K: 9.8–10.3 km, HM: 20.9–21.4 km, Marathon: 41.9–43.0 km, Ultra: >43 km). Distances outside these bands fall through to NULL.
**Workaround**: These activities still appear in the mart and can be queried; they just won't show up in distance-filtered views.
**Status**: Known limitation. Extend the CASE WHEN bands in `stg_garmin_activities.sql` if you need to categorize additional distances.

---

### Rolling averages require sufficient history
**Symptom**: `rolling_4wk_avg_distance_km` and `rolling_4wk_avg_training_load` show lower-than-expected values for the first few weeks in the dataset.
**Root cause**: DuckDB window functions with `ROWS BETWEEN 3 PRECEDING AND CURRENT ROW` compute over whatever rows are available; if fewer than 4 weeks exist, the average is computed over the available weeks only (not NULL-padded).
**Status**: Expected DuckDB behavior. Values are mathematically correct but represent a shorter window than labelled during the ramp-up period.

---

### TRIMP training load is an approximation
**Symptom**: `total_training_load` values in `mart_training_summary` do not exactly match the "Training Load" shown in Garmin Connect.
**Root cause**: The official Garmin training load formula is proprietary. The project uses a TRIMP-based approximation: `duration_minutes * avg_hr * hr_intensity_factor`. The formula is close but not identical.
**Status**: Known approximation. Useful for relative comparisons (week-over-week, trend analysis) but do not use it to quote exact Garmin figures.

---

## AI Coach

### `_col_mean()` silently returns `None` on object-dtype columns
**Symptom**: Coach context fields like `avg_hrv` show as `None` in the prompt even when HRV data exists in the database.
**Root cause**: If a numeric column was loaded as `object` dtype (common with DuckDB mixed-type columns), `pd.Series.mean()` returns `NaN` which is then normalized to `None`.
**Workaround**: `_col_mean()` in `llm_analyzer.py` wraps the column with `pd.to_numeric(..., errors='coerce')` before computing the mean. If a field reads as `None` in the prompt, verify the column dtype in the source DataFrame.
**Status**: Workaround in place. Add `pd.to_numeric` coercion for any new numeric column added to the coaching context.

---

### HRV numeric extraction depends on Garmin's status string
**Symptom**: `hrv_numeric` in `mart_health_trends` can be NULL even on days where HRV was measured.
**Root cause**: The HRV numeric value is extracted from Garmin's `hrv_status` string. If Garmin changes the format of this field (e.g., new status categories), the extraction logic in `stg_garmin_health.sql` will produce NULLs.
**Status**: Monitor after Garmin app updates. The raw `hrv_avg` value is still stored in `raw_garmin_daily_health` as a fallback.

---

## Infrastructure

### Airflow DAGs not yet implemented
**Symptom**: The `airflow/dags/` directory is empty. `docker-compose.yml` defines an Airflow service but no DAGs are deployed.
**Root cause**: Airflow orchestration is Phase 5 of the roadmap and has not been built yet.
**Status**: Infrastructure placeholder only. Ingestion currently runs manually via `python -m ingestion.ingest_garmin`. See `NEXT_STEPS.md` for the Phase 5 plan.

---

## Column Name Gotchas (reference)

These have caused bugs before. Keep this list handy when writing new queries or Streamlit code.

| What you might write | What it actually is | Location |
|---------------------|--------------------|----|
| `average_pace_min_per_km` | `avg_pace_min_per_km` | `mart_training_summary` |
| `average_pace_min_per_km` | `pace_min_per_km` | `mart_race_performance` |
| `health_date` | `date` | `mart_health_trends` |
| `hrv_avg` (raw) | `hrv_numeric` (transformed) | `mart_health_trends` |
| `week_date` | `week_start_date` | `mart_training_summary` |
