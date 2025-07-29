# Makefile for SentientResearchAgent

.PHONY: help install install-dev run run-debug frontend-dev test clean clean-cache clean-experiments lint format docker-up docker-down

# Default target
help:
	@echo "SentientResearchAgent Development Commands"
	@echo "========================================="
	@echo "install          Install dependencies with PDM"
	@echo "install-dev      Install with development dependencies"
	@echo "run              Run the server"
	@echo "run-debug        Run server in debug mode"
	@echo "frontend-dev     Run frontend development server"
	@echo "test             Run tests"
	@echo "clean            Clean all generated files"
	@echo "clean-cache      Clean agent cache"
	@echo "clean-experiments Clean old experiment results"
	@echo "lint             Run code linting"
	@echo "format           Format code"
	@echo "docker-up        Start Docker services"
	@echo "docker-down      Stop Docker services"

# Installation
install:
	pdm install

install-dev:
	pdm install -d
	cd frontend && npm install

# Running
run:
	python -m sentientresearchagent

run-debug:
	python -m sentientresearchagent --debug

frontend-dev:
	cd frontend && npm run dev

# Testing
test:
	pdm run pytest

test-coverage:
	pdm run pytest --cov=sentientresearchagent --cov-report=html

# Cleaning
clean: clean-cache clean-logs clean-pycache
	@echo "Cleaned cache, logs, and Python artifacts"

clean-pycache:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete

clean-cache:
	rm -rf runtime/cache/
	rm -rf .agent_cache/  # Legacy

clean-logs:
	rm -rf runtime/logs/
	rm -f *.log  # Legacy logs in root

clean-runtime:
	rm -rf runtime/
	@echo "Cleaned all runtime files"

clean-legacy:
	rm -rf .agent_cache/
	rm -rf .agent_projects/
	rm -rf project_results/
	rm -rf emergency_backups/
	rm -f *.log
	@echo "Cleaned legacy directories"

clean-experiments:
	python scripts/clean_old_experiments.py --dry-run

clean-experiments-force:
	python scripts/clean_old_experiments.py

clean-all: clean clean-runtime clean-legacy clean-experiments-force
	@echo "Performed complete cleanup"

# Code quality
lint:
	pdm run ruff check src/

format:
	pdm run ruff format src/
	pdm run ruff check --fix src/

# Docker (delegate to docker/Makefile)
docker-up:
	$(MAKE) -C docker up

docker-down:
	$(MAKE) -C docker down

docker-logs:
	$(MAKE) -C docker logs

docker-build:
	$(MAKE) -C docker build

docker-shell:
	$(MAKE) -C docker shell

docker-clean:
	$(MAKE) -C docker clean

# Development shortcuts
dev: install-dev
	@echo "Development environment ready!"

quick-test:
	python -m sentientresearchagent --config experiments/configs/example_research.yaml

# Logging utilities
logs:
	python scripts/view_logs.py -f

logs-error:
	python scripts/view_logs.py -f -l ERROR

logs-search:
	@read -p "Search pattern: " pattern; \
	python scripts/view_logs.py -f -s "$$pattern"

test-logging:
	python scripts/test_logging.py