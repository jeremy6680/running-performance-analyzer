# 📊 mart_training_summary - Data Lineage

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      BRONZE LAYER (Raw Data)                    │
│                                                                 │
│  ┌───────────────────────────┐  ┌──────────────────────────┐  │
│  │ raw_garmin_activities      │  │ raw_garmin_daily_health  │  │
│  │                            │  │                          │  │
│  │ - activity_id              │  │ - date                   │  │
│  │ - activity_date            │  │ - steps                  │  │
│  │ - distance_meters          │  │ - sleep_seconds          │  │
│  │ - duration_seconds         │  │ - resting_hr             │  │
│  │ - avg_heart_rate           │  │ - hrv_ms                 │  │
│  │ - avg_pace                 │  │ - stress_level           │  │
│  │ - elevation_gain_meters    │  │ - body_battery           │  │
│  │ ...                        │  │ ...                      │  │
│  └───────────────┬────────────┘  └──────────────────────────┘  │
└─────────────────┼──────────────────────────────────────────────┘
                  │
                  │ dbt source + staging
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SILVER LAYER (Cleaned Data)                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ stg_garmin_activities                                     │  │
│  │                                                           │  │
│  │ - activity_id (unique)                                    │  │
│  │ - activity_date                                           │  │
│  │ - distance_km (converted)                                 │  │
│  │ - duration_minutes (converted)                            │  │
│  │ - pace_min_per_km (calculated)                            │  │
│  │ - avg_heart_rate_bpm                                      │  │
│  │ - max_heart_rate_bpm                                      │  │
│  │ - elevation_gain_m                                        │  │
│  │ - pace_zone (Easy/Moderate/Tempo/Threshold/Speed)        │  │
│  │ - hr_zone (Zone 1-5)                                      │  │
│  │ - effort_level (1-10)                                     │  │
│  │ - training_load_score (duration × intensity)             │  │
│  │ - is_race (boolean)                                       │  │
│  │ - terrain (Flat/Rolling/Hilly)                            │  │
│  │ ...                                                        │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────┘
                              │
                              │ dbt intermediate
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 SILVER LAYER (Unified/Enriched)                 │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ int_unified_activities                                    │  │
│  │                                                           │  │
│  │ All columns from stg_garmin_activities                    │  │
│  │ +                                                          │  │
│  │ - data_source (Garmin/Strava/etc)                        │  │
│  │ - activity_type_standardized                              │  │
│  │ - training_readiness (Good/Moderate/Poor)                 │  │
│  │ - ran_while_tired (boolean)                               │  │
│  │ - workout_context (Post-rest/Back-to-back/Recovery)      │  │
│  │ ...                                                        │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────┘
                              │
                              │ dbt mart (aggregation + analytics)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GOLD LAYER (Analytics)                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ mart_training_summary                                     │  │
│  │                                                           │  │
│  │ GRAIN: One row per week                                   │  │
│  │                                                           │  │
│  │ Weekly Aggregates:                                        │  │
│  │ - total_activities                                        │  │
│  │ - total_distance_km                                       │  │
│  │ - total_duration_minutes                                  │  │
│  │ - avg_pace_min_per_km (distance-weighted)                │  │
│  │ - avg_heart_rate_bpm                                      │  │
│  │ - total_elevation_gain_m                                  │  │
│  │ - total_training_load                                     │  │
│  │ - pct_zone1_easy ... pct_zone5_max                       │  │
│  │                                                           │  │
│  │ Rolling Averages (Window Functions):                      │  │
│  │ - rolling_4wk_avg_distance_km                             │  │
│  │ - rolling_4wk_avg_activities                              │  │
│  │ - rolling_4wk_avg_training_load                           │  │
│  │ - rolling_8wk_avg_distance_km                             │  │
│  │ - rolling_8wk_avg_activities                              │  │
│  │ - rolling_8wk_avg_training_load                           │  │
│  │                                                           │  │
│  │ Comparisons (LAG + Percentage Change):                    │  │
│  │ - distance_vs_prev_week_pct                               │  │
│  │ - activities_vs_prev_week_pct                             │  │
│  │ - distance_vs_4wk_avg_pct                                 │  │
│  │ - distance_trend_4wk (Increasing/Decreasing/Stable)      │  │
│  │ - training_load_trend_4wk                                 │  │
│  │                                                           │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────┘
                              │
                              │ Used by:
                              ▼
                    ┌─────────────────────┐
                    │  Streamlit Dashboard │
                    │  (Phase 3)           │
                    └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  AI Coach            │
                    │  (Phase 4)           │
                    └─────────────────────┘
```

---

## SQL Transformation Steps

### Step 1: Create Week Spine

```sql
with weeks_spine as (
    select distinct date_trunc('week', activity_date) as week_start_date
    from int_unified_activities
)
-- Result: One row per week that has activities
-- Example: 2026-02-10, 2026-02-03, 2026-01-27, ...
```

### Step 2: Aggregate by Week

```sql
weekly_aggregates as (
    select
        date_trunc('week', activity_date) as week_start_date,
        count(*) as total_activities,
        sum(distance_km) as total_distance_km,
        sum(pace_min_per_km * distance_km) / sum(distance_km) as avg_pace_min_per_km
    from int_unified_activities
    group by 1
)
-- Result: Weekly totals/averages
-- Example: Week 2026-02-10 → 3 activities, 15.5 km, 5:20 min/km
```

### Step 3: Calculate Rolling Metrics

```sql
rolling_metrics as (
    select
        week_start_date,
        total_distance_km,
        avg(total_distance_km) over (
            order by week_start_date
            rows between 3 preceding and current row
        ) as rolling_4wk_avg_distance_km,
        lag(total_distance_km, 1) over (
            order by week_start_date
        ) as prev_week_distance_km
    from weekly_aggregates
)
-- Result: Each week + its rolling averages + previous week value
-- Example: Week 2026-02-10 → 15.5 km, 4wk avg 18.2 km, prev week 22.1 km
```

### Step 4: Calculate Percentage Changes

```sql
final as (
    select
        week_start_date,
        total_distance_km,
        rolling_4wk_avg_distance_km,
        round(
            ((total_distance_km - prev_week_distance_km) / prev_week_distance_km) * 100,
            1
        ) as distance_vs_prev_week_pct,
        case
            when total_distance_km > rolling_4wk_avg_distance_km then 'Increasing'
            when total_distance_km < rolling_4wk_avg_distance_km then 'Decreasing'
            else 'Stable'
        end as distance_trend_4wk
    from rolling_metrics
)
-- Result: Final analytics with all calculated fields
-- Example: Week 2026-02-10 → -29.9% vs prev, -14.8% vs 4wk avg, Decreasing
```

---

## Column Transformation Examples

### From Bronze → Gold

**Distance:**

```
Bronze: distance_meters = 10000 (raw API value)
  ↓
Silver: distance_km = 10.0 (converted)
  ↓
Gold: total_distance_km = 45.2 (weekly sum)
      avg_distance_per_activity_km = 15.1 (weekly average)
      rolling_4wk_avg_distance_km = 38.7 (smoothed trend)
```

**Pace:**

```
Bronze: avg_pace = 330 (seconds per km)
  ↓
Silver: pace_min_per_km = 5.5 (minutes:seconds)
        pace_zone = 'Moderate' (classified)
  ↓
Gold: avg_pace_min_per_km = 5.3 (distance-weighted weekly average)
```

**Heart Rate:**

```
Bronze: avg_heart_rate = 155 (bpm)
  ↓
Silver: avg_heart_rate_bpm = 155
        hr_zone = 'Zone 3 (Tempo)' (classified)
        hr_zone_predominant = 'Zone 3 (Tempo)'
  ↓
Gold: avg_heart_rate_bpm = 158 (weekly average)
      pct_zone3_tempo = 60.0 (% of activities in this zone)
```

**Training Load:**

```
Bronze: duration_seconds = 3600, avg_heart_rate = 150
  ↓
Silver: duration_minutes = 60
        effort_level = 7 (based on pace zone)
        training_load_score = 420 (duration × effort)
  ↓
Gold: total_training_load = 1680 (weekly sum)
      rolling_4wk_avg_training_load = 1520 (smoothed)
      training_load_trend_4wk = 'Increasing'
```

---

## Key SQL Techniques Used

### Window Functions

```sql
-- Rolling average: current + 3 previous rows = 4 weeks
avg(metric) over (
    order by week_start_date
    rows between 3 preceding and current row
)

-- Previous value: get value from 1 row back
lag(metric, 1) over (order by week_start_date)

-- Running total (cumulative sum)
sum(metric) over (order by week_start_date)
```

### Date Functions

```sql
-- Get Monday of the week
date_trunc('week', activity_date)

-- Extract year/week number
extract(year from date)
extract(week from date)
```

### Aggregations

```sql
-- Distance-weighted average (longer runs have more weight)
sum(pace * distance) / sum(distance)

-- Conditional aggregation (count only races)
count(case when is_race then 1 end)

-- Average excluding nulls
avg(case when hr_zone is not null then hr_zone end)
```

---

## Testing Coverage

```
mart_training_summary
├── Data Quality Tests (15)
│   ├── unique(week_start_date)
│   ├── not_null(week_start_date, year, week_number, ...)
│   └── ...
│
├── Range Tests (35)
│   ├── total_activities: 0-20
│   ├── total_distance_km: 0-300
│   ├── avg_pace_min_per_km: 3.0-15.0
│   ├── avg_heart_rate_bpm: 100-200
│   └── ...
│
└── Business Logic Tests (3)
    ├── distance_trend_4wk in ('Increasing', 'Decreasing', 'Stable')
    ├── training_load_trend_4wk in ('Increasing', 'Decreasing', 'Stable')
    └── ...
```

**Total: 53 tests**

---

## Performance Characteristics

**Row Count:**

- ~52 weeks per year of data
- Example: 2 years = ~104 rows

**Query Performance:**

- SELECT \* → Instant (<10ms)
- Aggregations over all weeks → <100ms
- Complex filtering → <500ms

**Build Time:**

- dbt run → 1-3 seconds
- Window functions are efficient in DuckDB

**Storage:**

- ~5-10 KB per week of data
- Example: 100 weeks ≈ 500 KB - 1 MB

---

## Downstream Usage Examples

### Streamlit Dashboard

```python
# Load data
df = load_training_summary()

# Weekly distance trend
fig = px.line(df,
    x='week_start_date',
    y=['total_distance_km', 'rolling_4wk_avg_distance_km'],
    title='Weekly Distance with 4-Week Rolling Average'
)

# Training load comparison
fig = px.bar(df,
    x='week_start_date',
    y='total_training_load',
    color='training_load_trend_4wk',
    title='Training Load Trend'
)
```

### AI Coach Context

```python
# Get last 12 weeks for LLM
recent = df.head(12)

context = f"""
Training Summary (Last 12 weeks):
- Current weekly distance: {df.iloc[0]['total_distance_km']:.1f} km
- 4-week average: {df.iloc[0]['rolling_4wk_avg_distance_km']:.1f} km
- Trend: {df.iloc[0]['distance_trend_4wk']}
- Training load: {df.iloc[0]['total_training_load']:.1f}
"""
```

### Analytics

```python
# Find peak training weeks
peak_weeks = df.nlargest(5, 'total_distance_km')

# Identify rapid increases (injury risk)
risk_weeks = df[df['distance_vs_4wk_avg_pct'] > 30]

# Training consistency
std_dev = df['total_activities'].std()
```

---

## Related Marts (To Be Created)

```
mart_training_summary (✅ Complete)
├── mart_race_performance
│   └── Filter: is_race = true
│       - PR tracking
│       - Race pace analysis
│
├── mart_health_trends
│   └── Join: with raw_garmin_daily_health
│       - Sleep quality
│       - HRV trends
│       - Recovery metrics
│
└── mart_ai_features
    └── Combine: activities + health + training_summary
        - Training readiness
        - Injury risk
        - Performance predictions
```

---

## Questions to Explore with This Mart

1. **Training Volume**
   - How much am I running per week?
   - Is my volume increasing, decreasing, or stable?
   - What's my longest training week?

2. **Training Consistency**
   - How many activities per week?
   - Am I maintaining consistent volume?
   - Are there gaps in training?

3. **Training Intensity**
   - What's my average pace?
   - How is my HR zone distribution?
   - Am I training too hard/easy?

4. **Training Load**
   - What's my weekly training stress?
   - Is load increasing gradually or too rapidly?
   - Do I need a recovery week?

5. **Trends**
   - Is my fitness improving (volume up, pace down)?
   - Are my rolling averages trending up?
   - When was my last peak training block?

6. **Injury Risk**
   - Any week >30% above 4-week average? (red flag)
   - Sudden drops in volume? (possible injury)
   - Consistent load progression? (safe)

---

**This mart is your foundation for all training analytics!** 🎉
