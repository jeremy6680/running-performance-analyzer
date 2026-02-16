# 📚 Marts Documentation Index

This directory contains comprehensive documentation for all gold layer marts in the Running Performance Analyzer project.

---

## 📊 Available Marts

### 1. mart_training_summary

**Weekly training analytics with rolling averages and trends**

- **Guide**: [`mart_training_summary_guide.md`](mart_training_summary_guide.md) - Full implementation guide
- **Quick Ref**: [`mart_training_summary_quickref.md`](mart_training_summary_quickref.md) - Command reference
- **Lineage**: [`mart_training_summary_lineage.md`](mart_training_summary_lineage.md) - Data flow diagram
- **Tests**: 53 (100% passing)
- **Grain**: One row per week

**Key Features**:

- Weekly aggregations (distance, duration, activities)
- 4-week and 8-week rolling averages
- Training load progression
- HR zone distribution
- Week-over-week comparisons

---

### 2. mart_race_performance

**Race-specific performance analysis with PR tracking**

- **Guide**: [`mart_race_performance_guide.md`](mart_race_performance_guide.md) - Full implementation guide
- **Quick Ref**: [`mart_race_performance_quickref.md`](mart_race_performance_quickref.md) - Command reference
- **Tests**: 33 (88% passing)
- **Grain**: One row per race

**Key Features**:

- Personal record (PR) tracking per distance
- Performance ratings (PR, Near PR, Good, Fair, Off Day)
- Training context (30 days before race)
- Race readiness scoring
- Pacing analysis
- Recovery status tracking

---

## 📖 How to Use This Documentation

### If You're New to the Project

1. Start with the **Guide** for each mart to understand:
   - What the mart provides
   - How the SQL works
   - Testing strategy
   - Use cases

2. Reference the **Quick Ref** for:
   - Common queries
   - Command snippets
   - Quick lookups

### If You're Building Dashboards

- Use the **Quick Ref** for copy-paste SQL queries
- Check the **Guide** for Streamlit code examples
- Review available metrics in each mart

### If You're Adding New Marts

- Follow the structure established in existing guides
- Include: Purpose, Features, SQL walkthrough, Tests, Use cases
- Create both a Guide and Quick Reference

---

## 🎯 Quick Access

### Common Tasks

**Run a specific mart:**

```bash
cd dbt_project
dbt run --select mart_training_summary
dbt run --select mart_race_performance
```

**Test a specific mart:**

```bash
dbt test --select mart_training_summary
dbt test --select mart_race_performance
```

**Query marts:**

```bash
duckdb data/duckdb/running_analytics.duckdb
```

```sql
SET schema 'main_gold';
SELECT * FROM mart_training_summary LIMIT 5;
SELECT * FROM mart_race_performance LIMIT 5;
```

---

## 📐 Mart Design Principles

All marts in this project follow these principles:

### 1. Clear Grain

Every mart has a well-defined grain (one row per X):

- `mart_training_summary`: One row per week
- `mart_race_performance`: One row per race

### 2. Business-Focused

Marts answer specific business questions:

- "How's my training volume trending?" → training_summary
- "Am I improving my race times?" → race_performance

### 3. Comprehensive Testing

- Data quality tests (not_null, unique)
- Range validation (accepted_range)
- Business logic tests (accepted_values)

### 4. Self-Documenting

- Descriptive column names
- Comprehensive schema.yml documentation
- Code comments explaining business logic

### 5. Performance Optimized

- Materialized as tables (not views)
- Appropriate use of window functions
- Efficient CTEs instead of nested subqueries

---

## 🔍 Documentation Standards

Each mart should have:

### Full Guide (e.g., `mart_xxx_guide.md`)

- **What it provides** - Overview
- **Key features** - Detailed list
- **How to run** - Commands
- **Understanding the SQL** - Step-by-step walkthrough
- **Key concepts** - SQL patterns explained
- **Sample output** - Example data
- **Testing strategy** - Why each test exists
- **Use cases** - Practical queries
- **Streamlit examples** - Dashboard code
- **Troubleshooting** - Common issues
- **Key takeaways** - Main lessons

### Quick Reference (e.g., `mart_xxx_quickref.md`)

- **Essential commands** - Run, test, query
- **Key metrics** - Available columns
- **Useful queries** - Copy-paste ready
- **SQL patterns** - Common techniques
- **For Streamlit** - Quick code snippets
- **Troubleshooting** - Quick fixes

### Schema Documentation (in `schema_marts.yml`)

- Model description
- Grain definition
- Business logic explanation
- Column descriptions
- Comprehensive tests

---

## 🎓 Learning Path

If you're learning from these marts:

1. **Start with**: `mart_training_summary_guide.md`
   - Simpler logic (weekly aggregations)
   - Clear window function examples
   - Good introduction to rolling averages

2. **Then study**: `mart_race_performance_guide.md`
   - More complex (self-joins, LAG, partitioning)
   - Advanced window functions
   - Multi-table calculations

3. **Practice**: Modify the marts
   - Change time windows (4-week → 8-week)
   - Add new metrics
   - Create new classifications

---

## 🚀 Future Marts

Planned marts for this project:

### mart_health_trends

- **Grain**: One row per day
- **Features**: Sleep quality, HRV, recovery metrics
- **Status**: Not yet created

### mart_ai_features

- **Grain**: Various (week, race, day)
- **Features**: ML features, training readiness, predictions
- **Status**: Not yet created

### mart_monthly_summary

- **Grain**: One row per month
- **Features**: Monthly totals, quarterly comparisons
- **Status**: Not yet created

---

## 📞 Support

- **dbt issues**: Check compiled SQL in `target/compiled/`
- **Test failures**: Review `target/run_results.json`
- **Data issues**: Query staging/intermediate models
- **General questions**: Review the guides in this directory

---

## 📊 Statistics

**Current Documentation**:

- 5 documentation files
- ~3,000 lines of documentation
- 2 marts fully documented
- 86 tests documented
- 60+ example queries
- 10+ Streamlit code examples

---

**Last Updated**: February 16, 2026

**Maintainer**: Jeremy Marchandeau
