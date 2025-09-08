.PHONY: help test coverage lint format clean install dev-install run docker-build docker-run

# Default target
help:
	@echo "Available targets:"
	@echo "  help         - Show this help message"
	@echo "  install      - Install package and dependencies"
	@echo "  dev-install  - Install package in development mode with test dependencies"
	@echo "  test         - Run tests"
	@echo "  coverage     - Run tests with coverage report"
	@echo "  lint         - Run linting (flake8, mypy)"
	@echo "  format       - Format code (black, isort)"
	@echo "  clean        - Clean build artifacts and cache"
	@echo "  run          - Run the application"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"

# Install package and dependencies
install:
	pip install -e .

# Install in development mode with test dependencies
dev-install:
	pip install -e ".[test]"
	pip install black isort flake8 mypy

# Run tests
test:
	pytest

# Run tests with coverage
coverage:
	pytest --cov=src/ws/prometheus_uptimerobot --cov-report=html --cov-report=term-missing

# Run formatter
format:
	black src tests
	isort src tests

# Run linting
lint:
	flake8 --ignore=E501,W503 src tests
	mypy --install-types
	mypy src

# Clean build artifacts and cache
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Run the application (requires API key in environment)
run:
	python src/ws/prometheus_uptimerobot/web.py --config config.ini

# Build Docker image
docker-build:
	docker build -t prometheus-uptimerobot .

# Run Docker container (requires API key in environment)
docker-run:
	docker run --rm -p 9429:9429 -e UPTIMEROBOT_API_KEY="$(UPTIMEROBOT_API_KEY)" prometheus-uptimerobot

# Run all quality checks
check: lint test

# Run tests in different Python versions (if available)
test-all:
	tox || echo "tox not available, running single version tests"
	$(MAKE) test
