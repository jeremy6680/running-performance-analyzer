-- =============================================================================
-- STAGING MODEL: Garmin Calendar Events (Silver Layer)
-- =============================================================================
-- Purpose:
--   Clean and expose race events stored in the Garmin Connect calendar.
--   These are races the user has registered for via the Garmin Connect app.
--
-- Key difference vs stg_garmin_activities:
--   stg_garmin_activities = PAST races you've actually run (from activity data)
--   stg_garmin_calendar_events = ALL races you plan to run (from calendar)
--
-- Some events may have already been completed (event_date < today).
-- For those, an activity record may exist in stg_garmin_activities to join to.
--
-- Grain: One row per calendar race event (keyed on event_uuid)
--
-- Materialization: VIEW (fast to rebuild, feeds marts and AI coach)
--
-- Dependencies:
--   - Bronze layer: raw_garmin_calendar_events (populated by ingest_garmin.py)
--
-- Downstream usage:
--   - mart_race_performance: join to enrich past race results with calendar context
--   - AI Coach: provide upcoming race schedule to Claude for training advice
--
-- Author: Jeremy Marchandeau
-- Created: 2026-02-18
-- =============================================================================

WITH source AS (

    -- Pull all calendar race events from the bronze layer
    SELECT * FROM {{ source('garmin', 'raw_garmin_calendar_events') }}

),

enriched AS (

    SELECT
        -- -----------------------------------------------------------------------
        -- Identifiers
        -- -----------------------------------------------------------------------
        event_uuid,                        -- Stable UUID from Garmin Connect
        title,                             -- Event title (e.g. 'Cannes Half Marathon')

        -- -----------------------------------------------------------------------
        -- Date & Timing
        -- -----------------------------------------------------------------------
        event_date,                        -- Race date (DATE type)

        -- Extract temporal dimensions for grouping / filtering
        EXTRACT(YEAR  FROM event_date) AS event_year,
        EXTRACT(MONTH FROM event_date) AS event_month,

        -- Days from today to race date (negative = past, positive = upcoming)
        -- Useful for the AI coach: "next race in X days"
        CAST(event_date AS DATE) - CAST(CURRENT_DATE AS DATE) AS days_until_race,

        -- Boolean flag: is the race still in the future?
        CASE
            WHEN event_date >= CURRENT_DATE THEN TRUE
            ELSE FALSE
        END AS is_upcoming,

        -- Season bucket: matches mart_race_performance for easy joining
        CASE
            WHEN EXTRACT(MONTH FROM event_date) IN (3, 4, 5)  THEN 'Spring'
            WHEN EXTRACT(MONTH FROM event_date) IN (6, 7, 8)  THEN 'Summer'
            WHEN EXTRACT(MONTH FROM event_date) IN (9, 10, 11) THEN 'Fall'
            ELSE 'Winter'
        END AS race_season,

        -- Start time and timezone (can be NULL for events without time info)
        start_time,                        -- HH:MM string (e.g. '08:30')
        timezone,                          -- IANA timezone (e.g. 'Europe/Paris')

        -- -----------------------------------------------------------------------
        -- Location
        -- -----------------------------------------------------------------------
        location,                          -- City/country from Garmin (e.g. 'Cannes, FR')

        -- -----------------------------------------------------------------------
        -- Distance
        -- -----------------------------------------------------------------------
        distance_m,                        -- Official distance in metres
        distance_km,                       -- Official distance in kilometres

        -- Race distance category (already computed in connector, kept as-is)
        -- Values: '5K' | '10K' | 'Half Marathon' | 'Marathon' | 'Ultra' | NULL
        race_distance_category,

        -- -----------------------------------------------------------------------
        -- Status Flags
        -- -----------------------------------------------------------------------
        is_race,                           -- Always TRUE (only race events stored)
        subscribed,                        -- User is subscribed to this event on Garmin

        -- -----------------------------------------------------------------------
        -- External URL
        -- -----------------------------------------------------------------------
        url,                               -- Link to race page (from partner sites)

        -- -----------------------------------------------------------------------
        -- Audit Fields
        -- -----------------------------------------------------------------------
        inserted_at AS loaded_at,
        updated_at

    FROM source

)

-- -----------------------------------------------------------------------
-- FINAL OUTPUT
-- -----------------------------------------------------------------------
-- Return all events, sorted by date ascending (soonest first).
-- Downstream models can filter on is_upcoming to see only future races.
SELECT * FROM enriched
ORDER BY event_date ASC
