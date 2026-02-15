-- =============================================================================
-- STAGING MODEL: Garmin Activities (Silver Layer)
-- =============================================================================
-- Purpose:
--   Clean and standardize raw Garmin activity data from the bronze layer.
--   This is the SILVER layer - one step removed from raw data.
--
-- Transformations Applied:
--   - Rename columns for consistency
--   - Add calculated fields (pace zones, effort levels, training load)
--   - Handle null values appropriately
--   - Filter out invalid data (zero distance, very short activities)
--   - Add business logic (race detection, terrain classification)
--
-- Grain: One row per activity
--
-- Materialization: VIEW (fast to build, feeds into marts)
--
-- Dependencies:
--   - Bronze layer: raw_garmin_activities table from Garmin API
--
-- Usage in downstream models:
--   Reference this model using: ref('stg_garmin_activities')
--
-- Author: Jeremy Marchandeau
-- Created: 2025-02-16
-- =============================================================================

-- =============================================================================
-- CTE 1: SOURCE DATA
-- =============================================================================
-- Pull raw data from the bronze layer
-- The source() function references our sources.yml definition
WITH source_data AS (
  
  SELECT * 
  FROM {{ source('garmin', 'raw_garmin_activities') }}

),

-- =============================================================================
-- CTE 2: BASIC CLEANING & TYPE CASTING
-- =============================================================================
-- In this step we:
-- - Cast data types for easier analysis (timestamps to dates)
-- - Rename columns for consistency
-- - Handle null values with COALESCE
-- - Convert units to more intuitive formats (m/s to km/h)
-- - Calculate derived metrics (pause time, HR delta, net elevation)
cleaned AS (

  SELECT
    -- -------------------------------------------------------------------------
    -- Identifiers
    -- -------------------------------------------------------------------------
    -- These uniquely identify each activity
    activity_id,           -- Primary key from Garmin API
    activity_name,         -- User-defined name (can be null)
    
    -- -------------------------------------------------------------------------
    -- Temporal Fields
    -- -------------------------------------------------------------------------
    -- We extract different time components for flexible analysis
    
    -- Cast to DATE for easier grouping by day/week/month
    -- This removes the time component, making aggregations simpler
    CAST(activity_date AS DATE) AS activity_date,
    
    -- Keep full timestamp for precise analysis (splits, intervals)
    start_time_local AS activity_start_time,
    
    -- Extract time components for analysis
    -- HOUR: 0-23, useful for "time of day" analysis
    EXTRACT(HOUR FROM start_time_local) AS start_hour,
    
    -- DOW: Day of week (0=Sunday, 1=Monday, ..., 6=Saturday)
    -- Useful for weekend vs weekday analysis
    EXTRACT(DOW FROM start_time_local) AS day_of_week,
    
    -- -------------------------------------------------------------------------
    -- Activity Metadata
    -- -------------------------------------------------------------------------
    activity_type,         -- running, cycling, swimming, etc.
    device_name,          -- Which Garmin device was used
    location_name,        -- City/location of activity
    
    -- -------------------------------------------------------------------------
    -- Distance Metrics
    -- -------------------------------------------------------------------------
    -- Distance is already in good units (km) from bronze layer
    -- We add null handling to ensure calculations don't fail
    COALESCE(distance_km, 0.0) AS distance_km,
    
    -- -------------------------------------------------------------------------
    -- Duration Metrics
    -- -------------------------------------------------------------------------
    -- Duration is already converted to minutes in bronze layer
    duration_minutes,
    
    -- Moving duration excludes pauses (more accurate for pace calculation)
    -- We round to 2 decimal places for readability
    ROUND(moving_duration_seconds / 60.0, 2) AS moving_duration_minutes,
    
    -- Calculate pause time (total duration - moving duration)
    -- This tells us how much time was spent stopped/paused
    ROUND(
      (duration_seconds - COALESCE(moving_duration_seconds, duration_seconds)) / 60.0, 
      2
    ) AS pause_duration_minutes,
    
    -- -------------------------------------------------------------------------
    -- Speed & Pace Metrics
    -- -------------------------------------------------------------------------
    -- Pace (min/km) is already calculated in bronze layer
    -- This is the primary metric for runners
    avg_pace_min_km,
    
    -- Convert speed from m/s to km/h (more intuitive)
    -- Multiply by 3.6 to convert: (m/s) * (3600s/h) / (1000m/km) = km/h
    ROUND(avg_speed_mps * 3.6, 2) AS avg_speed_kmh,
    ROUND(max_speed_mps * 3.6, 2) AS max_speed_kmh,
    
    -- -------------------------------------------------------------------------
    -- Heart Rate Metrics
    -- -------------------------------------------------------------------------
    avg_heart_rate,        -- Average HR in beats per minute (bpm)
    max_heart_rate,        -- Maximum HR reached during activity
    
    -- Calculate heart rate delta (max - avg)
    -- This indicates intensity variation within the workout
    -- Large delta = high intensity intervals
    -- Small delta = steady-state effort
    max_heart_rate - avg_heart_rate AS hr_delta,
    
    -- -------------------------------------------------------------------------
    -- Elevation Metrics
    -- -------------------------------------------------------------------------
    -- Elevation gain and loss in meters
    elevation_gain_m,
    elevation_loss_m,
    
    -- Calculate net elevation change (gain - loss)
    -- Positive = more uphill, Negative = more downhill
    elevation_gain_m - COALESCE(elevation_loss_m, 0) AS net_elevation_m,
    
    -- Elevation range (highest point - lowest point)
    -- Useful for understanding terrain variety
    max_elevation_m - COALESCE(min_elevation_m, 0) AS elevation_range_m,
    
    -- -------------------------------------------------------------------------
    -- Calories & Training Effect
    -- -------------------------------------------------------------------------
    calories,                      -- Estimated calories burned
    aerobic_training_effect,       -- Garmin's aerobic score (0-5)
    anaerobic_training_effect,     -- Garmin's anaerobic score (0-5)
    
    -- Total training effect (sum of aerobic + anaerobic)
    -- Gives overall workout intensity score
    COALESCE(aerobic_training_effect, 0) + COALESCE(anaerobic_training_effect, 0) 
      AS total_training_effect,
    
    -- -------------------------------------------------------------------------
    -- Cadence (Running)
    -- -------------------------------------------------------------------------
    -- Cadence = steps per minute
    -- Optimal running cadence is typically 170-180 spm
    avg_cadence AS avg_cadence_spm,
    max_cadence AS max_cadence_spm,
    
    -- -------------------------------------------------------------------------
    -- Audit Fields
    -- -------------------------------------------------------------------------
    -- Track when data was loaded for debugging and lineage
    inserted_at AS loaded_at,
    updated_at
    
  FROM source_data

),

-- =============================================================================
-- CTE 3: ADD CALCULATED FIELDS & BUSINESS LOGIC
-- =============================================================================
-- This is where we add domain-specific logic and categorizations
-- These fields make the data more useful for analysis and coaching
enriched AS (

  SELECT
    *,  -- Include all fields from 'cleaned' CTE
    
    -- -------------------------------------------------------------------------
    -- Activity Classification: Race Detection
    -- -------------------------------------------------------------------------
    -- We use multiple heuristics to detect if an activity is a race:
    -- 1. Activity name contains race-related keywords
    -- 2. Distance matches standard race distances (5K, 10K, half, full)
    --
    -- Why this matters: Races are analyzed differently than training runs
    -- (PRs, race performance trends, pacing strategy)
    CASE
      -- Keyword-based detection
      WHEN LOWER(COALESCE(activity_name, '')) LIKE '%race%' THEN TRUE
      WHEN LOWER(COALESCE(activity_name, '')) LIKE '%marathon%' THEN TRUE
      WHEN LOWER(COALESCE(activity_name, '')) LIKE '%5k%' THEN TRUE
      WHEN LOWER(COALESCE(activity_name, '')) LIKE '%10k%' THEN TRUE
      WHEN LOWER(COALESCE(activity_name, '')) LIKE '%half%' THEN TRUE
      
      -- Distance-based detection (with small tolerance for GPS drift)
      WHEN distance_km BETWEEN 4.9 AND 5.1 THEN TRUE      -- 5K
      WHEN distance_km BETWEEN 9.9 AND 10.1 THEN TRUE     -- 10K
      WHEN distance_km BETWEEN 21.0 AND 21.2 THEN TRUE    -- Half Marathon
      WHEN distance_km BETWEEN 42.0 AND 42.4 THEN TRUE    -- Marathon
      
      ELSE FALSE
    END AS is_race,
    
    -- Race distance category (only for detected races)
    -- This allows us to compare performances across same distances
    CASE
      WHEN distance_km BETWEEN 4.9 AND 5.1 THEN '5K'
      WHEN distance_km BETWEEN 9.9 AND 10.1 THEN '10K'
      WHEN distance_km BETWEEN 21.0 AND 21.2 THEN 'Half Marathon'
      WHEN distance_km BETWEEN 42.0 AND 42.4 THEN 'Marathon'
      WHEN distance_km > 42.4 THEN 'Ultra'
      ELSE NULL  -- Not a race or non-standard distance
    END AS race_distance_category,
    
    -- -------------------------------------------------------------------------
    -- Pace Zones (Based on typical running paces)
    -- -------------------------------------------------------------------------
    -- These zones are general guidelines based on common pace ranges
    -- You can adjust these thresholds based on your personal fitness level
    --
    -- Why pace zones matter:
    -- - Easy runs should be in 'easy' or 'recovery' zones
    -- - Tempo runs should be in 'moderate' or 'fast' zones
    -- - Interval/speed work should be in 'fast' or 'elite' zones
    CASE
      WHEN avg_pace_min_km IS NULL THEN 'no_data'
      WHEN avg_pace_min_km < 4.0 THEN 'elite'        -- < 4:00/km (very fast)
      WHEN avg_pace_min_km < 5.0 THEN 'fast'         -- 4:00-5:00/km (tempo pace)
      WHEN avg_pace_min_km < 6.0 THEN 'moderate'     -- 5:00-6:00/km (steady state)
      WHEN avg_pace_min_km < 7.0 THEN 'easy'         -- 6:00-7:00/km (base building)
      ELSE 'recovery'                                 -- > 7:00/km (recovery/walking)
    END AS pace_zone,
    
    -- -------------------------------------------------------------------------
    -- Heart Rate Zones (Simplified - using absolute values)
    -- -------------------------------------------------------------------------
    -- NOTE: These are simplified zones using absolute HR values
    -- TODO: In future, join with health data to get resting HR and calculate
    --       personalized zones based on HR reserve (HRR method)
    --
    -- Current zones (approximate):
    -- Zone 1 (< 120 bpm): Recovery, very easy effort
    -- Zone 2 (120-140 bpm): Base building, aerobic development
    -- Zone 3 (140-160 bpm): Tempo, moderate effort
    -- Zone 4 (160-175 bpm): Threshold, hard effort
    -- Zone 5 (> 175 bpm): Max effort, VO2max intervals
    --
    -- These zones should be adjusted based on your max HR
    -- Rule of thumb: Max HR = 220 - age (though this varies individually)
    CASE
      WHEN avg_heart_rate IS NULL THEN 'no_hr_data'
      WHEN avg_heart_rate < 120 THEN 'zone_1_recovery'
      WHEN avg_heart_rate < 140 THEN 'zone_2_base'
      WHEN avg_heart_rate < 160 THEN 'zone_3_tempo'
      WHEN avg_heart_rate < 175 THEN 'zone_4_threshold'
      ELSE 'zone_5_max'
    END AS hr_zone,
    
    -- -------------------------------------------------------------------------
    -- Effort Level (Combining pace and HR for overall assessment)
    -- -------------------------------------------------------------------------
    -- This combines both pace and heart rate to determine overall effort
    -- It's more accurate than using either metric alone
    --
    -- Easy: Low HR + slow pace (recovery, base building)
    -- Moderate: Medium HR + medium pace (steady runs, long runs)
    -- Hard: High HR OR fast pace (tempo, intervals, races)
    CASE
      WHEN avg_heart_rate IS NULL THEN 'unknown'
      WHEN avg_heart_rate < 130 AND avg_pace_min_km > 6.5 THEN 'easy'
      WHEN avg_heart_rate < 150 AND avg_pace_min_km BETWEEN 5.5 AND 6.5 THEN 'moderate'
      WHEN avg_heart_rate >= 150 OR avg_pace_min_km < 5.5 THEN 'hard'
      ELSE 'moderate'
    END AS effort_level,
    
    -- -------------------------------------------------------------------------
    -- Training Load (Simplified TRIMP calculation)
    -- -------------------------------------------------------------------------
    -- TRIMP = Training Impulse = duration × intensity factor
    --
    -- This is a simplified version of the TRIMP (TRaining IMPulse) metric
    -- Full TRIMP uses exponential weighting based on HR zones
    --
    -- Our simplified version:
    -- - Low HR (< 130): 1.0x multiplier
    -- - Medium HR (130-150): 1.5x multiplier
    -- - High HR (150-170): 2.0x multiplier
    -- - Very high HR (> 170): 2.5x multiplier
    --
    -- Example: 60 min run at HR 155 = 60 × 2.0 = 120 training load
    --
    -- Why this matters:
    -- - Track cumulative weekly load to prevent overtraining
    -- - Compare load across different workout types
    -- - Monitor training stress balance
    ROUND(
      duration_minutes * 
      CASE 
        WHEN avg_heart_rate IS NULL THEN 1.0
        WHEN avg_heart_rate < 130 THEN 1.0
        WHEN avg_heart_rate < 150 THEN 1.5
        WHEN avg_heart_rate < 170 THEN 2.0
        ELSE 2.5
      END, 
      2
    ) AS training_load,
    
    -- -------------------------------------------------------------------------
    -- Terrain Classification
    -- -------------------------------------------------------------------------
    -- Categorize activities by elevation gain to understand terrain difficulty
    --
    -- Flat (< 50m): Roads, tracks, flat trails
    -- Rolling (50-150m): Gentle hills, undulating terrain
    -- Hilly (150-300m): Significant elevation changes
    -- Mountainous (> 300m): Mountain trails, steep climbs
    --
    -- Why this matters:
    -- - Adjust expectations for pace (slower on hills is normal)
    -- - Track trail running vs road running separately
    -- - Plan training based on race terrain
    CASE
      WHEN elevation_gain_m IS NULL THEN 'unknown'
      WHEN elevation_gain_m < 50 THEN 'flat'
      WHEN elevation_gain_m < 150 THEN 'rolling'
      WHEN elevation_gain_m < 300 THEN 'hilly'
      ELSE 'mountainous'
    END AS terrain_type,
    
    -- -------------------------------------------------------------------------
    -- Time of Day
    -- -------------------------------------------------------------------------
    -- Categorize when the activity occurred
    -- Useful for analyzing performance patterns:
    -- - Are you faster in morning vs evening?
    -- - Do you prefer certain times for long runs?
    CASE
      WHEN start_hour BETWEEN 5 AND 11 THEN 'morning'    -- 5 AM - 11 AM
      WHEN start_hour BETWEEN 12 AND 17 THEN 'afternoon' -- 12 PM - 5 PM
      WHEN start_hour BETWEEN 18 AND 21 THEN 'evening'   -- 6 PM - 9 PM
      ELSE 'night'                                        -- 10 PM - 4 AM
    END AS time_of_day,
    
    -- -------------------------------------------------------------------------
    -- Weekend Flag
    -- -------------------------------------------------------------------------
    -- TRUE if activity occurred on Saturday or Sunday
    -- Useful for analyzing:
    -- - Weekend long runs vs weekday shorter runs
    -- - Training patterns (do you run more on weekends?)
    CASE 
      WHEN day_of_week IN (0, 6) THEN TRUE  -- 0=Sunday, 6=Saturday
      ELSE FALSE
    END AS is_weekend,
    
    -- -------------------------------------------------------------------------
    -- Data Quality Flags
    -- -------------------------------------------------------------------------
    -- These flags help identify problematic data that might need review
    
    -- Flag 1: Missing critical data
    -- Activities with zero distance or duration are likely errors
    CASE
      WHEN distance_km = 0 OR distance_km IS NULL THEN TRUE
      WHEN duration_minutes = 0 OR duration_minutes IS NULL THEN TRUE
      ELSE FALSE
    END AS has_data_quality_issues,
    
    -- Flag 2: Very short activities
    -- Activities under 5 minutes are likely device tests or accidental starts
    -- These are filtered out in the final CTE
    CASE
      WHEN duration_minutes < 5 THEN TRUE
      ELSE FALSE
    END AS is_very_short,
    
    -- Flag 3: Unrealistic pace
    -- Pace < 3 min/km = world-class marathon pace (unlikely for most)
    -- Pace > 15 min/km = very slow walking pace (might be GPS errors)
    CASE
      WHEN avg_pace_min_km < 3.0 OR avg_pace_min_km > 15.0 THEN TRUE
      ELSE FALSE
    END AS has_unrealistic_pace

  FROM cleaned

),

-- =============================================================================
-- CTE 4: FINAL SELECTION & FILTERING
-- =============================================================================
-- Apply data quality filters to ensure we only include valid activities
final AS (

  SELECT
    *
  
  FROM enriched
  
  -- -------------------------------------------------------------------------
  -- Data Quality Filters
  -- -------------------------------------------------------------------------
  -- Only include activities that meet minimum quality standards
  
  -- Filter 1: Must have distance and duration
  WHERE distance_km > 0
    AND duration_minutes > 0
    
  -- Filter 2: Must be at least 5 minutes long
  -- This filters out accidental starts, device tests, etc.
  -- Matches the min_activity_duration variable in dbt_project.yml
  AND duration_minutes >= 5
  
  -- Optional Filter 3: Remove activities with unrealistic pace
  -- Uncomment the line below if you want to exclude these
  -- Note: Sometimes GPS errors cause weird pace values, but the activity is valid
  -- AND has_unrealistic_pace = FALSE

)

-- =============================================================================
-- FINAL OUTPUT
-- =============================================================================
-- Return the final cleaned and enriched dataset
SELECT * FROM final

-- =============================================================================
-- USAGE NOTES
-- =============================================================================
-- This model transforms your raw Garmin activities into analytics-ready data
-- 
-- Example queries for downstream use:
--
-- 1. Get all running activities from last 30 days:
--    SELECT * FROM main_silver.stg_garmin_activities
--    WHERE activity_type = 'running'
--      AND activity_date >= CURRENT_DATE - INTERVAL 30 DAY
--
-- 2. Find all races:
--    SELECT * FROM main_silver.stg_garmin_activities
--    WHERE is_race = TRUE
--    ORDER BY activity_date
--
-- 3. Analyze training by effort level:
--    SELECT 
--      effort_level,
--      COUNT(*) AS num_activities,
--      SUM(distance_km) AS total_distance
--    FROM main_silver.stg_garmin_activities
--    WHERE activity_type = 'running'
--    GROUP BY effort_level
--
-- 4. Weekend vs weekday comparison:
--    SELECT 
--      is_weekend,
--      AVG(distance_km) AS avg_distance,
--      AVG(avg_pace_min_km) AS avg_pace
--    FROM main_silver.stg_garmin_activities
--    WHERE activity_type = 'running'
--    GROUP BY is_weekend
--
-- =============================================================================
-- NEXT STEPS
-- =============================================================================
-- 1. Create stg_garmin_health.sql for daily health metrics
-- 2. Create intermediate models that join activities + health
-- 3. Create marts for specific analytics (training, races, health trends)
-- 4. Build Streamlit dashboard to visualize the data
-- =============================================================================