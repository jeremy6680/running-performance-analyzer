-- mart_race_performance.sql
-- Purpose: Race-specific performance analysis and PR tracking
-- Grain: One row per race
-- Dependencies: int_unified_activities

{{ config(
    materialized='table',
    tags=['mart', 'racing']
) }}

-- Step 1: Filter for races only and add race context
with races_base as (
    select
        activity_id,
        activity_date,
        activity_type,
        distance_km,
        duration_minutes,
        avg_pace_min_km as pace_min_per_km,  -- Rename for consistency
        avg_heart_rate as avg_heart_rate_bpm,  -- Rename for consistency
        max_heart_rate as max_heart_rate_bpm,  -- Rename for consistency
        elevation_gain_m,
        race_distance_category,
        training_load,
        effort_level,
        
        -- Extract year, month, season for analysis
        extract(year from activity_date) as race_year,
        extract(month from activity_date) as race_month,
        extract(quarter from activity_date) as race_quarter,
        
        -- Season classification (Northern Hemisphere running seasons)
        case
            when extract(month from activity_date) in (1, 2, 12) then 'Winter'
            when extract(month from activity_date) in (3, 4, 5) then 'Spring'
            when extract(month from activity_date) in (6, 7, 8) then 'Summer'
            when extract(month from activity_date) in (9, 10, 11) then 'Fall'
        end as race_season,
        
        -- Race distance in meters for precise calculations
        distance_km * 1000 as distance_meters
        
    from {{ ref('int_unified_activities') }}
    where is_race = true
    order by activity_date
),

-- Step 2: Calculate days since previous race
race_intervals as (
    select
        *,
        -- Days since last race
        activity_date - lag(activity_date, 1) over (order by activity_date) as days_since_last_race,
        
        -- Race number (chronological order)
        row_number() over (order by activity_date) as race_number,
        
        -- Races in current year
        row_number() over (partition by race_year order by activity_date) as race_number_this_year
        
    from races_base
),

-- Step 3: Calculate Personal Records (PRs) per distance category
personal_records as (
    select
        race_distance_category,
        min(duration_minutes) as pr_duration_minutes,
        min(pace_min_per_km) as pr_pace_min_per_km
    from race_intervals
    where race_distance_category is not null
    group by race_distance_category
),

-- Step 4: Calculate training pace context (30 days before race)
training_context as (
    select
        r.activity_id,
        
        -- Average training pace in 30 days before race
        avg(t.avg_pace_min_km) as avg_training_pace_30d,
        
        -- Training volume in 30 days before race
        sum(t.distance_km) as total_training_distance_30d,
        count(*) as training_runs_30d
        
    from race_intervals r
    left join {{ ref('int_unified_activities') }} t
        on t.activity_date between (r.activity_date - interval '30 days') and (r.activity_date - interval '1 day')
        and t.is_race = false
    group by r.activity_id
),

-- Step 5: Calculate race performance metrics
race_metrics as (
    select
        ri.*,
        pr.pr_duration_minutes,
        pr.pr_pace_min_per_km,
        tc.avg_training_pace_30d,
        tc.total_training_distance_30d,
        tc.training_runs_30d,
        
        -- Is this a PR?
        case
            when ri.duration_minutes = pr.pr_duration_minutes then true
            else false
        end as is_personal_record,
        
        -- Time off PR (in minutes)
        ri.duration_minutes - pr.pr_duration_minutes as minutes_off_pr,
        
        -- Percentage off PR
        case
            when pr.pr_duration_minutes > 0 then
                round(((ri.duration_minutes - pr.pr_duration_minutes) / pr.pr_duration_minutes) * 100, 1)
            else null
        end as pct_off_pr,
        
        -- Race pace vs training pace comparison
        case
            when tc.avg_training_pace_30d is not null then
                round(ri.pace_min_per_km - tc.avg_training_pace_30d, 2)
            else null
        end as race_vs_training_pace_diff,
        
        -- Race readiness score (1-10)
        -- Based on: training volume, days since last race, training pace
        case
            when tc.total_training_distance_30d is null then 5 -- No training data
            when tc.total_training_distance_30d >= 100 and 
                 (ri.days_since_last_race is null or ri.days_since_last_race >= 14) then 9
            when tc.total_training_distance_30d >= 80 and 
                 (ri.days_since_last_race is null or ri.days_since_last_race >= 10) then 8
            when tc.total_training_distance_30d >= 60 then 7
            when tc.total_training_distance_30d >= 40 then 6
            else 5
        end as race_readiness_score,
        
        -- Finish time in H:MM:SS format
        -- Cast hours to integer first to avoid '0.0:59:50' float formatting
        cast(floor(ri.duration_minutes / 60) as integer) || ':' ||
        lpad(cast(floor(ri.duration_minutes % 60) as varchar), 2, '0') || ':' ||
        lpad(cast(floor((ri.duration_minutes % 1) * 60) as varchar), 2, '0') as finish_time_formatted
        
    from race_intervals ri
    left join personal_records pr
        on ri.race_distance_category = pr.race_distance_category
    left join training_context tc
        on ri.activity_id = tc.activity_id
),

-- Step 6: Calculate performance trends
performance_trends as (
    select
        *,
        -- Moving average pace (last 3 races of same distance)
        avg(pace_min_per_km) over (
            partition by race_distance_category
            order by activity_date
            rows between 2 preceding and current row
        ) as pace_ma_3_races,
        
        -- Performance trend vs previous race of same distance
        pace_min_per_km - lag(pace_min_per_km, 1) over (
            partition by race_distance_category
            order by activity_date
        ) as pace_change_vs_last,
        
        -- Days since PR at this distance
        activity_date - first_value(activity_date) over (
            partition by race_distance_category, is_personal_record
            order by activity_date
            rows between unbounded preceding and current row
        ) as days_since_pr
        
    from race_metrics
),

-- Step 7: Final output with all calculated fields
final as (
    select
        -- Identifiers
        activity_id as race_id,
        activity_date as race_date,
        race_year,
        race_month,
        race_quarter,
        race_season,
        race_number,
        race_number_this_year,
        
        -- Race details
        race_distance_category,
        round(distance_km, 2) as distance_km,
        round(distance_meters, 0) as distance_meters,
        round(duration_minutes, 1) as duration_minutes,
        finish_time_formatted,
        round(pace_min_per_km, 2) as pace_min_per_km,
        
        -- Performance metrics
        round(avg_heart_rate_bpm, 0) as avg_heart_rate_bpm,
        max_heart_rate_bpm,
        round(elevation_gain_m, 0) as elevation_gain_m,
        round(training_load, 1) as training_load,
        effort_level,
        
        -- PR analysis
        is_personal_record,
        round(pr_duration_minutes, 1) as pr_duration_minutes,
        round(pr_pace_min_per_km, 2) as pr_pace_min_per_km,
        round(minutes_off_pr, 1) as minutes_off_pr,
        pct_off_pr,
        
        -- Training context (30 days before race)
        round(avg_training_pace_30d, 2) as avg_training_pace_30d,
        round(total_training_distance_30d, 1) as total_training_distance_30d,
        training_runs_30d,
        round(race_vs_training_pace_diff, 2) as race_vs_training_pace_diff,
        race_readiness_score,
        
        -- Race intervals
        days_since_last_race,
        
        -- Performance trends
        round(pace_ma_3_races, 2) as pace_ma_3_races,
        round(pace_change_vs_last, 2) as pace_change_vs_last_race,
        
        -- Performance classification
        case
            when is_personal_record then 'PR'
            when pct_off_pr <= 5 then 'Near PR'
            when pct_off_pr <= 10 then 'Good'
            when pct_off_pr <= 20 then 'Fair'
            else 'Off Day'
        end as performance_rating,
        
        -- Pacing strategy assessment
        case
            when race_vs_training_pace_diff < -1.0 then 'Much faster than training'
            when race_vs_training_pace_diff < -0.5 then 'Faster than training'
            when race_vs_training_pace_diff between -0.5 and 0.5 then 'Consistent with training'
            when race_vs_training_pace_diff > 0.5 then 'Slower than training'
            else 'No training data'
        end as pacing_assessment,
        
        -- Race recovery indicator
        case
            when days_since_last_race is null then 'First race'
            when days_since_last_race < 7 then 'Quick turnaround'
            when days_since_last_race between 7 and 14 then 'Standard recovery'
            when days_since_last_race > 14 then 'Well rested'
        end as recovery_status
        
    from performance_trends
)

select * from final
order by race_date desc