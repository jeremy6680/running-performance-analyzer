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

# Copy requirements first (for Docker layer caching)
COPY requirements.txt /app/
COPY streamlit_app/requirements.txt /app/streamlit_requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r streamlit_requirements.txt

# Copy application code
COPY streamlit_app/ /app/streamlit_app/
COPY ai_engine/ /app/ai_engine/

# Create data directory (will be mounted as volume)
RUN mkdir -p /app/data/duckdb

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
# - --server.port: Port to listen on
# - --server.address: Bind to all interfaces (required for Docker)
# - --server.headless: Run without opening browser
# - --server.fileWatcherType: Disable file watcher in container
CMD ["streamlit", "run", "streamlit_app/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.fileWatcherType=none"]

# =============================================================================
# USAGE EXAMPLES
# =============================================================================
# 
# Build:
#   docker build -f streamlit_app/Dockerfile -t running-analyzer-streamlit .
# 
# Run standalone (without docker-compose):
#   docker run -d \
#     --name streamlit \
#     -p 8501:8501 \
#     -v $(pwd)/data:/app/data:ro \
#     --env-file .env \
#     running-analyzer-streamlit
# 
# Development mode with live reload:
#   docker run -d \
#     --name streamlit-dev \
#     -p 8501:8501 \
#     -v $(pwd)/streamlit_app:/app/streamlit_app \
#     -v $(pwd)/data:/app/data:ro \
#     --env-file .env \
#     running-analyzer-streamlit
# 
# View logs:
#   docker logs -f streamlit
# 
# Stop:
#   docker stop streamlit && docker rm streamlit
