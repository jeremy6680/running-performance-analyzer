# 📝 mart_race_performance - Quick Reference Card

## Essential Commands

```bash
# Run the model
cd dbt_project && dbt run --select mart_race_performance

# Run tests
dbt test --select mart_race_performance

# Query results (DuckDB)
duckdb data/duckdb/running_analytics.duckdb

# Set schema
SET schema 'main_gold';
```

---

## Key Metrics Available

### Race Details

- `race_id`, `race_date`, `race_year`, `race_season`
- `race_distance_category` (5K, 10K, Half, Marathon, Ultra)
- `distance_km`, `duration_minutes`, `finish_time_formatted`
- `pace_min_per_km`

### Performance Metrics

- `is_personal_record` (true/false)
- `pr_pace_min_per_km` - Current PR for this distance
- `minutes_off_pr` - How many minutes slower than PR
- `pct_off_pr` - Percentage slower than PR
- `performance_rating` (PR, Near PR, Good, Fair, Off Day)

### Training Context (30 days before race)

- `avg_training_pace_30d` - Average training pace
- `total_training_distance_30d` - Total kilometers trained
- `training_runs_30d` - Number of training runs
- `race_vs_training_pace_diff` - Race vs training pace (min/km)
- `race_readiness_score` (1-10)
- `pacing_assessment` - How you paced the race

### Recovery

- `days_since_last_race`
- `recovery_status` (First race, Quick turnaround, Standard, Well rested)

### Trends

- `pace_ma_3_races` - 3-race moving average pace
- `pace_change_vs_last_race` - Improvement vs last race

---

## Useful Queries

### All Personal Records

```sql
SELECT
    race_distance_category,
    race_date,
    finish_time_formatted,
    pace_min_per_km
FROM mart_race_performance
WHERE is_personal_record = true
ORDER BY race_distance_category;
```

### Race Calendar (Recent First)

```sql
SELECT
    race_date,
    race_distance_category,
    finish_time_formatted,
    performance_rating,
    days_since_last_race
FROM mart_race_performance
ORDER BY race_date DESC;
```

### Performance vs Readiness

```sql
SELECT
    race_date,
    race_readiness_score,
    total_training_distance_30d,
    performance_rating,
    pct_off_pr
FROM mart_race_performance
ORDER BY race_date DESC;
```

### 10K Progression

```sql
SELECT
    race_date,
    pace_min_per_km,
    pace_ma_3_races,
    is_personal_record,
    pct_off_pr
FROM mart_race_performance
WHERE race_distance_category = '10K'
ORDER BY race_date;
```

### Pacing Analysis

```sql
SELECT
    race_date,
    race_distance_category,
    avg_training_pace_30d,
    pace_min_per_km as race_pace,
    race_vs_training_pace_diff,
    pacing_assessment,
    performance_rating
FROM mart_race_performance
ORDER BY race_date DESC;
```

### Best Performances (Top 5)

```sql
SELECT
    race_date,
    race_distance_category,
    finish_time_formatted,
    pace_min_per_km,
    performance_rating
FROM mart_race_performance
ORDER BY pct_off_pr
LIMIT 5;
```

---

## SQL Patterns Used

### Window Function - Moving Average

```sql
avg(pace_min_per_km) over (
    partition by race_distance_category  -- Per distance
    order by race_date
    rows between 2 preceding and current row  -- 3 races total
)
```

### Self-Join - Training Context

```sql
from races r
left join activities t
    on t.date between r.date - interval '30 days' and r.date - interval '1 day'
    and t.is_race = false
```

### MIN Aggregation - Find PRs

```sql
select
    race_distance_category,
    min(duration_minutes) as pr_duration
group by race_distance_category
```

### LAG - Days Between Races

```sql
activity_date - lag(activity_date, 1) over (order by activity_date)
```

---

## Performance Classifications

### Performance Rating

- **PR**: Personal record
- **Near PR**: Within 5% of PR
- **Good**: Within 10% of PR
- **Fair**: Within 20% of PR
- **Off Day**: More than 20% off PR

### Pacing Assessment

- **Much faster than training**: < -1.0 min/km difference
- **Faster than training**: -0.5 to -1.0 difference
- **Consistent with training**: ±0.5 difference
- **Slower than training**: > +0.5 difference

### Recovery Status

- **First race**: No previous race
- **Quick turnaround**: < 7 days
- **Standard recovery**: 7-14 days
- **Well rested**: > 14 days

### Race Readiness Score

- **9-10**: 100+ km, 14+ days rest
- **7-8**: 60-100 km, 10+ days rest
- **5-6**: 40-60 km or short recovery
- **1-4**: Low volume or racing tired

---

## For Streamlit Dashboard

### PR Cards

```python
import duckdb
conn = duckdb.connect("data/duckdb/running_analytics.duckdb")

prs = conn.execute("""
    SELECT race_distance_category, finish_time_formatted, pace_min_per_km
    FROM main_gold.mart_race_performance
    WHERE is_personal_record = true
""").df()

for _, row in prs.iterrows():
    st.metric(
        label=f"{row['race_distance_category']} PR",
        value=row['finish_time_formatted']
    )
```

### Pace Progression Chart

```python
import plotly.express as px

races = conn.execute("SELECT * FROM main_gold.mart_race_performance").df()

fig = px.line(
    races,
    x='race_date',
    y='pace_min_per_km',
    color='race_distance_category',
    markers=True
)
st.plotly_chart(fig)
```

---

## Troubleshooting

### No Races Returned

```sql
-- Check if races are identified
SELECT count(*) FROM int_unified_activities WHERE is_race = true;
```

### PR Seems Wrong

```sql
-- Verify PR calculation
SELECT
    race_distance_category,
    min(duration_minutes),
    count(*)
FROM mart_race_performance
GROUP BY race_distance_category;
```

### Training Context is Null

```sql
-- Check training data exists
SELECT race_date, training_runs_30d, total_training_distance_30d
FROM mart_race_performance;
```

---

## Test Coverage

**33 tests total:**

- Data quality: 9 tests (unique, not_null)
- Range validation: 13 tests (accepted_range)
- Business logic: 11 tests (accepted_values)

Run tests:

```bash
dbt test --select mart_race_performance
```

---

## Files

```
dbt_project/models/marts/
├── mart_race_performance.sql         # Main SQL
└── schema_marts.yml                  # Tests + docs

docs/marts/
├── mart_race_performance_guide.md    # Full guide
└── mart_race_performance_quickref.md # This file
```

---

## Key Concepts

- **Grain**: One row per race
- **PR**: Fastest time for each distance category
- **Training Context**: 30 days before race
- **Window Functions**: Moving averages per distance
- **LAG**: Compare to previous race

---

## Remember

✅ PRs are tracked per distance (5K PR ≠ 10K PR)
✅ Training context = 30 days before race
✅ Race readiness based on volume + recovery
✅ Performance rating based on % off PR
✅ Partition by distance for fair comparisons

---

Need help? Check:

- Full guide: `docs/marts/mart_race_performance_guide.md`
- Schema file: `dbt_project/models/marts/schema_marts.yml`
- dbt docs: `dbt docs generate && dbt docs serve`
