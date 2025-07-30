# Dockerfile for SentientResearchAgent with UV for faster builds

# Backend base image
FROM python:3.12-slim AS backend

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install UV for fast Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml pdm.lock* ./
COPY README.md ./

# Convert PDM lock to requirements and install with UV
# This provides compatibility with PDM while using UV's speed
RUN if [ -f pdm.lock ]; then \
        pip install pdm && \
        pdm export -f requirements --without-hashes > requirements.txt && \
        uv pip install --system -r requirements.txt; \
    else \
        uv pip install --system -e .; \
    fi

# Copy source code
COPY src/ ./src/
COPY sentient.yaml ./
COPY emergency_backups/ ./emergency_backups/
COPY project_results/ ./project_results/

# Set Python path
ENV PYTHONPATH=/app/src
ENV FLASK_APP=sentientresearchagent.server.main

# Expose backend port
EXPOSE 5000

# Command to run the backend
CMD ["python", "-m", "sentientresearchagent"]