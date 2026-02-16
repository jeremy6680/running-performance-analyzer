-- =============================================================================
-- STAGING MODEL: Garmin Daily Health (Silver Layer)
-- =============================================================================
-- Purpose:
--   Clean and standardize raw Garmin daily health data from the bronze layer.
--   This is the SILVER layer - one step removed from raw data.
--
-- Transformations Applied:
--   - Convert sleep/duration fields from seconds to hours
--   - Convert daily distance from meters to kilometers
--   - Add date dimensions (day of week, week number, month, weekend flag)
--   - Calculate derived metrics (sleep efficiency, total calories, body battery net)
--   - Add sleep quality, stress, and recovery categorizations
--   - Handle null values appropriately
--
-- Grain: One row per calendar day
--
-- Materialization: VIEW (fast to build, feeds into marts)
--
-- Dependencies:
--   - Bronze layer: raw_garmin_daily_health table from Garmin API
--
-- Usage in downstream models:
--   Reference this model using: ref('stg_garmin_health')
--
-- Author: Jeremy Marchandeau
-- Created: 2026-02-16
-- =============================================================================

-- =============================================================================
-- CTE 1: SOURCE DATA
-- =============================================================================
WITH source_data AS (

  SELECT *
  FROM {{ source('garmin', 'raw_garmin_daily_health') }}

),

-- =============================================================================
-- CTE 2: BASIC CLEANING & TYPE CASTING
-- =============================================================================
-- In this step we:
-- - Rename columns for consistency and clarity
-- - Convert seconds to hours for sleep metrics
-- - Convert distance from meters to kilometers
-- - Calculate derived totals (total calories, body battery net)
-- - Extract date dimensions for flexible analysis
cleaned AS (

  SELECT
    -- -------------------------------------------------------------------------
    -- Identifier
    -- -------------------------------------------------------------------------
    date AS health_date,

    -- -------------------------------------------------------------------------
    -- Date Dimensions
    -- -------------------------------------------------------------------------
    -- Extract components for grouping and filtering

    -- Day of week (0=Sunday, 1=Monday, ..., 6=Saturday)
    EXTRACT(DOW FROM date) AS day_of_week,

    -- ISO week number (1-53)
    EXTRACT(WEEK FROM date) AS week_of_year,

    -- Month number (1-12)
    EXTRACT(MONTH FROM date) AS month_number,

    -- Year
    EXTRACT(YEAR FROM date) AS year_number,

    -- -------------------------------------------------------------------------
    -- Steps & Daily Movement
    -- -------------------------------------------------------------------------
    COALESCE(steps, 0)                            AS steps,

    -- Convert daily distance from meters to kilometers
    ROUND(COALESCE(distance_m, 0) / 1000.0, 2)   AS daily_distance_km,

    -- -------------------------------------------------------------------------
    -- Calories
    -- -------------------------------------------------------------------------
    COALESCE(active_calories, 0)                  AS active_calories,
    COALESCE(bmr_calories, 0)                     AS bmr_calories,

    -- Total daily calories = activity + resting metabolic rate
    COALESCE(active_calories, 0) + COALESCE(bmr_calories, 0)
                                                  AS total_calories,

    -- -------------------------------------------------------------------------
    -- Heart Rate
    -- -------------------------------------------------------------------------
    resting_heart_rate,    -- Key fitness indicator (lower = fitter)
    min_heart_rate,        -- Usually overnight minimum (nocturnal dip)
    max_heart_rate,        -- Daily maximum (activity, stress, etc.)

    -- -------------------------------------------------------------------------
    -- HRV (Heart Rate Variability)
    -- -------------------------------------------------------------------------
    -- Higher HRV = better recovery & autonomic nervous system health
    hrv_avg,
    hrv_status,            -- Garmin's classification (balanced, unbalanced, low, poor)

    -- -------------------------------------------------------------------------
    -- Sleep Metrics (seconds → hours)
    -- -------------------------------------------------------------------------
    -- Converting to hours makes values more human-readable
    -- Optimal: 7-9 hours total, with ~20% deep, ~20% REM

    ROUND(COALESCE(sleep_seconds, 0) / 3600.0, 2)       AS sleep_hours,
    ROUND(COALESCE(deep_sleep_seconds, 0) / 3600.0, 2)  AS deep_sleep_hours,
    ROUND(COALESCE(light_sleep_seconds, 0) / 3600.0, 2) AS light_sleep_hours,
    ROUND(COALESCE(rem_sleep_seconds, 0) / 3600.0, 2)   AS rem_sleep_hours,
    ROUND(COALESCE(awake_seconds, 0) / 3600.0, 2)       AS awake_hours,

    -- Sleep efficiency: proportion of time-in-bed actually spent sleeping
    -- High efficiency (> 85%) = good sleep; low = fragmented or insomnia
    CASE
      WHEN COALESCE(sleep_seconds, 0) + COALESCE(awake_seconds, 0) = 0 THEN NULL
      ELSE ROUND(
        sleep_seconds * 100.0
        / (sleep_seconds + COALESCE(awake_seconds, 0)),
        1
      )
    END AS sleep_efficiency_pct,

    -- Sleep stage composition (% of total sleep)
    -- These help assess sleep architecture quality
    CASE
      WHEN COALESCE(sleep_seconds, 0) = 0 THEN NULL
      ELSE ROUND(deep_sleep_seconds * 100.0 / NULLIF(sleep_seconds, 0), 1)
    END AS deep_sleep_pct,

    CASE
      WHEN COALESCE(sleep_seconds, 0) = 0 THEN NULL
      ELSE ROUND(rem_sleep_seconds * 100.0 / NULLIF(sleep_seconds, 0), 1)
    END AS rem_sleep_pct,

    -- -------------------------------------------------------------------------
    -- Stress
    -- -------------------------------------------------------------------------
    -- Garmin stress score (0-100): 0-25 rest/low, 26-50 moderate, 51-75 high, 76+ very high
    stress_avg,

    -- -------------------------------------------------------------------------
    -- Body Battery
    -- -------------------------------------------------------------------------
    -- Garmin's energy reserve metric (0-100 scale)
    -- High charge = well recovered; high drain = heavy activity/stress day
    COALESCE(body_battery_charged, 0)  AS body_battery_charged,
    COALESCE(body_battery_drained, 0)  AS body_battery_drained,
    body_battery_high,                 -- Peak energy level of the day
    body_battery_low,                  -- Lowest energy level of the day

    -- Net body battery change (positive = net recovery, negative = net fatigue)
    COALESCE(body_battery_charged, 0) - COALESCE(body_battery_drained, 0)
                                       AS body_battery_net,

    -- -------------------------------------------------------------------------
    -- Respiration
    -- -------------------------------------------------------------------------
    avg_waking_respiration_rate,   -- Breaths per minute while awake
    avg_sleep_respiration_rate,    -- Breaths per minute during sleep

    -- -------------------------------------------------------------------------
    -- Audit Fields
    -- -------------------------------------------------------------------------
    inserted_at AS loaded_at,
    updated_at

  FROM source_data

),

-- =============================================================================
-- CTE 3: ADD CALCULATED FIELDS & BUSINESS LOGIC
-- =============================================================================
-- Domain-specific categorizations that make data actionable for analysis
enriched AS (

  SELECT
    *,  -- Include all fields from 'cleaned' CTE

    -- -------------------------------------------------------------------------
    -- Weekend Flag
    -- -------------------------------------------------------------------------
    CASE
      WHEN day_of_week IN (0, 6) THEN TRUE   -- 0=Sunday, 6=Saturday
      ELSE FALSE
    END AS is_weekend,

    -- -------------------------------------------------------------------------
    -- Sleep Quality Category
    -- -------------------------------------------------------------------------
    -- Based on total sleep hours (adult recommendation: 7-9 hours)
    --
    -- Poor   < 5h: Significant sleep debt, performance will suffer
    -- Fair   5-6h: Below recommended, some impairment
    -- Good   6-7h: Adequate for most people
    -- Excellent >= 7h: Optimal recovery
    CASE
      WHEN sleep_hours IS NULL OR sleep_hours = 0 THEN 'no_data'
      WHEN sleep_hours < 5.0 THEN 'poor'
      WHEN sleep_hours < 6.0 THEN 'fair'
      WHEN sleep_hours < 7.0 THEN 'good'
      ELSE 'excellent'
    END AS sleep_quality,

    -- -------------------------------------------------------------------------
    -- Stress Category
    -- -------------------------------------------------------------------------
    -- Based on Garmin's 0-100 stress scale
    CASE
      WHEN stress_avg IS NULL THEN 'no_data'
      WHEN stress_avg <= 25 THEN 'low'
      WHEN stress_avg <= 50 THEN 'moderate'
      WHEN stress_avg <= 75 THEN 'high'
      ELSE 'very_high'
    END AS stress_category,

    -- -------------------------------------------------------------------------
    -- Body Battery Status
    -- -------------------------------------------------------------------------
    -- Based on peak body battery level for the day
    -- This indicates how well-charged you started or ended the day
    CASE
      WHEN body_battery_high IS NULL THEN 'no_data'
      WHEN body_battery_high >= 75 THEN 'high'
      WHEN body_battery_high >= 50 THEN 'moderate'
      WHEN body_battery_high >= 25 THEN 'low'
      ELSE 'depleted'
    END AS body_battery_status,

    -- -------------------------------------------------------------------------
    -- HRV Category
    -- -------------------------------------------------------------------------
    -- Contextualise HRV values. These thresholds are approximate general ranges.
    -- Individual baselines vary widely; use trends over time, not absolute values.
    CASE
      WHEN hrv_avg IS NULL THEN 'no_data'
      WHEN hrv_avg >= 60 THEN 'excellent'
      WHEN hrv_avg >= 40 THEN 'good'
      WHEN hrv_avg >= 20 THEN 'moderate'
      ELSE 'low'
    END AS hrv_category,

    -- -------------------------------------------------------------------------
    -- Steps Goal Achievement
    -- -------------------------------------------------------------------------
    -- Common step goal is 10,000/day; flag whether it was met
    CASE
      WHEN steps >= 10000 THEN TRUE
      ELSE FALSE
    END AS steps_goal_met,

    -- -------------------------------------------------------------------------
    -- Recovery Score (Composite)
    -- -------------------------------------------------------------------------
    -- A simple 0-100 score combining multiple recovery indicators:
    --   - Sleep quality:    up to 35 points
    --   - Stress level:     up to 25 points (inverted - lower stress = more points)
    --   - Body Battery:     up to 25 points
    --   - Resting HR:       up to 15 points (lower = better)
    --
    -- This is a simplified heuristic, not a clinical measurement.
    -- Use it to spot trends, not as an absolute readiness benchmark.
    ROUND(
      -- Sleep contribution (35 pts max)
      CASE
        WHEN sleep_hours IS NULL OR sleep_hours = 0 THEN 0
        WHEN sleep_hours >= 8.0 THEN 35
        WHEN sleep_hours >= 7.0 THEN 30
        WHEN sleep_hours >= 6.0 THEN 20
        WHEN sleep_hours >= 5.0 THEN 10
        ELSE 0
      END

      -- Stress contribution (25 pts max - inverted)
      + CASE
        WHEN stress_avg IS NULL THEN 12  -- assume neutral if no data
        WHEN stress_avg <= 25 THEN 25
        WHEN stress_avg <= 50 THEN 15
        WHEN stress_avg <= 75 THEN 5
        ELSE 0
      END

      -- Body battery contribution (25 pts max)
      + CASE
        WHEN body_battery_high IS NULL THEN 12  -- assume neutral if no data
        WHEN body_battery_high >= 75 THEN 25
        WHEN body_battery_high >= 50 THEN 18
        WHEN body_battery_high >= 25 THEN 8
        ELSE 0
      END

      -- Resting HR contribution (15 pts max - lower HR = better)
      + CASE
        WHEN resting_heart_rate IS NULL THEN 7  -- assume neutral if no data
        WHEN resting_heart_rate < 45 THEN 15    -- athlete-level
        WHEN resting_heart_rate < 55 THEN 12    -- excellent
        WHEN resting_heart_rate < 65 THEN 8     -- good
        WHEN resting_heart_rate < 75 THEN 4     -- average
        ELSE 0
      END,
    0) AS recovery_score,

    -- -------------------------------------------------------------------------
    -- Data Quality Flags
    -- -------------------------------------------------------------------------

    -- Flag days where all sleep data is missing (can happen for short nights
    -- or if the watch wasn't worn to sleep)
    CASE
      WHEN sleep_hours IS NULL OR sleep_hours = 0 THEN TRUE
      ELSE FALSE
    END AS has_missing_sleep,

    -- Flag days where HR data is entirely missing
    CASE
      WHEN resting_heart_rate IS NULL THEN TRUE
      ELSE FALSE
    END AS has_missing_hr

  FROM cleaned

),

-- =============================================================================
-- CTE 4: FINAL SELECTION
-- =============================================================================
final AS (

  SELECT *
  FROM enriched

  -- Only include days that have at least steps or sleep data
  -- (fully empty rows add no analytical value)
  WHERE steps > 0
     OR sleep_hours > 0

)

-- =============================================================================
-- FINAL OUTPUT
-- =============================================================================
SELECT * FROM final

-- =============================================================================
-- USAGE NOTES
-- =============================================================================
-- This model transforms raw daily health metrics into analytics-ready data.
--
-- Example queries for downstream use:
--
-- 1. Sleep trends over last 30 days:
--    SELECT health_date, sleep_hours, sleep_quality, deep_sleep_pct
--    FROM main_silver.stg_garmin_health
--    WHERE health_date >= CURRENT_DATE - INTERVAL 30 DAY
--    ORDER BY health_date
--
-- 2. Identify high-stress / poor recovery days:
--    SELECT health_date, stress_avg, recovery_score, sleep_quality
--    FROM main_silver.stg_garmin_health
--    WHERE stress_category IN ('high', 'very_high')
--      OR sleep_quality IN ('poor', 'fair')
--    ORDER BY health_date
--
-- 3. Weekly recovery averages:
--    SELECT year_number, week_of_year,
--           AVG(recovery_score)       AS avg_recovery,
--           AVG(sleep_hours)          AS avg_sleep,
--           AVG(resting_heart_rate)   AS avg_rhr
--    FROM main_silver.stg_garmin_health
--    GROUP BY year_number, week_of_year
--    ORDER BY year_number, week_of_year
--
-- =============================================================================
-- NEXT STEPS
-- =============================================================================
-- 1. Create int_unified_activities.sql merging activities + health context
-- 2. Create mart_health_trends.sql for dashboard visualizations
-- 3. Create mart_ai_features.sql for LLM context building
-- =============================================================================
