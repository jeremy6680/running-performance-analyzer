/*
 * Mart: Health Trends
 * Purpose: Track sleep quality, HRV evolution, resting heart rate trends, and recovery metrics
 * Grain: One row per date
 * 
 * Business Logic:
 * - Daily health metrics with trend analysis
 * - Sleep quality patterns (duration, deep sleep, awake time)
 * - Heart rate variability (HRV) tracking for recovery
 * - Resting heart rate trends
 * - Stress and Body Battery analysis
 * - Rolling averages to identify trends
 * - Week-over-week comparisons
 * 
 * Use Cases:
 * - Monitor recovery patterns
 * - Identify sleep quality trends
 * - Track HRV for training readiness
 * - Analyze stress levels over time
 * - Correlate health metrics with training load
 */

with health as (
    select * from {{ ref('stg_garmin_health') }}
),

-- Add week start date for aggregations
health_with_weeks as (
    select
        *,
        -- Calculate week start date (Monday of the week)
        date_trunc('week', health_date) as week_start_date,
        -- Calculate month start date
        date_trunc('month', health_date) as month_start_date,
        -- Day name
        CASE day_of_week
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
            WHEN 0 THEN 'Sunday'
        END as day_name
    from health
),

-- Calculate rolling averages for trend analysis
health_with_trends as (
    select
        health_date,
        day_name,
        week_start_date,
        month_start_date,
        
        -- Sleep metrics
        sleep_hours as total_sleep_hours,
        deep_sleep_hours,
        light_sleep_hours,
        rem_sleep_hours,
        awake_hours,
        sleep_efficiency_pct,
        sleep_quality as sleep_quality_category,
        
        -- Heart rate metrics
        resting_heart_rate,
        min_heart_rate,
        max_heart_rate,
        
        -- HRV and recovery
        hrv_avg,
        hrv_status,
        hrv_category,
        
        -- Stress and energy
        stress_avg as average_stress_level,
        stress_category,
        
        -- Body Battery (Garmin's proprietary recovery metric)
        body_battery_charged,
        body_battery_drained,
        body_battery_high,
        body_battery_low,
        body_battery_net as body_battery_net_change,
        body_battery_status,
        
        -- Activity metrics
        steps as total_steps,
        daily_distance_km,
        
        -- Existing recovery score from staging
        recovery_score as stg_recovery_score,
        
        -- Calculate 7-day rolling averages for sleep
        avg(sleep_hours) over (
            order by health_date 
            rows between 6 preceding and current row
        ) as sleep_7day_avg,
        
        avg(deep_sleep_hours) over (
            order by health_date 
            rows between 6 preceding and current row
        ) as deep_sleep_7day_avg,
        
        -- Calculate 7-day rolling average for RHR
        avg(resting_heart_rate) over (
            order by health_date 
            rows between 6 preceding and current row
        ) as rhr_7day_avg,
        
        -- Calculate 7-day rolling average for stress
        avg(stress_avg) over (
            order by health_date 
            rows between 6 preceding and current row
        ) as stress_7day_avg,
        
        -- Calculate 7-day rolling average for steps
        avg(steps) over (
            order by health_date 
            rows between 6 preceding and current row
        ) as steps_7day_avg,
        
        -- Calculate 28-day rolling averages for longer trends
        avg(sleep_hours) over (
            order by health_date 
            rows between 27 preceding and current row
        ) as sleep_28day_avg,
        
        avg(resting_heart_rate) over (
            order by health_date 
            rows between 27 preceding and current row
        ) as rhr_28day_avg,
        
        -- Previous day metrics for day-over-day comparison
        lag(sleep_hours, 1) over (order by health_date) as prev_day_sleep_hours,
        lag(resting_heart_rate, 1) over (order by health_date) as prev_day_rhr,
        lag(stress_avg, 1) over (order by health_date) as prev_day_stress,
        lag(body_battery_net, 1) over (order by health_date) as prev_day_battery_change,
        
        -- Previous week same day for week-over-week comparison
        lag(sleep_hours, 7) over (order by health_date) as prev_week_sleep_hours,
        lag(resting_heart_rate, 7) over (order by health_date) as prev_week_rhr
        
    from health_with_weeks
),

-- Calculate recovery score and training readiness
health_with_recovery as (
    select
        *,
        
        -- Day-over-day changes
        (total_sleep_hours - prev_day_sleep_hours) as sleep_change_vs_prev_day,
        (resting_heart_rate - prev_day_rhr) as rhr_change_vs_prev_day,
        (average_stress_level - prev_day_stress) as stress_change_vs_prev_day,
        
        -- Week-over-week changes
        (total_sleep_hours - prev_week_sleep_hours) as sleep_change_vs_prev_week,
        (resting_heart_rate - prev_week_rhr) as rhr_change_vs_prev_week,
        
        -- Trend vs rolling averages (positive = better than average)
        (total_sleep_hours - sleep_7day_avg) as sleep_vs_7day_avg,
        (resting_heart_rate - rhr_7day_avg) as rhr_vs_7day_avg,  -- Negative is better (lower RHR)
        (average_stress_level - stress_7day_avg) as stress_vs_7day_avg,  -- Negative is better
        
        -- Calculate enhanced recovery score (0-100)
        -- Based on: sleep quality (40%), RHR deviation (20%), stress (20%), Body Battery (20%)
        -- Higher score = better recovery
        round(
            -- Sleep component (0-40 points): 8 hours = full points
            least(40, (total_sleep_hours / 8.0) * 40) +
            
            -- RHR component (0-20 points): at or below 7-day avg = full points
            case
                when resting_heart_rate is null then 10  -- neutral if no data
                when rhr_7day_avg is null then 10        -- not enough history
                when resting_heart_rate <= rhr_7day_avg then 20
                when resting_heart_rate <= rhr_7day_avg * 1.05 then 15  -- 5% above avg
                when resting_heart_rate <= rhr_7day_avg * 1.10 then 10  -- 10% above avg
                else 5  -- More than 10% above avg
            end +
            
            -- Stress component (0-20 points): lower is better
            case
                when average_stress_level is null then 10  -- neutral if no data
                when average_stress_level <= 25 then 20
                when average_stress_level <= 40 then 15
                when average_stress_level <= 55 then 10
                else 5
            end +
            
            -- Body Battery component (0-20 points): positive net change = full points
            case
                when body_battery_net_change is null then 10  -- neutral if no data
                when body_battery_net_change >= 20 then 20
                when body_battery_net_change >= 10 then 15
                when body_battery_net_change >= 0 then 10
                else 5
            end
        , 0) as recovery_score,
        
        -- Training readiness indicator
        case
            when 
                total_sleep_hours >= 7 
                and (rhr_7day_avg is null or resting_heart_rate <= rhr_7day_avg * 1.05)
                and (average_stress_level is null or average_stress_level <= 40)
                and (body_battery_net_change is null or body_battery_net_change >= 0)
            then 'optimal'
            when 
                total_sleep_hours >= 6 
                and (rhr_7day_avg is null or resting_heart_rate <= rhr_7day_avg * 1.10)
                and (average_stress_level is null or average_stress_level <= 55)
            then 'good'
            when total_sleep_hours >= 5 then 'moderate'
            else 'low'
        end as training_readiness,
        
        -- Sleep debt tracking (assuming 8 hours target)
        round(8.0 - total_sleep_hours, 2) as sleep_debt_hours,
        
        -- Cumulative sleep debt over 7 days
        sum(8.0 - total_sleep_hours) over (
            order by health_date 
            rows between 6 preceding and current row
        ) as sleep_debt_7day_cumulative,
        
        -- Weekly aggregations
        avg(total_sleep_hours) over (
            partition by week_start_date
        ) as week_avg_sleep,
        
        avg(resting_heart_rate) over (
            partition by week_start_date
        ) as week_avg_rhr,
        
        avg(average_stress_level) over (
            partition by week_start_date
        ) as week_avg_stress,
        
        sum(total_steps) over (
            partition by week_start_date
        ) as week_total_steps
        
    from health_with_trends
)

select
    -- Identifiers
    health_date as date,
    day_name as day_of_week,
    week_start_date,
    month_start_date,
    
    -- Sleep metrics
    total_sleep_hours,
    deep_sleep_hours,
    light_sleep_hours,
    rem_sleep_hours,
    awake_hours,
    sleep_quality_category,
    sleep_efficiency_pct,
    sleep_debt_hours,
    sleep_debt_7day_cumulative,
    
    -- Sleep trends
    sleep_7day_avg,
    sleep_28day_avg,
    sleep_change_vs_prev_day,
    sleep_change_vs_prev_week,
    sleep_vs_7day_avg,
    
    -- Heart rate metrics
    resting_heart_rate,
    min_heart_rate,
    max_heart_rate,
    
    -- RHR trends
    rhr_7day_avg,
    rhr_28day_avg,
    rhr_change_vs_prev_day,
    rhr_change_vs_prev_week,
    rhr_vs_7day_avg,
    
    -- HRV metrics
    hrv_avg as hrv_numeric,
    hrv_status,
    hrv_category,
    
    -- Stress metrics
    average_stress_level,
    stress_category,
    
    -- Stress trends
    stress_7day_avg,
    stress_change_vs_prev_day,
    stress_vs_7day_avg,
    
    -- Body Battery
    body_battery_charged,
    body_battery_drained,
    body_battery_high,
    body_battery_low,
    body_battery_net_change,
    body_battery_status,
    
    -- Activity metrics
    total_steps,
    daily_distance_km as total_distance_km,
    steps_7day_avg,
    
    -- Recovery score and readiness
    recovery_score,
    stg_recovery_score,  -- Keep the staging recovery score for comparison
    training_readiness,
    
    -- Weekly aggregations
    week_avg_sleep,
    week_avg_rhr,
    week_avg_stress,
    week_total_steps

from health_with_recovery
order by date desc
