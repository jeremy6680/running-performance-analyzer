#!/usr/bin/env python3
"""
Test dbt Connection to DuckDB
==============================
This script verifies that:
1. DuckDB database file exists
2. Bronze tables are accessible
3. dbt profile configuration will work

Run this before running dbt commands to catch issues early.

Usage:
    python test_dbt_connection.py
"""

import sys
from pathlib import Path

# =============================================================================
# Test 1: Check if DuckDB file exists
# =============================================================================
def test_duckdb_exists():
    """Check if the DuckDB database file exists."""
    print("=" * 70)
    print("TEST 1: Checking if DuckDB file exists...")
    print("=" * 70)
    
    db_path = Path("data/duckdb/running_analytics.duckdb")
    
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"✅ PASS: DuckDB file exists")
        print(f"   Location: {db_path.absolute()}")
        print(f"   Size: {size_mb:.2f} MB")
        return True
    else:
        print(f"❌ FAIL: DuckDB file not found")
        print(f"   Expected location: {db_path.absolute()}")
        print(f"   Did you run the ingestion script?")
        print(f"   Run: python -m ingestion.ingest_garmin --days 7")
        return False


# =============================================================================
# Test 2: Check if we can import duckdb
# =============================================================================
def test_duckdb_import():
    """Check if duckdb Python package is installed."""
    print("\n" + "=" * 70)
    print("TEST 2: Checking if duckdb package is installed...")
    print("=" * 70)
    
    try:
        import duckdb
        print(f"✅ PASS: duckdb package installed")
        print(f"   Version: {duckdb.__version__}")
        return True
    except ImportError:
        print(f"❌ FAIL: duckdb package not installed")
        print(f"   Install with: pip install duckdb")
        return False


# =============================================================================
# Test 3: Connect to DuckDB and query bronze tables
# =============================================================================
def test_bronze_tables():
    """Connect to DuckDB and verify bronze tables exist."""
    print("\n" + "=" * 70)
    print("TEST 3: Connecting to DuckDB and checking bronze tables...")
    print("=" * 70)
    
    try:
        import duckdb
        
        db_path = "data/duckdb/running_analytics.duckdb"
        conn = duckdb.connect(db_path, read_only=True)
        
        print(f"✅ Connection successful")
        
        # Check for bronze tables
        tables_query = """
            SELECT table_name, 
                   table_schema,
                   COUNT(*) as estimated_rows
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_type = 'BASE TABLE'
              AND table_name LIKE 'raw_%'
            GROUP BY table_name, table_schema
            ORDER BY table_name;
        """
        
        result = conn.execute(tables_query).fetchall()
        
        if result:
            print(f"✅ PASS: Found {len(result)} bronze tables:")
            print()
            print(f"   {'Table Name':<30} {'Schema':<15} {'Est. Rows':<10}")
            print(f"   {'-' * 30} {'-' * 15} {'-' * 10}")
            
            for table_name, schema, rows in result:
                print(f"   {table_name:<30} {schema:<15} {rows:<10}")
            
            # Get actual row counts for each table
            print("\n   Actual row counts:")
            for table_name, schema, _ in result:
                count_result = conn.execute(
                    f"SELECT COUNT(*) FROM {schema}.{table_name}"
                ).fetchone()
                print(f"   - {table_name}: {count_result[0]} rows")
            
            conn.close()
            return True
        else:
            print(f"❌ FAIL: No bronze tables found (raw_*)")
            print(f"   Expected tables:")
            print(f"   - raw_garmin_activities")
            print(f"   - raw_garmin_daily_health")
            print(f"\n   Did you run the ingestion script?")
            print(f"   Run: python -m ingestion.ingest_garmin --days 7")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ FAIL: Error connecting to DuckDB")
        print(f"   Error: {e}")
        return False


# =============================================================================
# Test 4: Check if dbt is installed
# =============================================================================
def test_dbt_installed():
    """Check if dbt-core and dbt-duckdb are installed."""
    print("\n" + "=" * 70)
    print("TEST 4: Checking if dbt packages are installed...")
    print("=" * 70)
    
    all_installed = True
    
    # Test dbt-core
    try:
        import dbt
        print(f"✅ dbt-core installed")
        # Try to get version using dbt CLI
        import subprocess
        result = subprocess.run(['dbt', '--version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            # Extract version from output
            for line in result.stdout.split('\n'):
                if 'installed:' in line.lower():
                    print(f"   {line.strip()}")
                    break
    except ImportError:
        print(f"❌ dbt-core not installed")
        print(f"   Install with: pip install dbt-core")
        all_installed = False
    except Exception as e:
        print(f"✅ dbt-core installed (version check failed: {e})")
    
    # Test dbt-duckdb adapter
    try:
        import dbt.adapters.duckdb
        print(f"✅ dbt-duckdb installed")
    except ImportError:
        print(f"❌ dbt-duckdb not installed")
        print(f"   Install with: pip install dbt-duckdb")
        all_installed = False
    
    return all_installed


# =============================================================================
# Test 5: Check dbt project files
# =============================================================================
def test_dbt_files():
    """Check if required dbt configuration files exist."""
    print("\n" + "=" * 70)
    print("TEST 5: Checking dbt configuration files...")
    print("=" * 70)
    
    required_files = {
        'dbt_project/dbt_project.yml': 'Main dbt project configuration',
        'profiles.yml': 'Database connection settings'
    }
    
    all_exist = True
    
    for filename, description in required_files.items():
        filepath = Path(filename)
        if filepath.exists():
            print(f"✅ {filename} exists")
            print(f"   Purpose: {description}")
        else:
            print(f"❌ {filename} missing")
            print(f"   Purpose: {description}")
            all_exist = False
    
    return all_exist


# =============================================================================
# Main Test Runner
# =============================================================================
def main():
    """Run all tests and report results."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "dbt Connection Test Suite" + " " * 28 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    tests = [
        ("DuckDB file exists", test_duckdb_exists),
        ("DuckDB package installed", test_duckdb_import),
        ("Bronze tables accessible", test_bronze_tables),
        ("dbt packages installed", test_dbt_installed),
        ("dbt config files exist", test_dbt_files),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 All tests passed! You're ready to run dbt commands.")
        print("\nNext steps:")
        print("  1. cd to your project directory")
        print("  2. Run: dbt debug --profiles-dir .")
        print("  3. Create your first model!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix the issues above before proceeding.")
        print("\nCommon fixes:")
        print("  - Missing packages: pip install -r requirements.txt")
        print("  - No data: python -m ingestion.ingest_garmin --days 7")
        print("  - Config files: Make sure dbt_project.yml and profiles.yml exist")
        return 1


if __name__ == "__main__":
    sys.exit(main())