#!/usr/bin/env python3
"""
Validation script for mart_training_summary
This simulates what dbt would produce by executing the SQL directly on DuckDB
"""

import duckdb
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent / "data" / "duckdb" / "running_analytics.duckdb"

def validate_mart_training_summary():
    """
    Execute the mart_training_summary SQL and display results
    """
    print("=" * 80)
    print("MART TRAINING SUMMARY - VALIDATION")
    print("=" * 80)
    print()
    
    # Check if database exists
    if not DB_PATH.exists():
        print(f"❌ Database not found at: {DB_PATH}")
        print("Please run ingestion first to create the database.")
        return
    
    # Connect to DuckDB
    conn = duckdb.connect(str(DB_PATH))
    
    # First, check if int_unified_activities exists
    tables = conn.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'main'
    """).fetchall()
    
    print("Available tables:")
    for table in tables:
        print(f"  - {table[0]}")
    print()
    
    # Read the SQL file
    sql_path = Path(__file__).parent / "dbt_project" / "models" / "marts" / "mart_training_summary.sql"
    
    with open(sql_path, 'r') as f:
        sql_content = f.read()
    
    # Remove dbt-specific syntax (refs, config)
    # Replace {{ ref('int_unified_activities') }} with int_unified_activities
    sql_clean = sql_content.replace("{{ ref('int_unified_activities') }}", "int_unified_activities")
    
    # Remove config block
    import re
    sql_clean = re.sub(r'{{\s*config\([^}]+\)\s*}}', '', sql_clean)
    
    # Remove any remaining {{ }} blocks
    sql_clean = re.sub(r'{{[^}]+}}', '', sql_clean)
    
    print("🔄 Executing mart_training_summary SQL...")
    print()
    
    try:
        # Execute the query
        result = conn.execute(sql_clean).fetchdf()
        
        if len(result) == 0:
            print("⚠️  No data returned - check if int_unified_activities has data")
            return
        
        print(f"✅ Successfully generated {len(result)} weeks of data")
        print()
        print("=" * 80)
        print("SAMPLE OUTPUT (Most Recent 3 Weeks)")
        print("=" * 80)
        print()
        
        # Display last 3 weeks
        sample = result.head(3)
        
        for idx, row in sample.iterrows():
            print(f"📅 {row['week_label']} ({row['week_start_date']})")
            print(f"   Activities: {row['total_activities']} ({row['total_races']} races)")
            print(f"   Distance: {row['total_distance_km']:.2f} km (avg {row['avg_distance_per_activity_km']:.2f} km/run)")
            print(f"   Duration: {row['total_duration_minutes']:.0f} min (avg {row['avg_duration_per_activity_minutes']:.0f} min/run)")
            print(f"   Pace: {row['avg_pace_min_per_km']:.2f} min/km")
            
            if row['avg_heart_rate_bpm'] is not None:
                print(f"   Heart Rate: {row['avg_heart_rate_bpm']:.0f} bpm (max {row['max_heart_rate_bpm']:.0f})")
            
            print(f"   Elevation: {row['total_elevation_gain_m']:.0f} m (avg {row['avg_elevation_per_activity_m']:.0f} m/run)")
            print(f"   Training Load: {row['total_training_load']:.1f}")
            print()
            
            # Rolling averages
            print(f"   4-Week Rolling Avg:")
            print(f"     Distance: {row['rolling_4wk_avg_distance_km']:.2f} km")
            print(f"     Activities: {row['rolling_4wk_avg_activities']:.1f}")
            print(f"     Training Load: {row['rolling_4wk_avg_training_load']:.1f}")
            print()
            
            # Comparisons
            if row['distance_vs_prev_week_pct'] is not None:
                direction = "↑" if row['distance_vs_prev_week_pct'] > 0 else "↓"
                print(f"   vs Previous Week: {direction} {abs(row['distance_vs_prev_week_pct']):.1f}% distance")
            
            if row['distance_vs_4wk_avg_pct'] is not None:
                direction = "↑" if row['distance_vs_4wk_avg_pct'] > 0 else "↓"
                print(f"   vs 4-Week Avg: {direction} {abs(row['distance_vs_4wk_avg_pct']):.1f}% distance")
            
            print(f"   Trend: Distance {row['distance_trend_4wk']}, Load {row['training_load_trend_4wk']}")
            print()
            print("-" * 80)
            print()
        
        # Summary statistics
        print("=" * 80)
        print("SUMMARY STATISTICS (All Weeks)")
        print("=" * 80)
        print()
        print(f"Total weeks tracked: {len(result)}")
        print(f"Average weekly distance: {result['total_distance_km'].mean():.2f} km")
        print(f"Average activities per week: {result['total_activities'].mean():.1f}")
        print(f"Peak weekly distance: {result['total_distance_km'].max():.2f} km")
        print(f"Peak weekly training load: {result['total_training_load'].max():.1f}")
        print()
        
        # Heart rate zone distribution (if available)
        if result['avg_heart_rate_bpm'].notna().any():
            print("Average HR Zone Distribution:")
            print(f"  Zone 1 (Easy): {result['pct_zone1_easy'].mean():.1f}%")
            print(f"  Zone 2 (Moderate): {result['pct_zone2_moderate'].mean():.1f}%")
            print(f"  Zone 3 (Tempo): {result['pct_zone3_tempo'].mean():.1f}%")
            print(f"  Zone 4 (Threshold): {result['pct_zone4_threshold'].mean():.1f}%")
            print(f"  Zone 5 (Max): {result['pct_zone5_max'].mean():.1f}%")
            print()
        
        # Column list for reference
        print("=" * 80)
        print("ALL COLUMNS AVAILABLE IN MART")
        print("=" * 80)
        print()
        for col in result.columns:
            print(f"  - {col}")
        
        print()
        print("✅ Validation complete!")
        print()
        print("📊 Next steps:")
        print("  1. On your local machine, run: cd dbt_project && dbt run --select mart_training_summary")
        print("  2. Then run tests: dbt test --select mart_training_summary")
        print("  3. Check the output in your DuckDB database")
        
    except Exception as e:
        print(f"❌ Error executing SQL: {e}")
        print()
        print("This might be because:")
        print("  1. int_unified_activities doesn't exist yet (run dbt run first)")
        print("  2. There's a SQL syntax error")
        print("  3. Missing columns in source data")
        
    finally:
        conn.close()

if __name__ == "__main__":
    validate_mart_training_summary()