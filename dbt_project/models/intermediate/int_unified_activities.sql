-- =============================================================================
-- INTERMEDIATE MODEL: Unified Activities (Silver Layer)
-- =============================================================================
-- Purpose:
--   Enrich each activity with its same-day health context, and lay the
--   groundwork for a multi-source activity table (Garmin today, Strava future).
--
-- Why an intermediate model?
--   Staging models are thin and source-specific. This intermediate model is
--   where we apply cross-domain business logic — joining activities with the
--   health state the athlete was in when they ran. That context is critical for:
--   - Understanding whether a hard session was appropriate
--   - Building features for the AI coach
--   - Powering training load vs recovery dashboards
--
-- Key Transformations:
--   - LEFT JOIN stg_garmin_activities → stg_garmin_health on activity_date
--   - Add data_source column for future multi-source unification
--   - Add training_readiness level (high / moderate / low) from recovery_score
--   - Add ran_while_tired flag (hard effort on poor recovery day)
--   - Add workout_context label (well_executed / normal / overreaching)
--
-- Grain: One row per activity
--
-- Materialization: VIEW (same schema as staging, consumed by marts)
--
-- Dependencies:
--   - ref('stg_garmin_activities')
--   - ref('stg_garmin_health')
--
-- Downstream:
--   - mart_training_analysis
--   - mart_race_performance
--   - mart_ai_features
--
-- Author: Jeremy Marchandeau
-- Created: 2026-02-16
-- =============================================================================

-- =============================================================================
-- CTE 1: ACTIVITIES
-- =============================================================================
WITH activities AS (

  SELECT *
  FROM {{ ref('stg_garmin_activities') }}

),

-- =============================================================================
-- CTE 2: HEALTH CONTEXT
-- =============================================================================
-- We only need the recovery-relevant columns from the health model.
-- Using a slim CTE avoids pulling all 30+ health columns into the join.
health AS (

  SELECT
    health_date,
    recovery_score,
    sleep_hours,
    sleep_quality,
    sleep_efficiency_pct,
    resting_heart_rate        AS daily_resting_hr,
    hrv_avg,
    hrv_category,
    stress_avg,
    stress_category,
    body_battery_high,
    body_battery_low,
    body_battery_net,
    body_battery_status

  FROM {{ ref('stg_garmin_health') }}

),

-- =============================================================================
-- CTE 3: JOIN + ENRICH
-- =============================================================================
-- Left join so activities are never dropped (health data may be missing for
-- some days if the watch wasn't worn overnight).
joined AS (

  SELECT

    -- -------------------------------------------------------------------------
    -- Source Tag (for future multi-source unification)
    -- -------------------------------------------------------------------------
    -- When Strava integration is added, its activities will also flow through
    -- an int_unified_activities-like model with data_source = 'strava'.
    -- A final UNION in this model will combine them seamlessly.
    'garmin' AS data_source,

    -- -------------------------------------------------------------------------
    -- Activity Identity
    -- -------------------------------------------------------------------------
    a.activity_id,
    a.activity_name,
    a.activity_date,
    a.activity_start_time,
    a.start_hour,
    a.day_of_week,
    a.is_weekend,

    -- -------------------------------------------------------------------------
    -- Activity Classification
    -- -------------------------------------------------------------------------
    a.activity_type,
    a.device_name,
    a.location_name,
    a.is_race,
    a.race_distance_category,
    a.time_of_day,
    a.terrain_type,

    -- -------------------------------------------------------------------------
    -- Performance Metrics
    -- -------------------------------------------------------------------------
    a.distance_km,
    a.duration_minutes,
    a.moving_duration_minutes,
    a.pause_duration_minutes,
    a.avg_pace_min_km,
    a.avg_speed_kmh,
    a.max_speed_kmh,
    a.avg_heart_rate,
    a.max_heart_rate,
    a.hr_delta,
    a.elevation_gain_m,
    a.elevation_loss_m,
    a.net_elevation_m,
    a.elevation_range_m,
    a.calories,
    a.aerobic_training_effect,
    a.anaerobic_training_effect,
    a.total_training_effect,
    a.avg_cadence_spm,
    a.max_cadence_spm,

    -- -------------------------------------------------------------------------
    -- Effort Classification
    -- -------------------------------------------------------------------------
    a.pace_zone,
    a.hr_zone,
    a.effort_level,
    a.training_load,

    -- -------------------------------------------------------------------------
    -- Health Context (same-day recovery state)
    -- -------------------------------------------------------------------------
    -- These columns answer: "How recovered was the athlete when they ran?"
    h.recovery_score,           -- Composite readiness score (0-100)
    h.sleep_hours               AS pre_run_sleep_hours,
    h.sleep_quality             AS pre_run_sleep_quality,
    h.sleep_efficiency_pct      AS pre_run_sleep_efficiency_pct,
    h.daily_resting_hr,         -- Baseline HR that day
    h.hrv_avg,
    h.hrv_category,
    h.stress_avg,
    h.stress_category,
    h.body_battery_high,        -- Peak energy available that day
    h.body_battery_low,
    h.body_battery_net,
    h.body_battery_status,

    -- Flag to know whether health context was available for this activity
    CASE WHEN h.health_date IS NULL THEN TRUE ELSE FALSE END
      AS is_missing_health_context,

    -- -------------------------------------------------------------------------
    -- Audit Fields
    -- -------------------------------------------------------------------------
    a.loaded_at,
    a.updated_at

  FROM activities a
  LEFT JOIN health h
    ON a.activity_date = h.health_date

),

-- =============================================================================
-- CTE 4: BUSINESS LOGIC
-- =============================================================================
-- Cross-domain labels that combine activity effort with recovery state.
-- These are the high-value fields for coaching and AI context.
enriched AS (

  SELECT
    *,

    -- -------------------------------------------------------------------------
    -- Training Readiness
    -- -------------------------------------------------------------------------
    -- How ready was the athlete to train that day?
    -- Derived from the composite recovery_score (0-100).
    --
    -- High   (>= 70): Well recovered — appropriate for hard sessions
    -- Moderate (40-69): Adequately recovered — normal training
    -- Low     (< 40): Under-recovered — should be easy or rest
    -- No data: Health data not available
    CASE
      WHEN is_missing_health_context THEN 'no_data'
      WHEN recovery_score >= 70 THEN 'high'
      WHEN recovery_score >= 40 THEN 'moderate'
      ELSE 'low'
    END AS training_readiness,

    -- -------------------------------------------------------------------------
    -- Ran While Tired
    -- -------------------------------------------------------------------------
    -- TRUE when the athlete did a hard effort despite being under-recovered.
    -- Useful for:
    -- - Flagging potential overtraining patterns
    -- - Contextualising unexpectedly slow sessions
    -- - AI coach advice ("you tend to run hard when tired on Mondays")
    CASE
      WHEN effort_level = 'hard'
       AND (
         pre_run_sleep_quality IN ('poor', 'fair')
         OR (recovery_score IS NOT NULL AND recovery_score < 40)
       )
      THEN TRUE
      ELSE FALSE
    END AS ran_while_tired,

    -- -------------------------------------------------------------------------
    -- Workout Context
    -- -------------------------------------------------------------------------
    -- A three-tier label capturing the relationship between effort and recovery.
    --
    -- well_executed:  Hard effort on a well-recovered day — ideal
    -- normal:         Effort matches recovery state — sustainable
    -- overreaching:   Hard effort despite poor recovery — risk zone
    -- easy_day:       Low effort regardless of recovery — recovery run
    -- no_data:        Can't assess (missing health data)
    CASE
      WHEN is_missing_health_context THEN 'no_data'
      WHEN effort_level = 'easy' THEN 'easy_day'
      WHEN effort_level = 'hard' AND training_readiness = 'high'     THEN 'well_executed'
      WHEN effort_level = 'hard' AND training_readiness = 'moderate' THEN 'normal'
      WHEN effort_level = 'hard' AND training_readiness = 'low'      THEN 'overreaching'
      WHEN effort_level = 'moderate'                                  THEN 'normal'
      ELSE 'normal'
    END AS workout_context

  FROM joined

)

-- =============================================================================
-- FINAL OUTPUT
-- =============================================================================
SELECT * FROM enriched

-- =============================================================================
-- USAGE NOTES
-- =============================================================================
-- This is the primary activity table for all downstream marts.
--
-- Example queries:
--
-- 1. Find overreaching sessions:
--    SELECT activity_date, activity_name, effort_level, recovery_score
--    FROM main_silver.int_unified_activities
--    WHERE workout_context = 'overreaching'
--    ORDER BY activity_date DESC
--
-- 2. Training load vs recovery (for mart_training_analysis):
--    SELECT activity_date, training_load, recovery_score, effort_level
--    FROM main_silver.int_unified_activities
--    WHERE activity_type = 'running'
--    ORDER BY activity_date
--
-- 3. Activities with health context for AI coach (mart_ai_features):
--    SELECT * FROM main_silver.int_unified_activities
--    WHERE activity_date >= CURRENT_DATE - INTERVAL 84 DAY  -- 12 weeks
--    ORDER BY activity_date
--
-- =============================================================================
-- NEXT STEPS
-- =============================================================================
-- When Strava integration is added:
--   1. Create stg_strava_activities.sql (same columns, data_source = 'strava')
--   2. UNION stg_strava_activities into this model alongside stg_garmin_activities
--   3. Downstream marts automatically include Strava data — no other changes needed
-- =============================================================================
