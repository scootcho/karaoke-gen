# Makefile for karaoke-gen project
# Run `make help` to see available commands

.PHONY: help test test-unit test-backend test-integration test-e2e test-all lint clean emulators-start emulators-stop

# Default target
help:
	@echo "Available commands:"
	@echo "  make test           - Run all tests (unit + backend + emulator-based)"
	@echo "  make test-unit      - Run unit tests only (karaoke_gen)"
	@echo "  make test-backend   - Run backend unit tests only"
	@echo "  make test-e2e       - Run E2E tests with emulators (starts/stops automatically)"
	@echo "  make test-all       - Alias for 'make test'"
	@echo "  make lint           - Run linter checks"
	@echo "  make emulators-start - Start GCP emulators for local development"
	@echo "  make emulators-stop  - Stop GCP emulators"
	@echo ""
	@echo "Before committing, run: make test"

# Run unit tests for karaoke_gen package
test-unit:
	@echo "=== Running karaoke_gen unit tests ==="
	poetry run pytest tests/unit/ -v --cov=karaoke_gen --cov-report=term-missing --cov-fail-under=69

# Run backend unit tests
test-backend:
	@echo "=== Running backend unit tests ==="
	poetry run pytest backend/tests/ --ignore=backend/tests/emulator -v

# Run E2E integration tests with emulators
test-e2e:
	@echo "=== Running E2E integration tests with emulators ==="
	@./scripts/start-emulators.sh || (echo "Failed to start emulators" && exit 1)
	@export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 && \
	export STORAGE_EMULATOR_HOST=http://127.0.0.1:4443 && \
	export GOOGLE_CLOUD_PROJECT=test-project && \
	export GCS_BUCKET_NAME=test-bucket && \
	export ADMIN_TOKENS=test-admin-token && \
	export ENVIRONMENT=test && \
	poetry run pytest backend/tests/emulator/ -v; \
	TEST_RESULT=$$?; \
	./scripts/stop-emulators.sh; \
	exit $$TEST_RESULT

# Run all tests (use this before committing!)
test: test-unit test-backend test-e2e
	@echo ""
	@echo "✅ All tests passed! Ready to commit."

# Alias for test
test-all: test

# Lint checks
lint:
	@echo "=== Running lint checks ==="
	poetry run ruff check karaoke_gen/ backend/
	poetry run ruff format --check karaoke_gen/ backend/

# Start emulators for local development
emulators-start:
	@echo "=== Starting GCP emulators ==="
	./scripts/start-emulators.sh

# Stop emulators
emulators-stop:
	@echo "=== Stopping GCP emulators ==="
	./scripts/stop-emulators.sh

# Clean up temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml 2>/dev/null || true
	@echo "Cleaned up temporary files"

