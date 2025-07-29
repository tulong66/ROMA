# Dockerfile for SentientResearchAgent with PDM (using uv backend)

# Backend base image
FROM python:3.12-slim AS backend

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install pdm

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml pdm.lock* ./
COPY README.md ./

# Configure PDM to use uv backend
RUN pdm config use_uv true && \
    pdm config python.use_venv false

# Install dependencies
RUN pdm sync --prod

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
CMD ["pdm", "run", "python", "-m", "sentientresearchagent"]