# 📋 Quick Command Reference - mart_health_trends

## 🚀 Essential Commands

### Run the model
```bash
cd dbt_project
dbt run --select mart_health_trends
```

### Run tests
```bash
dbt test --select mart_health_trends
```

### Run model + tests together
```bash
dbt build --select mart_health_trends
```

### View recent data
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT date, recovery_score, training_readiness, total_sleep_hours
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7
"
```

## 📊 Useful Queries

### Daily recovery overview
```sql
SELECT 
    date,
    recovery_score,
    training_readiness,
    total_sleep_hours,
    resting_heart_rate,
    average_stress_level
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7;
```

### Best/worst recovery days
```sql
-- Best
SELECT date, recovery_score, training_readiness
FROM mart_health_trends
ORDER BY recovery_score DESC
LIMIT 5;

-- Worst
SELECT date, recovery_score, training_readiness
FROM mart_health_trends
ORDER BY recovery_score ASC
LIMIT 5;
```

### Sleep debt check
```sql
SELECT 
    date,
    sleep_debt_7day_cumulative,
    total_sleep_hours,
    sleep_quality_category
FROM mart_health_trends
WHERE sleep_debt_7day_cumulative > 5
ORDER BY date DESC;
```

### Weekly recovery trends
```sql
SELECT 
    week_start_date,
    round(avg(recovery_score), 1) as avg_recovery,
    round(avg(total_sleep_hours), 1) as avg_sleep,
    round(avg(resting_heart_rate), 1) as avg_rhr
FROM mart_health_trends
GROUP BY week_start_date
ORDER BY week_start_date DESC
LIMIT 4;
```

### RHR trend analysis
```sql
SELECT 
    date,
    resting_heart_rate,
    rhr_7day_avg,
    rhr_vs_7day_avg,
    CASE 
        WHEN rhr_vs_7day_avg > 0 THEN '⬆️ Above avg'
        WHEN rhr_vs_7day_avg < 0 THEN '⬇️ Below avg'
        ELSE '➡️ At avg'
    END as trend
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7;
```

### Training readiness calendar
```sql
SELECT 
    day_of_week,
    count(*) as days,
    round(avg(recovery_score), 1) as avg_score
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

### Stress analysis
```sql
SELECT 
    date,
    average_stress_level,
    pct_time_high_stress,
    stress_vs_7day_avg
FROM mart_health_trends
WHERE pct_time_high_stress > 15
ORDER BY date DESC;
```

### Body Battery patterns
```sql
SELECT 
    date,
    body_battery_charged,
    body_battery_drained,
    body_battery_net_change,
    CASE 
        WHEN body_battery_net_change >= 20 THEN '🔋 Great recovery'
        WHEN body_battery_net_change >= 0 THEN '✅ Positive'
        ELSE '⚠️ Deficit'
    END as battery_status
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7;
```

## 🔍 Data Quality Checks

### Check for nulls
```sql
SELECT 
    count(*) as total_rows,
    sum(CASE WHEN recovery_score IS NULL THEN 1 ELSE 0 END) as null_recovery,
    sum(CASE WHEN training_readiness IS NULL THEN 1 ELSE 0 END) as null_readiness
FROM mart_health_trends;
```

### Validate calculations
```sql
SELECT 
    date,
    total_sleep_hours,
    (8.0 - total_sleep_hours) as calculated_debt,
    sleep_debt_hours,
    CASE 
        WHEN abs((8.0 - total_sleep_hours) - sleep_debt_hours) < 0.01 THEN '✓'
        ELSE '✗'
    END as validation
FROM mart_health_trends
ORDER BY date DESC
LIMIT 5;
```

### Check value ranges
```sql
SELECT 
    min(recovery_score) as min_score,
    max(recovery_score) as max_score,
    min(resting_heart_rate) as min_rhr,
    max(resting_heart_rate) as max_rhr,
    min(total_sleep_hours) as min_sleep,
    max(total_sleep_hours) as max_sleep
FROM mart_health_trends;
```

## 🎯 Training Integration

### Combine with training load
```sql
SELECT 
    t.week_start_date,
    round(avg(t.weekly_distance_km), 1) as avg_distance,
    round(avg(h.recovery_score), 1) as avg_recovery,
    round(avg(h.total_sleep_hours), 1) as avg_sleep
FROM mart_training_analysis t
JOIN mart_health_trends h 
    ON t.week_start_date = h.week_start_date
GROUP BY t.week_start_date
ORDER BY t.week_start_date DESC
LIMIT 4;
```

### Recovery vs workout days
```sql
SELECT 
    h.date,
    h.recovery_score,
    h.training_readiness,
    count(a.activity_id) as num_workouts,
    round(coalesce(sum(a.distance_km), 0), 1) as total_distance
FROM mart_health_trends h
LEFT JOIN int_unified_activities a 
    ON h.date = a.activity_date
GROUP BY h.date, h.recovery_score, h.training_readiness
ORDER BY h.date DESC
LIMIT 7;
```

## 📈 Trending Queries

### 30-day recovery trend
```sql
SELECT 
    date,
    recovery_score,
    avg(recovery_score) OVER (
        ORDER BY date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as score_7day_ma
FROM mart_health_trends
WHERE date >= current_date - INTERVAL '30 days'
ORDER BY date;
```

### Sleep pattern by weekday
```sql
SELECT 
    day_of_week,
    round(avg(total_sleep_hours), 2) as avg_sleep,
    round(avg(sleep_quality_category = 'excellent') * 100, 1) as pct_excellent,
    round(avg(sleep_debt_hours), 2) as avg_debt
FROM mart_health_trends
GROUP BY day_of_week
ORDER BY 
    CASE day_of_week
        WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
    END;
```

## 🎨 Export for Visualization

### CSV export for charts
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
COPY (
    SELECT 
        date,
        recovery_score,
        total_sleep_hours,
        resting_heart_rate,
        average_stress_level
    FROM mart_health_trends
    ORDER BY date
) TO '../data/exports/health_trends.csv' (HEADER, DELIMITER ',');
"
```

### Weekly summary export
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
COPY (
    SELECT 
        week_start_date,
        week_avg_sleep,
        week_avg_rhr,
        week_avg_stress,
        week_total_steps
    FROM mart_health_trends
    GROUP BY week_start_date, week_avg_sleep, week_avg_rhr, week_avg_stress, week_total_steps
    ORDER BY week_start_date DESC
) TO '../data/exports/weekly_health.csv' (HEADER, DELIMITER ',');
"
```

## 🔧 Troubleshooting

### Check model compilation
```bash
dbt compile --select mart_health_trends
```

### View compiled SQL
```bash
cat target/compiled/running_performance_analyzer/models/marts/mart_health_trends.sql
```

### Debug mode
```bash
dbt run --select mart_health_trends --debug
```

### Check dependencies
```bash
dbt ls --select mart_health_trends --resource-type model
```

## 📝 Common Filters

### Recent data only
```sql
WHERE date >= current_date - INTERVAL '30 days'
```

### Weekends only
```sql
WHERE day_of_week IN ('Saturday', 'Sunday')
```

### Poor recovery days
```sql
WHERE recovery_score < 60 OR training_readiness = 'low'
```

### High sleep debt
```sql
WHERE sleep_debt_7day_cumulative > 7
```

### RHR elevated
```sql
WHERE rhr_vs_7day_avg > 5
```

---

**Save this file for quick reference during development and analysis!** 💾
