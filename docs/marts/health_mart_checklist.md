# ✅ mart_health_trends - Implementation Checklist

## Phase 1: File Verification ✓

- [x] `mart_health_trends.sql` created in `models/marts/`
- [x] `schema_marts_health.yml` created in `models/marts/`
- [x] `HEALTH_MART_GUIDE.md` created
- [x] `RECOVERY_SCORE_GUIDE.md` created
- [x] `HEALTH_MART_SUMMARY.md` created

## Phase 2: Model Execution

### Step 1: Navigate to dbt project
```bash
cd /path/to/running-performance-analyzer/dbt_project
```

### Step 2: Run the model
```bash
dbt run --select mart_health_trends
```

**Expected output:**
```
Running with dbt=1.x.x
Found 1 model, 0 tests, 0 snapshots, 0 analyses, 0 macros, 0 operations, 0 seed files, 0 sources

Concurrency: 4 threads (target='dev')

1 of 1 START sql table model main.mart_health_trends ..................... [RUN]
1 of 1 OK created sql table model main.mart_health_trends ................ [OK in X.XXs]

Completed successfully
```

- [ ] Model ran successfully
- [ ] No compilation errors
- [ ] Check row count matches days of health data

### Step 3: Run tests
```bash
dbt test --select mart_health_trends
```

**Expected output:**
```
Running with dbt=1.x.x
Found X models, 64 tests, 0 snapshots...

Concurrency: 4 threads (target='dev')

1 of 64 START test accepted_values_mart_health_trends_... ............... [RUN]
1 of 64 PASS accepted_values_mart_health_trends_... ..................... [PASS in X.XXs]
...
64 of 64 PASS not_null_mart_health_trends_week_total_steps .............. [PASS in X.XXs]

Completed successfully
Done. PASS=64 WARN=0 ERROR=0 SKIP=0 TOTAL=64
```

- [ ] All 64 tests passed
- [ ] No warnings or errors
- [ ] If any failures, check TROUBLESHOOTING section below

## Phase 3: Data Verification

### Query 1: Basic row check
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT count(*) as total_days
FROM mart_health_trends
"
```

- [ ] Row count matches expected days
- [ ] No duplicate dates

### Query 2: Check recent data
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    date,
    total_sleep_hours,
    sleep_quality_category,
    resting_heart_rate,
    recovery_score,
    training_readiness
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7
"
```

- [ ] Dates are correct
- [ ] Sleep hours are realistic (4-12 hours)
- [ ] RHR is realistic (40-80 bpm typically)
- [ ] Recovery scores are 0-100
- [ ] Training readiness categories look correct

### Query 3: Check calculated fields
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    date,
    total_sleep_hours,
    sleep_7day_avg,
    sleep_vs_7day_avg,
    resting_heart_rate,
    rhr_7day_avg,
    rhr_vs_7day_avg
FROM mart_health_trends
ORDER BY date DESC
LIMIT 7
"
```

- [ ] 7-day averages are calculating (not null after 7 days)
- [ ] Deviation calculations are correct
- [ ] Trends make sense

### Query 4: Recovery score distribution
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    training_readiness,
    count(*) as days,
    round(avg(recovery_score), 1) as avg_score,
    round(min(recovery_score), 1) as min_score,
    round(max(recovery_score), 1) as max_score
FROM mart_health_trends
GROUP BY training_readiness
ORDER BY 
    CASE training_readiness
        WHEN 'optimal' THEN 1
        WHEN 'good' THEN 2
        WHEN 'moderate' THEN 3
        WHEN 'low' THEN 4
    END
"
```

- [ ] All readiness categories present
- [ ] Score ranges make sense
- [ ] Distribution looks reasonable

## Phase 4: Advanced Validation

### Check for nulls in key fields
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    sum(CASE WHEN total_sleep_hours IS NULL THEN 1 ELSE 0 END) as null_sleep,
    sum(CASE WHEN resting_heart_rate IS NULL THEN 1 ELSE 0 END) as null_rhr,
    sum(CASE WHEN recovery_score IS NULL THEN 1 ELSE 0 END) as null_recovery,
    sum(CASE WHEN training_readiness IS NULL THEN 1 ELSE 0 END) as null_readiness
FROM mart_health_trends
"
```

- [ ] No nulls in sleep
- [ ] No nulls in RHR
- [ ] No nulls in recovery_score
- [ ] No nulls in training_readiness

### Check sleep debt calculation
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    date,
    total_sleep_hours,
    sleep_debt_hours,
    sleep_debt_7day_cumulative
FROM mart_health_trends
WHERE sleep_debt_7day_cumulative > 5
ORDER BY date DESC
LIMIT 5
"
```

- [ ] sleep_debt_hours = 8 - total_sleep_hours
- [ ] 7-day cumulative makes sense
- [ ] No extreme values

### Check Body Battery logic
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    date,
    body_battery_charged,
    body_battery_drained,
    body_battery_net_change,
    (body_battery_charged - body_battery_drained) as calculated_net
FROM mart_health_trends
ORDER BY date DESC
LIMIT 5
"
```

- [ ] net_change = charged - drained
- [ ] Values are realistic
- [ ] No calculation errors

## Phase 5: Integration Testing

### Test join with training mart
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    t.week_start_date,
    count(*) as training_records,
    count(h.date) as health_records,
    round(avg(t.weekly_distance_km), 1) as avg_distance,
    round(avg(h.recovery_score), 1) as avg_recovery
FROM mart_training_analysis t
LEFT JOIN mart_health_trends h 
    ON t.week_start_date = h.week_start_date
GROUP BY t.week_start_date
ORDER BY t.week_start_date DESC
LIMIT 4
"
```

- [ ] Join works correctly
- [ ] Week alignment is correct
- [ ] Both datasets present

### Test correlation queries
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    h.training_readiness,
    count(a.activity_id) as num_activities,
    round(avg(a.distance_km), 1) as avg_distance
FROM mart_health_trends h
LEFT JOIN int_unified_activities a 
    ON h.date = a.activity_date
GROUP BY h.training_readiness
"
```

- [ ] Query executes successfully
- [ ] Results make sense
- [ ] No join issues

## Phase 6: Documentation Check

### Review generated docs (optional)
```bash
dbt docs generate
dbt docs serve
```

Then open http://localhost:8080 and check:
- [ ] mart_health_trends appears in DAG
- [ ] All columns documented
- [ ] Tests visible
- [ ] Lineage correct (stg_garmin_health → mart_health_trends)

## Phase 7: Git Commit

```bash
git add dbt_project/models/marts/mart_health_trends.sql
git add dbt_project/models/marts/schema_marts_health.yml
git add dbt_project/HEALTH_MART_GUIDE.md
git add dbt_project/RECOVERY_SCORE_GUIDE.md
git add dbt_project/HEALTH_MART_SUMMARY.md

git commit -m "feat(dbt): Add mart_health_trends with recovery scoring

- Comprehensive health metrics mart with 64 columns
- Sleep quality tracking and debt calculation
- RHR trends with 7/28-day averages
- Stress level analysis and distribution
- Body Battery net change tracking
- Recovery score (0-100) based on weighted algorithm
- Training readiness assessment (optimal/good/moderate/low)
- 64 comprehensive tests for data quality
- Complete documentation and usage guides"
```

- [ ] Files committed
- [ ] Commit message clear
- [ ] No sensitive data included

## 🐛 Troubleshooting

### Issue: Model fails with "column not found"
**Solution:** Check that all columns exist in `stg_garmin_health`
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
DESCRIBE stg_garmin_health
"
```

### Issue: Tests failing on value ranges
**Solution:** Check actual data ranges
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    min(total_sleep_hours) as min_sleep,
    max(total_sleep_hours) as max_sleep,
    min(resting_heart_rate) as min_rhr,
    max(resting_heart_rate) as max_rhr,
    min(average_stress_level) as min_stress,
    max(average_stress_level) as max_stress
FROM stg_garmin_health
"
```
Then adjust test ranges in schema file if needed.

### Issue: Recovery score is NULL
**Solution:** Check that all component fields have data
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    date,
    total_sleep_hours,
    resting_heart_rate,
    average_stress_level,
    body_battery_charged,
    body_battery_drained
FROM stg_garmin_health
WHERE total_sleep_hours IS NULL 
   OR resting_heart_rate IS NULL
   OR average_stress_level IS NULL
ORDER BY date DESC
LIMIT 5
"
```

### Issue: HRV numeric conversion issues
**Solution:** Check actual HRV values
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT DISTINCT hrv_status
FROM stg_garmin_health
WHERE hrv_status IS NOT NULL
"
```
Then update CASE statement in model if needed.

### Issue: Training readiness all shows same value
**Solution:** Check distribution of component metrics
```bash
duckdb ../data/duckdb/running_analytics.duckdb "
SELECT 
    count(*) FILTER (WHERE total_sleep_hours >= 7) as sleep_7plus,
    count(*) FILTER (WHERE total_sleep_hours >= 6) as sleep_6plus,
    count(*) FILTER (WHERE total_sleep_hours >= 5) as sleep_5plus,
    count(*) FILTER (WHERE total_sleep_hours < 5) as sleep_under5
FROM stg_garmin_health
"
```

## ✅ Success Criteria

By the end of this checklist, you should have:
- ✅ mart_health_trends model running successfully
- ✅ All 64 tests passing
- ✅ Data validated and making sense
- ✅ Recovery scores distributed across range
- ✅ Training readiness categories balanced
- ✅ Integration with other marts working
- ✅ Documentation complete
- ✅ Code committed to Git

## 🎉 Next Steps After Completion

1. **Create sample queries file** with your favorite health analyses
2. **Update NEXT_STEPS.md** to mark health mart as complete
3. **Plan Streamlit health dashboard** (Phase 3)
4. **Consider AI Coach integration** (Phase 4)
5. **Share progress** on LinkedIn/GitHub

## 📊 Example Success Output

When everything is working, you should see something like:

```
Recovery Score Distribution:
- Optimal (90-100): 12 days
- Good (75-89): 45 days
- Moderate (60-74): 28 days
- Low (<60): 8 days

Training Readiness:
- Optimal: 18 days
- Good: 52 days
- Moderate: 20 days
- Low: 3 days

Average Recovery Score: 78.3
Sleep Debt (7-day avg): 3.2 hours
RHR Trend: Decreasing (good!)
```

---

**You've got this! This is the final mart for Phase 2. After this, you're ready for Streamlit dashboards!** 🚀
