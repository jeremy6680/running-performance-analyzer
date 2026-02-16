# 🎯 mart_training_summary - Implementation Guide

## What We Just Built

You now have your first **gold layer mart** that transforms individual running activities into weekly training summaries with rolling averages and trend analysis.

---

## 📊 What This Mart Provides

### Weekly Aggregations

- **Volume metrics**: Total distance, duration, activities per week
- **Performance metrics**: Average pace, heart rate, elevation
- **Training load**: Weekly training stress accumulation
- **HR zones**: Distribution of effort across intensity zones

### Rolling Averages (Smoothed Trends)

- **4-week averages**: Short-term trends (1 month)
- **8-week averages**: Longer-term trends (2 months)
- Helps identify true training direction vs weekly noise

### Comparison Metrics

- **vs Previous Week**: Week-over-week change (%)
- **vs 4-Week Average**: Current vs recent trend (%)
- **Trend Indicators**: Simple "Increasing/Decreasing/Stable" flags

---

## 🗂️ Files Created

```
dbt_project/models/marts/
├── mart_training_summary.sql      # Main SQL logic
└── schema_marts.yml               # Documentation + tests
```

---

## 🔧 How to Run (On Your Local Machine)

### Step 1: Run the Model

```bash
cd dbt_project

# Run just this mart
dbt run --select mart_training_summary

# Or run all marts (when you create more)
dbt run --select marts
```

**Expected Output:**

```
Running with dbt=1.7.0
Found 1 model, 0 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 0 sources, 0 exposures, 0 metrics, 0 groups

Completed successfully

Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```

### Step 2: Run Tests

```bash
# Test this mart specifically
dbt test --select mart_training_summary

# Or test all marts
dbt test --select marts
```

**Expected Output:**

```
Running with dbt=1.7.0
Found 53 tests, 1 model, ...

✓ unique_mart_training_summary_week_start_date
✓ not_null_mart_training_summary_week_start_date
✓ accepted_range_mart_training_summary_total_activities
... (and many more)

Done. PASS=53 WARN=0 ERROR=0 SKIP=0 TOTAL=53
```

### Step 3: Query the Results

**Option A: DuckDB CLI**

```bash
duckdb data/duckdb/running_analytics.duckdb
```

```sql
-- See most recent 5 weeks
SELECT
    week_label,
    total_activities,
    total_distance_km,
    avg_pace_min_per_km,
    rolling_4wk_avg_distance_km,
    distance_vs_4wk_avg_pct
FROM mart_training_summary
ORDER BY week_start_date DESC
LIMIT 5;
```

**Option B: Python Script**

```bash
python scripts/validate_mart_training_summary.py
```

---

## 📖 Understanding the SQL Logic

Let me walk you through the 4 main CTEs in the SQL:

### 1. `weeks_spine` - Create Week Dimension

```sql
with weeks_spine as (
    select distinct
        date_trunc('week', activity_date) as week_start_date,
        extract(year from ...) as year,
        extract(week from ...) as week_number
    from int_unified_activities
)
```

**What it does:** Creates one row per week that has at least one activity.

- Uses `date_trunc('week', ...)` to get Monday of each week (ISO 8601 standard)
- Extracts year and week number for labeling

### 2. `weekly_aggregates` - Sum Up Each Week

```sql
weekly_aggregates as (
    select
        date_trunc('week', activity_date) as week_start_date,
        count(*) as total_activities,
        sum(distance_km) as total_distance_km,
        avg(pace_min_per_km) as avg_pace_min_per_km,
        -- ... many more metrics
    from int_unified_activities
    group by 1
)
```

**What it does:** Groups all activities by week and calculates totals/averages.

- **Count**: How many runs?
- **Sum**: Total distance, duration, elevation
- **Average**: Pace, heart rate, effort level
- **Distribution**: % of activities in each HR zone

### 3. `rolling_metrics` - Calculate Moving Averages

```sql
rolling_metrics as (
    select
        week_start_date,
        total_distance_km,
        -- 4-week rolling average
        avg(total_distance_km) over (
            order by week_start_date
            rows between 3 preceding and current row
        ) as rolling_4wk_avg_distance_km,
        -- Previous week for comparison
        lag(total_distance_km, 1) over (
            order by week_start_date
        ) as prev_week_distance_km
    from weekly_aggregates
)
```

**What it does:** Uses window functions to calculate:

- **Rolling averages**: Average of current + previous N weeks
  - `rows between 3 preceding and current row` = 4 weeks total
  - Smooths out weekly variations to show true trend
- **Lag**: Previous week's value for week-over-week comparison

**Why rolling averages?**

- Individual weeks are noisy (rest weeks, race weeks, injury)
- Rolling averages show true training direction
- 4-week = short-term trend, 8-week = longer-term trend

### 4. `final` - Calculate Percentages & Format

```sql
final as (
    select
        week_start_date,
        total_distance_km,
        rolling_4wk_avg_distance_km,
        -- Calculate percentage change
        round(
            case
                when prev_week_distance_km > 0
                then ((total_distance_km - prev_week_distance_km) / prev_week_distance_km) * 100
                else null
            end,
            1
        ) as distance_vs_prev_week_pct
    from rolling_metrics
)
```

**What it does:** Final calculations and formatting:

- **Percentage changes**: (new - old) / old \* 100
- **Trend indicators**: Simple string flags ("Increasing" if current > average)
- **Rounding**: Make numbers readable (2 decimals for km, 0 for counts)

---

## 🎓 Key SQL Concepts Used

### Window Functions

```sql
avg(distance) over (
    order by week
    rows between 3 preceding and current row
)
```

- Calculates over a "window" of rows
- Doesn't collapse rows like GROUP BY
- Perfect for running totals, moving averages, rankings

### LAG Function

```sql
lag(distance, 1) over (order by week)
```

- Gets value from N rows back
- Used for week-over-week comparisons
- Returns NULL for first row (no previous week)

### CASE Expressions

```sql
case
    when condition1 then value1
    when condition2 then value2
    else default_value
end
```

- SQL's version of if/else
- Used for conditional logic (percentage changes, trend classification)

### CTEs (WITH clauses)

```sql
with step1 as (
    select ...
),
step2 as (
    select ... from step1
)
select * from step2
```

- Break complex query into readable steps
- Like creating temporary views
- Each CTE can reference previous ones

---

## 📊 Sample Output

After running the model, you'll get data like this:

```
week_start_date | week_label   | total_activities | total_distance_km | rolling_4wk_avg_distance_km | distance_vs_4wk_avg_pct
----------------|--------------|------------------|-------------------|-----------------------------|-----------------------
2026-02-10      | Week 7, 2026 | 3                | 15.5              | 18.2                        | -14.8
2026-02-03      | Week 6, 2026 | 4                | 22.1              | 19.5                        | 13.3
2026-01-27      | Week 5, 2026 | 2                | 12.3              | 17.8                        | -30.9
```

**Reading this:**

- Week 7: Ran 15.5 km (3 activities)
- 4-week average: 18.2 km
- Currently 14.8% below average → Might be a recovery week

---

## 🧪 Testing Strategy

The `schema_marts.yml` includes comprehensive tests:

### Data Quality Tests

- **not_null**: Critical columns must have values
- **unique**: week_start_date must be unique (one row per week)
- **accepted_range**: Values within realistic bounds
  - Distance: 0-300 km/week (marathon training max ~80-100 km)
  - Pace: 3-15 min/km (world record ~2:30, slow jog ~7:00)
  - Heart rate: 100-220 bpm (physiological limits)

### Business Logic Tests

- **accepted_values**: Trend indicators only have valid values
- Total races ≤ total activities (races are subset)
- Rolling averages within reasonable bounds

### Why These Ranges?

- **300 km/week**: Elite ultra-marathoners might hit 150-200 km
- **15 min/km pace**: Very slow recovery run
- **220 bpm max HR**: Age-dependent, but 220 - age is rough max

---

## 🚀 Next Steps

### Immediate (This Session)

1. **On your local machine**, run:

   ```bash
   cd dbt_project
   dbt run --select mart_training_summary
   dbt test --select mart_training_summary
   ```

2. **Validate the output:**

   ```bash
   python scripts/validate_mart_training_summary.py
   ```

3. **Query the results:**
   ```bash
   duckdb data/duckdb/running_analytics.duckdb
   ```
   ```sql
   SELECT * FROM mart_training_summary ORDER BY week_start_date DESC LIMIT 5;
   ```

### Create More Marts (Next Session)

Now that you understand the pattern, create:

1. **`mart_race_performance.sql`**
   - Filter for races only (`where is_race = true`)
   - Calculate PRs (personal records) per distance
   - Race pace trends over time
   - Compare race pace to training pace

2. **`mart_health_trends.sql`**
   - Join activities with daily health data
   - Sleep quality trends (rolling averages)
   - HRV evolution
   - Resting heart rate trends
   - Correlate health metrics with performance

3. **`mart_ai_features.sql`**
   - Aggregate features for AI/ML models
   - Training readiness score
   - Injury risk indicators (rapid load increases)
   - Performance predictions
   - Context for LLM prompts

### Build Streamlit Dashboard (Phase 3)

Use this mart for visualizations:

- Line chart: Weekly distance with rolling averages
- Bar chart: Weekly activities
- Scatter plot: Distance vs training load
- Heatmap: HR zone distribution over time

---

## 💡 Pro Tips

### Debugging dbt Models

**See compiled SQL:**

```bash
dbt compile --select mart_training_summary
cat target/compiled/running_analytics/models/marts/mart_training_summary.sql
```

**See what dbt will run:**

```bash
dbt run --select mart_training_summary --dry-run
```

**Run in development (doesn't overwrite prod):**

```bash
dbt run --select mart_training_summary --target dev
```

### Performance Optimization

**If your mart gets slow with lots of data:**

1. Add indexes in DuckDB:

   ```sql
   CREATE INDEX idx_week ON mart_training_summary(week_start_date);
   ```

2. Make it incremental (only process new weeks):

   ```sql
   {{ config(materialized='incremental') }}

   {% if is_incremental() %}
   where week_start_date > (select max(week_start_date) from {{ this }})
   {% endif %}
   ```

3. Partition by year (for massive datasets):
   ```sql
   {{ config(
       materialized='table',
       partition_by='year'
   ) }}
   ```

### Data Validation

**Before trusting your mart:**

1. Compare counts to source:

   ```sql
   -- Should match total unique weeks
   SELECT count(distinct date_trunc('week', activity_date))
   FROM int_unified_activities;
   ```

2. Spot-check calculations manually:

   ```sql
   -- Verify one week
   SELECT sum(distance_km)
   FROM int_unified_activities
   WHERE date_trunc('week', activity_date) = '2026-02-10';
   ```

3. Check for nulls where unexpected:
   ```sql
   SELECT * FROM mart_training_summary WHERE total_activities IS NULL;
   ```

---

## 🎯 Key Takeaways

1. **Marts are business-focused**: Not just technical aggregations, but answering real questions ("How's my training volume trending?")

2. **Rolling averages smooth noise**: Weekly data is volatile, rolling averages reveal true trends

3. **Window functions are powerful**: Calculate metrics without losing row-level detail

4. **Testing is critical**: Comprehensive tests catch data quality issues early

5. **Documentation matters**: Schema files help future-you understand what you built

---

## 📚 Further Reading

- [dbt Window Functions Guide](https://docs.getdbt.com/guides/best-practices/how-we-style/3-how-we-style-our-sql#window-functions)
- [Kimball Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
- [Analytics Engineering Handbook](https://www.getdbt.com/analytics-engineering/)

---

## ❓ Common Questions

**Q: Why use rolling averages instead of just weekly totals?**
A: Individual weeks have noise (recovery weeks, race weeks, illness). Rolling averages show true training direction. Example: Week 1: 30km, Week 2: 10km (recovery), Week 3: 30km. Without rolling average, looks volatile. With 4-week average: steady ~23 km/week.

**Q: Why 4-week and 8-week specifically?**
A: 4 weeks = monthly trend (short-term adjustments), 8 weeks = bi-monthly (longer-term progression). Common in periodized training programs.

**Q: Why distance-weighted pace average?**
A: If you run 1 km at 4:00 min/km and 10 km at 5:00 min/km, your average pace should be closer to 5:00 (you spent more time/distance at that pace). Simple average would be 4:30, which misrepresents your actual effort.

**Q: What if I have gaps in my training (weeks with 0 activities)?**
A: Current model only creates rows for weeks with activities. To include empty weeks, you'd need to generate a complete calendar spine and LEFT JOIN to it.

---

**Great work completing your first mart! This is the foundation for all your analytics.** 🎉

When you're ready, let's create `mart_race_performance` next! 🏃‍♂️
