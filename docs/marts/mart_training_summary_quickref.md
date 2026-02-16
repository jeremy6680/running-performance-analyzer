# 📝 mart_training_summary - Quick Reference Card

## Essential Commands

```bash
# Run the model
cd dbt_project && dbt run --select mart_training_summary

# Run tests
dbt test --select mart_training_summary

# See compiled SQL
dbt compile --select mart_training_summary
cat target/compiled/running_analytics/models/marts/mart_training_summary.sql

# Query results (DuckDB)
duckdb data/duckdb/running_analytics.duckdb

# Validate with Python
python scripts/validate_mart_training_summary.py
```

---

## Key Metrics Available

### Weekly Totals

- `total_activities` - Number of runs
- `total_distance_km` - Total distance
- `total_duration_minutes` - Total time running
- `avg_pace_min_per_km` - Average pace (distance-weighted)
- `avg_heart_rate_bpm` - Average HR
- `total_training_load` - Training stress

### Rolling Averages

- `rolling_4wk_avg_distance_km` - 4-week average distance
- `rolling_8wk_avg_distance_km` - 8-week average distance
- Same pattern for: activities, duration, training_load

### Comparisons

- `distance_vs_prev_week_pct` - % change vs last week
- `distance_vs_4wk_avg_pct` - % change vs 4-week average
- `distance_trend_4wk` - "Increasing", "Decreasing", "Stable"

### HR Zone Distribution (as %)

- `pct_zone1_easy` - Easy runs (<70% max HR)
- `pct_zone2_moderate` - Moderate (70-80%)
- `pct_zone3_tempo` - Tempo (80-87%)
- `pct_zone4_threshold` - Threshold (87-93%)
- `pct_zone5_max` - Max effort (>93%)

---

## Useful Queries

### Most Recent 5 Weeks

```sql
SELECT
    week_label,
    total_activities,
    total_distance_km,
    rolling_4wk_avg_distance_km,
    distance_vs_4wk_avg_pct,
    distance_trend_4wk
FROM mart_training_summary
ORDER BY week_start_date DESC
LIMIT 5;
```

### Peak Training Week

```sql
SELECT
    week_label,
    total_distance_km,
    total_training_load,
    total_activities
FROM mart_training_summary
ORDER BY total_distance_km DESC
LIMIT 1;
```

### Weeks Above 4-Week Average

```sql
SELECT
    week_label,
    total_distance_km,
    rolling_4wk_avg_distance_km,
    distance_vs_4wk_avg_pct
FROM mart_training_summary
WHERE total_distance_km > rolling_4wk_avg_distance_km
ORDER BY week_start_date DESC;
```

### HR Zone Distribution Trends

```sql
SELECT
    week_label,
    pct_zone1_easy,
    pct_zone2_moderate,
    pct_zone3_tempo,
    pct_zone4_threshold,
    pct_zone5_max
FROM mart_training_summary
ORDER BY week_start_date DESC
LIMIT 10;
```

### Training Load Progression

```sql
SELECT
    week_label,
    total_training_load,
    rolling_4wk_avg_training_load,
    training_load_trend_4wk
FROM mart_training_summary
ORDER BY week_start_date;
```

---

## SQL Patterns Used

### Window Function - Rolling Average

```sql
avg(metric) over (
    order by week_start_date
    rows between 3 preceding and current row
)
-- Returns average of current + 3 previous weeks (= 4 weeks total)
```

### Window Function - Previous Value

```sql
lag(metric, 1) over (order by week_start_date)
-- Returns metric from 1 week ago
```

### Percentage Change

```sql
round(
    case
        when old_value > 0
        then ((new_value - old_value) / old_value) * 100
        else null
    end,
    1
)
-- Formula: ((new - old) / old) * 100
```

### Distance-Weighted Average

```sql
sum(pace * distance) / nullif(sum(distance), 0)
-- Longer runs have more influence on average
```

---

## Test Coverage

**53 tests total** covering:

- Data quality (not_null, unique)
- Value ranges (min/max bounds)
- Business logic (valid values, relationships)

Run tests:

```bash
dbt test --select mart_training_summary
```

---

## Troubleshooting

### "No data returned"

➡️ Check if `int_unified_activities` has data:

```sql
SELECT count(*) FROM int_unified_activities;
```

### "Column not found"

➡️ Run intermediate model first:

```bash
dbt run --select int_unified_activities+
```

### "Tests failing"

➡️ Check which test failed:

```bash
dbt test --select mart_training_summary --store-failures
```

Then query `dbt_test_failures` schema for details.

### "Syntax error"

➡️ See compiled SQL to debug:

```bash
dbt compile --select mart_training_summary
cat target/compiled/.../mart_training_summary.sql
```

---

## For Streamlit Dashboard

**Load the data:**

```python
import duckdb
import streamlit as st

@st.cache_data
def load_training_summary():
    conn = duckdb.connect("data/duckdb/running_analytics.duckdb")
    return conn.execute("SELECT * FROM mart_training_summary ORDER BY week_start_date").df()

df = load_training_summary()
```

**Chart examples:**

```python
import plotly.express as px

# Weekly distance with rolling average
fig = px.line(df, x='week_start_date',
              y=['total_distance_km', 'rolling_4wk_avg_distance_km'])

# Training load trend
fig = px.bar(df, x='week_start_date', y='total_training_load',
             color='training_load_trend_4wk')

# HR zone distribution
fig = px.area(df, x='week_start_date',
              y=['pct_zone1_easy', 'pct_zone2_moderate', 'pct_zone3_tempo'])
```

---

## Next Marts to Create

1. **mart_race_performance** - Race-specific analysis
2. **mart_health_trends** - Sleep, HRV, recovery metrics
3. **mart_ai_features** - Features for AI coaching

---

## Files Created

```
dbt_project/models/marts/
├── mart_training_summary.sql      # Main logic
└── schema_marts.yml               # Tests + docs

scripts/
└── validate_mart_training_summary.py  # Validation script

docs/
└── mart_training_summary_guide.md     # Full guide
```

---

## Key Concepts

- **Grain**: One row per week (Monday to Sunday)
- **Rolling Average**: Smooths weekly noise to show trends
- **Window Function**: Calculates over rows without collapsing them
- **Marts**: Business-focused analytics tables (Gold layer)
- **Medallion Architecture**: Bronze (raw) → Silver (clean) → Gold (analytics)

---

## Remember

✅ Run tests after every change
✅ Check compiled SQL when debugging
✅ Validate output with spot-checks
✅ Document your logic (future-you will thank you!)

---

Need help? Check:

- Full guide: `docs/mart_training_summary_guide.md`
- dbt docs: `dbt docs generate && dbt docs serve`
- Schema file: `dbt_project/models/marts/schema_marts.yml`
