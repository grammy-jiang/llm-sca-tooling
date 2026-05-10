UV ?= uv
UV_CACHE_DIR ?= /tmp/uv-cache
UV_RUN = UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) run --no-sync

.PHONY: verify verify-baseline verify-strict format lint imports type test unit smoke schema-check manifest-regression harness-validate secrets-scan dependency-audit sast compile

verify: lint imports type unit secrets-scan dependency-audit sast schema-check manifest-regression harness-validate

verify-strict: verify

verify-baseline: compile test schema-check manifest-regression harness-validate

format:
	$(UV_RUN) isort .
	$(UV_RUN) black --workers 1 .
	$(UV_RUN) ruff check . --fix

lint:
	$(UV_RUN) isort --check .
	$(UV_RUN) black --check --workers 1 .
	$(UV_RUN) ruff check .

imports:
	$(UV_RUN) lint-imports

type:
	$(UV_RUN) mypy src/

unit:
	$(UV_RUN) pytest tests/unit/ -x

smoke:
	$(UV_RUN) pytest tests/smoke/

test:
	$(UV_RUN) pytest

compile:
	$(UV_RUN) python -m compileall -q src tests

schema-check:
	$(UV_RUN) python -m llm_sca_tooling.schemas.json_schema
	git diff --exit-code schemas

manifest-regression:
	$(UV_RUN) pytest tests/harness

harness-validate:
	@if command -v local-agent-harness >/dev/null 2>&1; then \
		local-agent-harness validate --repo .; \
	else \
		echo "SKIP local-agent-harness validate: command not found"; \
	fi

secrets-scan:
	$(UV_RUN) python -c 'import multiprocessing as mp, sys; mp.set_start_method("fork"); from detect_secrets.main import main; sys.argv=["detect-secrets", "-c", "1", "scan", "--baseline", ".secrets.baseline"]; raise SystemExit(main())'

dependency-audit:
	$(UV_RUN) pip-audit

sast:
	$(UV_RUN) bandit -r src/ -c pyproject.toml --severity-level high
