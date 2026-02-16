# Health Trends Mart - Testing Guide

## Files Created

1. **mart_health_trends.sql** - Main model file
   Location: `dbt_project/models/marts/mart_health_trends.sql`

2. **schema_marts_health.yml** - Tests and documentation
   Location: `dbt_project/models/marts/schema_marts_health.yml`

## Key Features

### Sleep Metrics
- Total sleep hours with breakdown (deep, light, REM, awake)
- Sleep quality categorization (excellent, good, fair, poor)
- Sleep efficiency percentage
- Sleep debt tracking (daily and 7-day cumulative)
- 7-day and 28-day rolling averages

### Heart Rate Metrics
- Resting heart rate (RHR) trends
- 7-day and 28-day RHR averages
- Day-over-day and week-over-week comparisons
- HRV status and numeric conversion

### Stress Analysis
- Average and max daily stress levels
- Time distribution across stress levels (low, medium, high)
- Stress percentages of total day
- 7-day rolling average
- Stress trend analysis

### Body Battery (Garmin Recovery Metric)
- Daily charge and drain amounts
- Highest and lowest levels
- Net change (positive = recovery day)

### Recovery Metrics
- **Recovery Score (0-100):** Weighted combination of:
  - Sleep quality (40%)
  - RHR deviation from average (20%)
  - Stress level (20%)
  - Body Battery net change (20%)

- **Training Readiness:** Multi-factor assessment
  - Optimal: Great sleep, low RHR, low stress, positive battery
  - Good: Adequate sleep, normal RHR, moderate stress
  - Moderate: Reduced sleep or elevated metrics
  - Low: Poor sleep or high stress/RHR

### Trend Analysis
- Day-over-day changes for all metrics
- Week-over-week comparisons (same day)
- Deviation from 7-day averages
- Weekly aggregations

## Running the Model

### Step 1: Run the model
```bash
cd /path/to/running-performance-analyzer/dbt_project
dbt run --select mart_health_trends
```

### Step 2: Run tests
```bash
dbt test --select mart_health_trends
```

### Step 3: Check results
```bash
# Query the mart directly
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    date,
    total_sleep_hours,
    sleep_quality_category,
    resting_heart_rate,
    average_stress_level,
    recovery_score,
    training_readiness
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7
"
```

## Expected Test Results

The schema file includes comprehensive tests:
- **64 total tests** covering:
  - Not null constraints (critical fields)
  - Unique constraints (date)
  - Accepted values (categories, day names)
  - Range validations (0-100 for scores, realistic ranges for metrics)

## Sample Queries

### 1. Recovery trends over time
```sql
SELECT 
    date,
    recovery_score,
    training_readiness,
    sleep_quality_category,
    rhr_vs_7day_avg,
    stress_vs_7day_avg
FROM mart_health_trends
ORDER BY date DESC
LIMIT 14;
```

### 2. Sleep debt analysis
```sql
SELECT 
    date,
    total_sleep_hours,
    sleep_debt_hours,
    sleep_debt_7day_cumulative,
    sleep_vs_7day_avg
FROM mart_health_trends
WHERE sleep_debt_7day_cumulative > 5  -- More than 5 hours of debt
ORDER BY date DESC;
```

### 3. Best and worst recovery days
```sql
-- Best recovery
SELECT 
    date,
    recovery_score,
    training_readiness,
    total_sleep_hours,
    resting_heart_rate,
    average_stress_level
FROM mart_health_trends
ORDER BY recovery_score DESC
LIMIT 5;

-- Worst recovery
SELECT 
    date,
    recovery_score,
    training_readiness,
    total_sleep_hours,
    resting_heart_rate,
    average_stress_level
FROM mart_health_trends
ORDER BY recovery_score ASC
LIMIT 5;
```

### 4. RHR trends
```sql
SELECT 
    week_start_date,
    week_avg_rhr,
    min(resting_heart_rate) as lowest_rhr,
    max(resting_heart_rate) as highest_rhr,
    avg(rhr_vs_7day_avg) as avg_deviation
FROM mart_health_trends
GROUP BY week_start_date
ORDER BY week_start_date DESC;
```

### 5. Stress patterns by day of week
```sql
SELECT 
    day_of_week,
    avg(average_stress_level) as avg_stress,
    avg(pct_time_high_stress) as avg_pct_high_stress,
    avg(total_sleep_hours) as avg_sleep
FROM mart_health_trends
GROUP BY day_of_week
ORDER BY 
    CASE day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
    END;
```

### 6. Training readiness distribution
```sql
SELECT 
    training_readiness,
    count(*) as days,
    round(avg(recovery_score), 1) as avg_score,
    round(avg(total_sleep_hours), 1) as avg_sleep,
    round(avg(resting_heart_rate), 1) as avg_rhr
FROM mart_health_trends
GROUP BY training_readiness
ORDER BY 
    CASE training_readiness
        WHEN 'optimal' THEN 1
        WHEN 'good' THEN 2
        WHEN 'moderate' THEN 3
        WHEN 'low' THEN 4
    END;
```

## Business Logic Highlights

### Recovery Score Calculation
```
Recovery Score = 
  + Sleep component (0-40 points): (hours / 8) * 40
  + RHR component (0-20 points): Based on deviation from 7-day avg
  + Stress component (0-20 points): Lower stress = more points
  + Body Battery (0-20 points): Positive net change = more points

Total: 0-100 (higher is better)
```

### Training Readiness Logic
- **Optimal:** ≥7 hrs sleep, RHR ≤105% of avg, stress ≤40, BB net ≥0
- **Good:** ≥6 hrs sleep, RHR ≤110% of avg, stress ≤55
- **Moderate:** ≥5 hrs sleep
- **Low:** <5 hrs sleep or poor metrics

### Sleep Quality Categories
- **Excellent:** ≥7 hrs total + ≥1.5 hrs deep
- **Good:** ≥6 hrs total + ≥1 hr deep
- **Fair:** ≥5 hrs total
- **Poor:** <5 hrs total

## Troubleshooting

### If dbt run fails:
1. Check that `stg_garmin_health` exists and has data
2. Verify DuckDB connection in `profiles.yml`
3. Check for syntax errors in the SQL

### If tests fail:
1. Check which tests failed: `dbt test --select mart_health_trends --store-failures`
2. Review the data ranges - they might need adjustment for your specific data
3. Check for null values where not expected

### Common adjustments needed:
- **HRV numeric conversion:** Update the CASE statement if Garmin returns different HRV formats
- **Test ranges:** Adjust min/max values based on your actual data
- **Recovery score weights:** Modify the 40/20/20/20 split if needed

## Next Steps

After running this mart:

1. **Verify data quality:**
   - Run all tests
   - Check that recovery scores make sense
   - Verify trends are calculating correctly

2. **Analyze your data:**
   - Look at recovery patterns
   - Identify optimal training days
   - Track sleep debt trends
   - Correlate with training load

3. **Dashboard integration:**
   - This mart is ready for Streamlit Phase 3
   - Create visualizations for sleep trends
   - Show RHR evolution
   - Display recovery score heatmap
   - Alert on high sleep debt

4. **AI Coach integration:**
   - Use recovery_score for training recommendations
   - Consider training_readiness in workout planning
   - Alert on concerning trends (rising RHR, sleep debt)

## What This Mart Enables

### For Analysis:
- Identify optimal training windows based on recovery
- Detect patterns in sleep quality
- Monitor stress impact on performance
- Track long-term health trends

### For AI Coach:
- Personalized training recommendations based on recovery
- Rest day suggestions when recovery is low
- Sleep optimization advice
- Stress management insights

### For Dashboards:
- Health overview cards
- Sleep quality trends
- RHR evolution charts
- Recovery score heatmap
- Training readiness calendar
