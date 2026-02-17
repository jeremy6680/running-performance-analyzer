-- mart_training_summary.sql
-- Purpose: Weekly training summary with rolling averages and trends
-- Grain: One row per week
-- Dependencies: int_unified_activities

-- Configuration: This is a materialized view that will be rebuilt on each dbt run
{{ config(
    materialized='table',
    tags=['mart', 'training']
) }}

-- Step 1: Define weeks dimension
-- Create a spine of weeks that have RUNNING activity data, starting from Monday.
-- Filter to activity_type = 'running' so non-running activity types (walks,
-- cycling, strength) do not create phantom weeks in this running-focused mart.
with weeks_spine as (
    select distinct
        -- Get Monday of the week for each activity
        date_trunc('week', activity_date) as week_start_date,
        extract(year from date_trunc('week', activity_date)) as year,
        extract(week from date_trunc('week', activity_date)) as week_number
    from {{ ref('int_unified_activities') }}
    where activity_date is not null
      and activity_type = 'running'  -- Running weeks only
),

-- Step 2: Aggregate activities by week
-- Filter to activity_type = 'running' so all metrics (distance, pace, HR, load)
-- reflect running only. Without this filter, a walk or cycling session would
-- distort avg_pace_min_per_km, avg_heart_rate_bpm, and total_training_load.
weekly_aggregates as (
    select
        date_trunc('week', activity_date) as week_start_date,
        
        -- Count metrics
        -- total_activities = total RUNNING sessions this week (non-runs excluded)
        count(*) as total_activities,
        count(case when is_race then 1 end) as total_races,
        
        -- Distance metrics
        sum(distance_km) as total_distance_km,
        avg(distance_km) as avg_distance_per_activity_km,
        max(distance_km) as max_distance_km,
        
        -- Duration metrics  
        sum(duration_minutes) as total_duration_minutes,
        avg(duration_minutes) as avg_duration_per_activity_minutes,
        
        -- Pace metrics (weighted average by distance)
        sum(avg_pace_min_km * distance_km) / nullif(sum(distance_km), 0) as avg_pace_min_per_km,
        
        -- Heart rate metrics (only for activities with HR data)
        avg(case when avg_heart_rate is not null then avg_heart_rate end) as avg_heart_rate_bpm,
        max(max_heart_rate) as max_heart_rate_bpm,

        -- Elevation metrics
        sum(elevation_gain_m) as total_elevation_gain_m,
        avg(elevation_gain_m) as avg_elevation_per_activity_m,

        -- Effort metrics
        avg(case effort_level when 'easy' then 1.0 when 'moderate' then 2.0 when 'hard' then 3.0 end) as avg_effort_level,
        sum(training_load) as total_training_load,

        -- Heart rate zone distribution (percentage of activities in each zone)
        avg(case when hr_zone = 'zone_1_recovery' then 1.0 else 0.0 end) as pct_zone1,
        avg(case when hr_zone = 'zone_2_base' then 1.0 else 0.0 end) as pct_zone2,
        avg(case when hr_zone = 'zone_3_tempo' then 1.0 else 0.0 end) as pct_zone3,
        avg(case when hr_zone = 'zone_4_threshold' then 1.0 else 0.0 end) as pct_zone4,
        avg(case when hr_zone = 'zone_5_vo2max' then 1.0 else 0.0 end) as pct_zone5
        
    from {{ ref('int_unified_activities') }}
    where activity_date is not null
      and activity_type = 'running'  -- Running activities only: prevents walks,
                                     -- cycling or strength sessions from distorting
                                     -- pace, HR, distance and training load metrics
    group by 1
),

-- Step 3: Calculate rolling averages using window functions
rolling_metrics as (
    select
        week_start_date,
        total_activities,
        total_races,
        total_distance_km,
        avg_distance_per_activity_km,
        max_distance_km,
        total_duration_minutes,
        avg_duration_per_activity_minutes,
        avg_pace_min_per_km,
        avg_heart_rate_bpm,
        max_heart_rate_bpm,
        total_elevation_gain_m,
        avg_elevation_per_activity_m,
        avg_effort_level,
        total_training_load,
        pct_zone1,
        pct_zone2,
        pct_zone3,
        pct_zone4,
        pct_zone5,
        
        -- 4-week rolling averages (current week + 3 previous weeks)
        avg(total_distance_km) over (
            order by week_start_date
            rows between 3 preceding and current row
        ) as rolling_4wk_avg_distance_km,
        
        avg(total_activities) over (
            order by week_start_date
            rows between 3 preceding and current row
        ) as rolling_4wk_avg_activities,
        
        avg(total_duration_minutes) over (
            order by week_start_date
            rows between 3 preceding and current row
        ) as rolling_4wk_avg_duration_minutes,
        
        avg(total_training_load) over (
            order by week_start_date
            rows between 3 preceding and current row
        ) as rolling_4wk_avg_training_load,
        
        -- 8-week rolling averages (current week + 7 previous weeks)
        avg(total_distance_km) over (
            order by week_start_date
            rows between 7 preceding and current row
        ) as rolling_8wk_avg_distance_km,
        
        avg(total_activities) over (
            order by week_start_date
            rows between 7 preceding and current row
        ) as rolling_8wk_avg_activities,
        
        avg(total_duration_minutes) over (
            order by week_start_date
            rows between 7 preceding and current row
        ) as rolling_8wk_avg_duration_minutes,
        
        avg(total_training_load) over (
            order by week_start_date
            rows between 7 preceding and current row
        ) as rolling_8wk_avg_training_load,
        
        -- Previous week metrics for comparison
        lag(total_distance_km, 1) over (order by week_start_date) as prev_week_distance_km,
        lag(total_activities, 1) over (order by week_start_date) as prev_week_activities,
        lag(avg_pace_min_per_km, 1) over (order by week_start_date) as prev_week_avg_pace
        
    from weekly_aggregates
),

-- Step 4: Calculate percentage changes and trends
final as (
    select
        w.week_start_date,
        w.year,
        w.week_number,
        -- Create a readable week label
        'Week ' || w.week_number || ', ' || w.year as week_label,
        
        -- Weekly totals
        r.total_activities,
        r.total_races,
        r.total_distance_km,
        r.avg_distance_per_activity_km,
        r.max_distance_km,
        r.total_duration_minutes,
        r.avg_duration_per_activity_minutes,
        round(r.avg_pace_min_per_km, 2) as avg_pace_min_per_km,
        round(r.avg_heart_rate_bpm, 0) as avg_heart_rate_bpm,
        r.max_heart_rate_bpm,
        r.total_elevation_gain_m,
        round(r.avg_elevation_per_activity_m, 0) as avg_elevation_per_activity_m,
        round(r.avg_effort_level, 1) as avg_effort_level,
        round(r.total_training_load, 1) as total_training_load,
        
        -- Heart rate zone distribution (as percentages)
        round(r.pct_zone1 * 100, 1) as pct_zone1_easy,
        round(r.pct_zone2 * 100, 1) as pct_zone2_moderate,
        round(r.pct_zone3 * 100, 1) as pct_zone3_tempo,
        round(r.pct_zone4 * 100, 1) as pct_zone4_threshold,
        round(r.pct_zone5 * 100, 1) as pct_zone5_max,
        
        -- 4-week rolling averages
        round(r.rolling_4wk_avg_distance_km, 2) as rolling_4wk_avg_distance_km,
        round(r.rolling_4wk_avg_activities, 1) as rolling_4wk_avg_activities,
        round(r.rolling_4wk_avg_duration_minutes, 0) as rolling_4wk_avg_duration_minutes,
        round(r.rolling_4wk_avg_training_load, 1) as rolling_4wk_avg_training_load,
        
        -- 8-week rolling averages
        round(r.rolling_8wk_avg_distance_km, 2) as rolling_8wk_avg_distance_km,
        round(r.rolling_8wk_avg_activities, 1) as rolling_8wk_avg_activities,
        round(r.rolling_8wk_avg_duration_minutes, 0) as rolling_8wk_avg_duration_minutes,
        round(r.rolling_8wk_avg_training_load, 1) as rolling_8wk_avg_training_load,
        
        -- Comparison metrics (percentage change)
        -- vs Previous Week
        round(
            case 
                when r.prev_week_distance_km > 0 
                then ((r.total_distance_km - r.prev_week_distance_km) / r.prev_week_distance_km) * 100
                else null
            end, 
            1
        ) as distance_vs_prev_week_pct,
        
        round(
            case 
                when r.prev_week_activities > 0 
                then ((r.total_activities - r.prev_week_activities) / cast(r.prev_week_activities as float)) * 100
                else null
            end, 
            1
        ) as activities_vs_prev_week_pct,
        
        -- vs 4-Week Average
        round(
            case 
                when r.rolling_4wk_avg_distance_km > 0 
                then ((r.total_distance_km - r.rolling_4wk_avg_distance_km) / r.rolling_4wk_avg_distance_km) * 100
                else null
            end, 
            1
        ) as distance_vs_4wk_avg_pct,
        
        -- Trend indicators (simple flags for dashboard)
        case
            when r.total_distance_km > r.rolling_4wk_avg_distance_km then 'Increasing'
            when r.total_distance_km < r.rolling_4wk_avg_distance_km then 'Decreasing'
            else 'Stable'
        end as distance_trend_4wk,
        
        case
            when r.total_training_load > r.rolling_4wk_avg_training_load then 'Increasing'
            when r.total_training_load < r.rolling_4wk_avg_training_load then 'Decreasing'
            else 'Stable'
        end as training_load_trend_4wk
        
    from weeks_spine as w
    left join rolling_metrics as r
        on w.week_start_date = r.week_start_date
)

select * from final
order by week_start_date desc