#!/usr/bin/env python3
"""
Simple validation script for mart_training_summary
Queries the mart directly from DuckDB (no SQL file needed)
"""

import duckdb
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "duckdb" / "running_analytics.duckdb"

def validate_mart():
    """Query and display mart_training_summary data"""
    
    print("=" * 80)
    print("MART TRAINING SUMMARY - VALIDATION")
    print("=" * 80)
    print()
    
    # Check if database exists
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        print("Please run: python -m ingestion.ingest_garmin --days 7")
        return
    
    print(f"✅ Database found: {DB_PATH}")
    print()
    
    # Connect to DuckDB
    conn = duckdb.connect(str(DB_PATH))
    
    try:
        # Check if mart exists (try both schemas)
        marts_check = conn.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_name = 'mart_training_summary'
        """).fetchall()
        
        if not marts_check:
            print("❌ mart_training_summary not found!")
            print()
            print("Available tables:")
            tables = conn.execute("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_schema NOT LIKE 'information_schema'
                ORDER BY table_schema, table_name
            """).fetchall()
            for schema, table in tables:
                print(f"  - {schema}.{table}")
            print()
            print("💡 Run: cd dbt_project && dbt run")
            return
        
        # Get schema name
        schema_name = marts_check[0][0]
        print(f"✅ Mart found in schema: {schema_name}")
        print()
        
        # Query the mart
        query = f"""
            SELECT 
                week_start_date,
                week_label,
                total_activities,
                total_races,
                total_distance_km,
                avg_distance_per_activity_km,
                total_duration_minutes,
                avg_pace_min_per_km,
                avg_heart_rate_bpm,
                max_heart_rate_bpm,
                total_elevation_gain_m,
                total_training_load,
                rolling_4wk_avg_distance_km,
                rolling_4wk_avg_activities,
                rolling_4wk_avg_training_load,
                distance_vs_prev_week_pct,
                distance_vs_4wk_avg_pct,
                distance_trend_4wk,
                training_load_trend_4wk
            FROM {schema_name}.mart_training_summary
            ORDER BY week_start_date DESC
        """
        
        result = conn.execute(query).fetchdf()
        
        if len(result) == 0:
            print("⚠️  Mart exists but contains no data")
            print("💡 Check if you have activities in stg_garmin_activities")
            return
        
        print(f"✅ Found {len(result)} weeks of training data")
        print()
        print("=" * 80)
        print("RECENT TRAINING SUMMARY (Last 3 Weeks)")
        print("=" * 80)
        print()
        
        # Display last 3 weeks
        for idx, row in result.head(3).iterrows():
            print(f"📅 {row['week_label']} ({row['week_start_date'].strftime('%Y-%m-%d')})")
            print(f"   Activities: {row['total_activities']}", end="")
            if row['total_races'] > 0:
                print(f" ({row['total_races']} races)", end="")
            print()
            
            print(f"   Distance: {row['total_distance_km']:.2f} km " +
                  f"(avg {row['avg_distance_per_activity_km']:.2f} km/activity)")
            print(f"   Duration: {row['total_duration_minutes']:.0f} min")
            print(f"   Pace: {row['avg_pace_min_per_km']:.2f} min/km")
            
            if row['avg_heart_rate_bpm'] is not None and str(row['avg_heart_rate_bpm']) != 'nan':
                print(f"   Heart Rate: {row['avg_heart_rate_bpm']:.0f} bpm " +
                      f"(max {row['max_heart_rate_bpm']:.0f})")
            
            print(f"   Elevation: {row['total_elevation_gain_m']:.0f} m")
            print(f"   Training Load: {row['total_training_load']:.1f}")
            print()
            
            # Rolling averages
            print(f"   📊 4-Week Rolling Averages:")
            print(f"      Distance: {row['rolling_4wk_avg_distance_km']:.2f} km/week")
            print(f"      Activities: {row['rolling_4wk_avg_activities']:.1f}/week")
            print(f"      Training Load: {row['rolling_4wk_avg_training_load']:.1f}")
            print()
            
            # Comparisons
            if str(row['distance_vs_prev_week_pct']) != 'nan':
                direction = "↑" if row['distance_vs_prev_week_pct'] > 0 else "↓"
                print(f"   📈 vs Previous Week: {direction} {abs(row['distance_vs_prev_week_pct']):.1f}%")
            
            if str(row['distance_vs_4wk_avg_pct']) != 'nan':
                direction = "↑" if row['distance_vs_4wk_avg_pct'] > 0 else "↓"
                print(f"   📈 vs 4-Week Avg: {direction} {abs(row['distance_vs_4wk_avg_pct']):.1f}%")
            
            print(f"   🎯 Trends: Distance {row['distance_trend_4wk']}, " +
                  f"Load {row['training_load_trend_4wk']}")
            print()
            print("-" * 80)
            print()
        
        # Summary statistics
        print("=" * 80)
        print("OVERALL STATISTICS")
        print("=" * 80)
        print()
        print(f"📅 Weeks tracked: {len(result)}")
        print(f"🏃 Total activities: {result['total_activities'].sum():.0f}")
        print(f"📏 Total distance: {result['total_distance_km'].sum():.2f} km")
        print(f"⏱️  Total duration: {result['total_duration_minutes'].sum():.0f} min " +
              f"({result['total_duration_minutes'].sum() / 60:.1f} hours)")
        print()
        print(f"📊 Weekly averages:")
        print(f"   Distance: {result['total_distance_km'].mean():.2f} km/week")
        print(f"   Activities: {result['total_activities'].mean():.1f}/week")
        print(f"   Training Load: {result['total_training_load'].mean():.1f}")
        print()
        print(f"🏆 Peak week:")
        peak_week = result.loc[result['total_distance_km'].idxmax()]
        print(f"   {peak_week['week_label']}: {peak_week['total_distance_km']:.2f} km " +
              f"({peak_week['total_activities']:.0f} activities)")
        print()
        
        print("=" * 80)
        print("✅ VALIDATION COMPLETE!")
        print("=" * 80)
        print()
        print("🎯 Next steps:")
        print(f"  1. Query in DuckDB: SET schema '{schema_name}'; SELECT * FROM mart_training_summary;")
        print("  2. Commit to Git: git add dbt_project/ scripts/")
        print("  3. Build Streamlit dashboard or create more marts")
        print()
        
    except Exception as e:
        print(f"❌ Error querying mart: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("💡 Try running: cd dbt_project && dbt run")
        
    finally:
        conn.close()

if __name__ == "__main__":
    validate_mart()