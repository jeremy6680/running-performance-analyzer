# Running Performance Analyzer - Streamlit Dockerfile
#
# Build image: docker build -f streamlit_app/Dockerfile -t running-analyzer-streamlit .
# Run container: docker run -p 8501:8501 --env-file .env running-analyzer-streamlit

FROM python:3.11-slim

# Metadata
LABEL maintainer="Your Name <your.email@example.com>"
LABEL description="Running Performance Analyzer - Streamlit Dashboard"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
# - gcc, g++: Required for compiling some Python packages
# - curl: Healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY the Streamlit-specific requirements (not the global requirements.txt
# which includes Airflow, dbt, stravalib etc. — not needed here and causes conflicts)
COPY streamlit_app/requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
# Note: ingestion/ is copied so that pages can import DuckDBManager.
# The full ingestion pipeline is NOT run inside Streamlit —
# only the database read layer (duckdb_manager.py) is used here.
COPY streamlit_app/ /app/streamlit_app/
COPY ai_engine/ /app/ai_engine/
COPY ingestion/ /app/ingestion/

# Make /app the Python root so that `from ingestion.x import y` and
# `from ai_engine.x import y` both resolve correctly
ENV PYTHONPATH=/app

# Create data directory (will be mounted as volume at runtime by docker-compose)
# The DuckDB file lands at /app/data/running_analytics.duckdb
RUN mkdir -p /app/data

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
# NOTE: filename has NO emoji — renamed from 0_Dashboard.py (emoji removed for Docker compat)
CMD ["streamlit", "run", "streamlit_app/0_Dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none"]