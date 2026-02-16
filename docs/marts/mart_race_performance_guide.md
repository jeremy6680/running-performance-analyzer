# 🏃 mart_race_performance - Implementation Guide

## What This Mart Provides

Race-specific performance analysis with PR tracking, training context, and performance trends.

---

## 📊 Key Features

### PR Tracking

- **Personal Records**: Fastest time for each distance (5K, 10K, Half, Marathon)
- **Time Off PR**: How many minutes slower than your best
- **PR Progression**: Track when PRs are set

### Performance Analysis

- **Performance Rating**: PR, Near PR, Good, Fair, Off Day
- **Race vs Training Pace**: Compare race execution to training
- **Pacing Assessment**: Did you race faster/slower than training?

### Training Context

- **30-Day Window**: Training volume before each race
- **Race Readiness Score**: 1-10 based on training & recovery
- **Training Runs**: Count of quality sessions before race

### Recovery Tracking

- **Days Between Races**: Track recovery periods
- **Recovery Status**: First race, Quick turnaround, Standard, Well rested
- **Race Frequency**: Races per month/season

### Performance Trends

- **3-Race Moving Average**: Smoothed pace trends
- **Pace Improvement**: Getting faster or slower?
- **Season Performance**: Compare across quarters

---

## 🗂️ Files Created

```
dbt_project/models/marts/
├── mart_race_performance.sql          # Main SQL logic
└── schema_marts.yml                   # Tests + documentation (race section)
```

---

## 🔧 How to Run

```bash
cd dbt_project

# Run just this mart
dbt run --select mart_race_performance

# Run tests
dbt test --select mart_race_performance

# Run with dependencies (staging + intermediate)
dbt run --select +mart_race_performance
```

---

## 📖 Understanding the SQL Logic

### Step 1: Filter for Races & Add Context

```sql
with races_base as (
    select
        activity_id,
        activity_date,
        distance_km,
        duration_minutes,
        avg_pace_min_km as pace_min_per_km,
        race_distance_category,

        -- Season classification
        case
            when extract(month from activity_date) in (1, 2, 12) then 'Winter'
            when extract(month from activity_date) in (3, 4, 5) then 'Spring'
            -- ...
        end as race_season

    from int_unified_activities
    where is_race = true
)
```

**What it does:**

- Filters for races only (`is_race = true`)
- Adds temporal context (year, month, quarter, season)
- Renames columns for consistency

### Step 2: Calculate Race Intervals

```sql
race_intervals as (
    select
        *,
        -- Days since last race
        activity_date - lag(activity_date, 1) over (order by activity_date) as days_since_last_race,

        -- Race number (chronological)
        row_number() over (order by activity_date) as race_number

    from races_base
)
```

**What it does:**

- Uses LAG to get previous race date
- Calculates days between races
- Numbers races chronologically

### Step 3: Find Personal Records (PRs)

```sql
personal_records as (
    select
        race_distance_category,
        min(duration_minutes) as pr_duration_minutes,
        min(pace_min_per_km) as pr_pace_min_per_km
    from race_intervals
    where race_distance_category is not null
    group by race_distance_category
)
```

**What it does:**

- Groups by distance (5K, 10K, Half, Marathon)
- Finds fastest time (`min(duration)`) for each distance
- Stores as PR benchmarks

**Why this matters:**
Every race is compared to the PR to determine performance quality.

### Step 4: Training Context (30 Days Before Race)

```sql
training_context as (
    select
        r.activity_id,

        -- Average training pace in 30 days before race
        avg(t.avg_pace_min_km) as avg_training_pace_30d,

        -- Training volume
        sum(t.distance_km) as total_training_distance_30d,
        count(*) as training_runs_30d

    from race_intervals r
    left join int_unified_activities t
        on t.activity_date between (r.activity_date - interval '30 days')
                                and (r.activity_date - interval '1 day')
        and t.is_race = false
    group by r.activity_id
)
```

**What it does:**

- For each race, looks at 30 days before
- Calculates average training pace
- Sums total training volume
- Counts number of runs

**Why 30 days?**
Recent training (last month) is most predictive of race performance.

### Step 5: Calculate Performance Metrics

```sql
race_metrics as (
    select
        ri.*,
        pr.pr_duration_minutes,
        tc.avg_training_pace_30d,

        -- Is this a PR?
        case
            when ri.duration_minutes = pr.pr_duration_minutes then true
            else false
        end as is_personal_record,

        -- Time off PR
        ri.duration_minutes - pr.pr_duration_minutes as minutes_off_pr,

        -- Percentage off PR
        round(((ri.duration_minutes - pr.pr_duration_minutes) / pr.pr_duration_minutes) * 100, 1)
            as pct_off_pr,

        -- Race vs training pace
        round(ri.pace_min_per_km - tc.avg_training_pace_30d, 2)
            as race_vs_training_pace_diff,

        -- Race readiness score (1-10)
        case
            when tc.total_training_distance_30d >= 100 and days_since_last_race >= 14 then 9
            when tc.total_training_distance_30d >= 80 and days_since_last_race >= 10 then 8
            -- ...
            else 5
        end as race_readiness_score

    from race_intervals ri
    left join personal_records pr on ri.race_distance_category = pr.race_distance_category
    left join training_context tc on ri.activity_id = tc.activity_id
)
```

**Key Calculations:**

**Is PR?**

```sql
duration_minutes = pr_duration_minutes  -- Exact match with fastest time
```

**% Off PR:**

```sql
((current_time - pr_time) / pr_time) * 100
-- Example: 55 min vs 50 min PR = ((55-50)/50)*100 = 10% off
```

**Race vs Training Pace:**

```sql
race_pace - avg_training_pace
-- Negative = raced faster than training (good execution)
-- Positive = raced slower than training (conservative or struggled)
```

**Race Readiness Score:**

- **9-10**: 100+ km training, 14+ days rest
- **7-8**: 60-100 km training, 10+ days rest
- **5-6**: 40-60 km training or short recovery
- **1-4**: Very low volume or racing on tired legs

### Step 6: Performance Trends

```sql
performance_trends as (
    select
        *,
        -- 3-race moving average
        avg(pace_min_per_km) over (
            partition by race_distance_category
            order by activity_date
            rows between 2 preceding and current row
        ) as pace_ma_3_races,

        -- Change vs last race
        pace_min_per_km - lag(pace_min_per_km, 1) over (
            partition by race_distance_category
            order by activity_date
        ) as pace_change_vs_last

    from race_metrics
)
```

**What it does:**

- **3-Race MA**: Smooths out one-off performances to show true trend
- **Pace Change**: Compare to previous race at same distance
- **Partitioned by distance**: Only compare apples to apples

**Example:**

```
10K Races:
- Race 1: 5:00 min/km
- Race 2: 4:50 min/km (↓ 0:10 faster - improving!)
- Race 3: 4:55 min/km (↑ 0:05 slower - still okay)
- 3-race MA: 4:55 min/km (smoothed trend)
```

### Step 7: Final Classifications

```sql
-- Performance rating
case
    when is_personal_record then 'PR'
    when pct_off_pr <= 5 then 'Near PR'
    when pct_off_pr <= 10 then 'Good'
    when pct_off_pr <= 20 then 'Fair'
    else 'Off Day'
end as performance_rating

-- Pacing assessment
case
    when race_vs_training_pace_diff < -1.0 then 'Much faster than training'
    when race_vs_training_pace_diff < -0.5 then 'Faster than training'
    when race_vs_training_pace_diff between -0.5 and 0.5 then 'Consistent with training'
    when race_vs_training_pace_diff > 0.5 then 'Slower than training'
    else 'No training data'
end as pacing_assessment

-- Recovery status
case
    when days_since_last_race is null then 'First race'
    when days_since_last_race < 7 then 'Quick turnaround'
    when days_since_last_race between 7 and 14 then 'Standard recovery'
    when days_since_last_race > 14 then 'Well rested'
end as recovery_status
```

---

## 🎓 Key SQL Concepts Used

### Window Functions with PARTITION BY

```sql
-- Moving average for EACH distance separately
avg(pace) over (
    partition by race_distance_category  -- Separate calcs per distance
    order by date
    rows between 2 preceding and current row
)
```

**Why partition?**
You don't want to compare 5K paces to Marathon paces!

### Self-Joins for Context

```sql
-- Join race to its own training runs
from races r
left join activities t
    on t.date between r.date - 30 days and r.date - 1 day
    and t.is_race = false
```

### MIN Aggregation for PRs

```sql
-- Find fastest time per distance
select
    distance_category,
    min(duration) as pr
group by distance_category
```

---

## 📊 Sample Output

```
race_date  | distance | finish_time | pace  | is_pr | performance | pacing         | readiness
-----------|----------|-------------|-------|-------|-------------|----------------|----------
2026-02-11 | 10K      | 54:00       | 5:24  | No    | Good        | No train data  | 5
2026-02-08 | 10K      | 50:00       | 5:00  | YES   | PR          | No train data  | 5
```

**Reading this:**

- **Race 1 (Feb 8)**: Set a PR at 50 minutes (5:00/km pace)
- **Race 2 (Feb 11)**: 54 minutes - only 4 min off PR (8% slower) = "Good"
- **Recovery**: Only 3 days between races = "Quick turnaround"
- **Readiness**: Score of 5 (neutral - no training data available)

---

## 🧪 Testing Strategy

### 33 Comprehensive Tests

**Data Quality (8 tests)**

- `unique(race_id)` - No duplicate races
- `not_null` on critical fields

**Range Validation (14 tests)**

- Distance: 3-100 km (reasonable race distances)
- Duration: 10-600 minutes (20 min to 10 hours)
- Pace: 3-10 min/km (elite to recreational)
- Readiness: 1-10 (score range)

**Business Logic (11 tests)**

- Performance ratings: Only valid categories
- Pacing assessments: Only valid classifications
- Recovery status: Only valid statuses
- Season: Only Spring/Summer/Fall/Winter

---

## 💡 Use Cases

### 1. PR Progression Dashboard

```sql
SELECT
    race_distance_category,
    race_date,
    finish_time_formatted,
    pace_min_per_km
FROM mart_race_performance
WHERE is_personal_record = true
ORDER BY race_distance_category, race_date;
```

**Shows:** When you set each PR at each distance

### 2. Race Calendar

```sql
SELECT
    race_date,
    race_distance_category,
    finish_time_formatted,
    performance_rating,
    days_since_last_race,
    recovery_status
FROM mart_race_performance
ORDER BY race_date DESC;
```

**Shows:** Full race history with recovery tracking

### 3. Training Effectiveness

```sql
SELECT
    race_date,
    total_training_distance_30d,
    training_runs_30d,
    race_readiness_score,
    performance_rating,
    pct_off_pr
FROM mart_race_performance
ORDER BY race_date;
```

**Shows:** Does more training = better performance?

### 4. Pacing Analysis

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
ORDER BY race_date;
```

**Shows:** Do you race smarter when pacing matches training?

### 5. Performance Trends

```sql
SELECT
    race_date,
    race_distance_category,
    pace_min_per_km,
    pace_ma_3_races,
    pace_change_vs_last_race
FROM mart_race_performance
WHERE race_distance_category = '10K'
ORDER BY race_date;
```

**Shows:** Are you improving at 10K over time?

---

## 🎯 For Streamlit Dashboard

### Race PR Card

```python
import streamlit as st
import duckdb

conn = duckdb.connect("data/duckdb/running_analytics.duckdb")

# Get all PRs
prs = conn.execute("""
    SELECT
        race_distance_category,
        finish_time_formatted,
        pace_min_per_km,
        race_date
    FROM main_gold.mart_race_performance
    WHERE is_personal_record = true
    ORDER BY race_distance_category
""").df()

# Display as cards
for idx, row in prs.iterrows():
    st.metric(
        label=f"{row['race_distance_category']} PR",
        value=row['finish_time_formatted'],
        delta=f"{row['pace_min_per_km']:.2f} min/km"
    )
```

### Race Performance Chart

```python
import plotly.express as px

# Get all races
races = conn.execute("""
    SELECT * FROM main_gold.mart_race_performance
    ORDER BY race_date
""").df()

# Pace progression by distance
fig = px.line(
    races,
    x='race_date',
    y='pace_min_per_km',
    color='race_distance_category',
    markers=True,
    title='Race Pace Progression'
)

# Highlight PRs
pr_races = races[races['is_personal_record']]
fig.add_scatter(
    x=pr_races['race_date'],
    y=pr_races['pace_min_per_km'],
    mode='markers',
    marker=dict(size=15, symbol='star', color='gold'),
    name='PRs'
)

st.plotly_chart(fig)
```

### Race Readiness Heatmap

```python
# Readiness vs Performance
fig = px.scatter(
    races,
    x='race_readiness_score',
    y='pct_off_pr',
    color='performance_rating',
    size='total_training_distance_30d',
    hover_data=['race_date', 'race_distance_category'],
    title='Race Readiness vs Performance'
)
st.plotly_chart(fig)
```

---

## 🐛 Troubleshooting

### "No data returned"

**Check races exist:**

```sql
SELECT count(*) FROM int_unified_activities WHERE is_race = true;
```

If 0, make sure your staging model correctly identifies races.

### "PR calculations seem wrong"

**Check PR values:**

```sql
SELECT
    race_distance_category,
    min(duration_minutes) as pr,
    count(*) as num_races
FROM main_gold.mart_race_performance
GROUP BY race_distance_category;
```

### "Training context is null"

**Check training data exists before races:**

```sql
SELECT
    race_date,
    total_training_distance_30d,
    training_runs_30d
FROM main_gold.mart_race_performance;
```

If null, you may not have training data in the 30 days before races.

---

## 📚 Key Takeaways

1. **PRs are relative to distance** - Each distance has its own PR
2. **Training context matters** - Better preparation = better performance
3. **Recovery is tracked** - Quick turnarounds show up in the data
4. **Trends reveal improvement** - Moving averages smooth out noise
5. **Performance is multifaceted** - Time, pacing, readiness all matter

---

## 🚀 Next Steps

1. **Build Streamlit dashboard** to visualize races
2. **Correlate with health data** - Does sleep affect race performance?
3. **Add race predictions** - Based on training, predict finish time
4. **Weather data** - Did conditions affect performance?
5. **Nutrition tracking** - Pre-race fueling impact

---

**Great work on building this mart! Your race analysis capabilities are now production-ready.** 🎉
