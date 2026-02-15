# dbt Setup Guide - Step by Step

# ================================

## 🎯 Goal

Set up dbt with the correct file structure for your running analytics project.

## 📂 Final Structure (What We're Building)

```
running-performance-analyzer/
│
├── profiles.yml                    # Database connection (project root)
├── test_dbt_connection.py          # Test script (project root)
│
├── dbt_project/                    # All dbt files go HERE
│   ├── dbt_project.yml             # Main dbt config
│   ├── models/                     # SQL models (we'll create these next)
│   ├── macros/                     # Reusable functions
│   ├── tests/                      # Custom tests
│   └── seeds/                      # Reference data CSVs
│
├── data/
│   └── duckdb/
│       └── running_analytics.duckdb  # Your existing database
│
└── (other project folders: ingestion/, streamlit_app/, etc.)
```

## 📝 Step-by-Step Instructions

### Step 1: Install dbt Packages

```bash
# Make sure you're in your project root
cd /path/to/running-performance-analyzer

# Activate your virtual environment
source venv/bin/activate  # Or however you activate it

# Install dbt-core and DuckDB adapter
pip install dbt-core dbt-duckdb

# Verify installation
dbt --version
# Should show: Core 1.7.x and duckdb plugin
```

### Step 2: Create dbt_project Directory Structure

```bash
# From project root
mkdir -p dbt_project/models/{staging,intermediate,marts}
mkdir -p dbt_project/macros
mkdir -p dbt_project/tests
mkdir -p dbt_project/seeds
```

### Step 3: Place Configuration Files

Download these 3 files from Claude and place them:

1. **dbt_project.yml** → Goes in `dbt_project/dbt_project.yml`
2. **profiles.yml** → Goes in project root `profiles.yml`
3. **test_dbt_connection.py** → Goes in project root `test_dbt_connection.py`

```bash
# Your structure should look like:
running-performance-analyzer/
├── profiles.yml              # ← HERE
├── test_dbt_connection.py    # ← HERE
└── dbt_project/
    └── dbt_project.yml       # ← HERE
```

### Step 4: Test Connection

```bash
# From project root, run the test script
python test_dbt_connection.py

# Expected output:
# ✅ PASS: DuckDB file exists
# ✅ PASS: duckdb package installed
# ✅ PASS: Bronze tables accessible
# ✅ PASS: dbt packages installed
# ✅ PASS: dbt config files exist
```

### Step 5: Test dbt Itself

```bash
# From project root, run dbt debug
# This tells dbt to look for profiles.yml in current directory
dbt debug --project-dir dbt_project --profiles-dir .

# Expected output:
# Configuration:
#   profiles.yml file [OK found and valid]
#   dbt_project.yml file [OK found and valid]
#
# Connection:
#   database: running_analytics
#   schema: main
#   path: data/duckdb/running_analytics.duckdb
#   Connection test: [OK connection ok]
```

## 🎯 How to Run dbt Commands

**Always run dbt commands from your project root:**

```bash
# From: /path/to/running-performance-analyzer/

# Run all models
dbt run --project-dir dbt_project --profiles-dir .

# Run specific model
dbt run --project-dir dbt_project --profiles-dir . --select stg_garmin_activities

# Run tests
dbt test --project-dir dbt_project --profiles-dir .

# Generate docs
dbt docs generate --project-dir dbt_project --profiles-dir .
dbt docs serve --project-dir dbt_project --profiles-dir .
```

## 🔑 Key Points

1. **profiles.yml location**: Project root (where you run commands)
2. **dbt_project.yml location**: Inside `dbt_project/` folder
3. **Database path**: Relative to project root (`data/duckdb/running_analytics.duckdb`)
4. **Run commands**: Always from project root with `--project-dir dbt_project --profiles-dir .`

## ❓ Why This Structure?

- **profiles.yml in root**: Can be shared across multiple dbt projects
- **dbt_project/ folder**: Keeps dbt files organized and separate from ingestion/streamlit code
- **Relative paths**: Makes project portable (works on any machine)

## ✅ You're Ready When...

You see this output from `dbt debug`:

```
All checks passed!
```

Then come back to Claude and say: "dbt connection working! Ready for sources.yml"
