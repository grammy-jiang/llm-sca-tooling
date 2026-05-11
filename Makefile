# Makefile — LLM-SCA tooling
# All commands use `uv run` per project convention.
# Run `uv sync` once after cloning to install dev dependencies.
# Run `pre-commit install` once after cloning to activate git hooks.

.PHONY: verify fmt lint typecheck test test-harness secrets audit sast \
        harness-check harness-report install help

# ---------------------------------------------------------------------------
# verify — full pre-commit gate; must pass before every commit
# Steps that require Phase 0+ artefacts (src/, tests/unit/) skip gracefully.
# ---------------------------------------------------------------------------
verify: fmt-check lint-check ## Run the full verify-before-commit gate
	@$(MAKE) --no-print-directory _lint_imports
	@$(MAKE) --no-print-directory _typecheck
	@$(MAKE) --no-print-directory _test_unit
	@$(MAKE) --no-print-directory _test_harness
	@$(MAKE) --no-print-directory secrets
	@$(MAKE) --no-print-directory _pip_audit
	@$(MAKE) --no-print-directory _sast
	@echo ""
	@echo "verify: all gates passed"

fmt: ## Auto-format: isort then black
	uv run isort .
	uv run black .

fmt-check: ## Check formatting without modifying files
	uv run isort --check .
	uv run black --check .

lint-check: ## Run ruff linter
	uv run ruff check .

_lint_imports:
	@if [ -d src ]; then \
		echo "lint-imports: checking architectural contracts..."; \
		uv run lint-imports; \
	else \
		echo "lint-imports: skipping — src/ not yet created (Phase 0)"; \
	fi

_typecheck:
	@if [ -d src ]; then \
		echo "mypy: type-checking src/..."; \
		uv run mypy src/; \
	else \
		echo "mypy: skipping — src/ not yet created (Phase 0)"; \
	fi

_test_unit:
	@if [ -d tests/unit ]; then \
		uv run pytest tests/unit/ -x; \
	else \
		echo "pytest unit: skipping — tests/unit/ not yet created (Phase 0)"; \
	fi

_test_harness:
	@if [ -d tests/harness ]; then \
		uv run pytest tests/harness/ -x; \
	else \
		echo "pytest harness: skipping — tests/harness/ not yet created"; \
	fi

secrets: ## Run detect-secrets scan against baseline
	uv run detect-secrets scan --baseline .secrets.baseline

_pip_audit:
	@if [ -f uv.lock ]; then \
		uv run pip-audit; \
	else \
		echo "pip-audit: skipping — uv.lock not yet generated (run uv sync)"; \
	fi

_sast:
	@if [ -d src ]; then \
		uv run bandit -r src/ -c pyproject.toml --severity-level medium; \
	else \
		echo "bandit: skipping — src/ not yet created (Phase 0)"; \
	fi

test: ## Run all tests
	uv run pytest tests/ -x

test-harness: ## Run harness non-relaxation tests only
	uv run pytest tests/harness/ -x -v

harness-check: ## Audit harness manifests for drift
	local-agent-harness check --repo .

harness-report: ## Refresh the AI-readiness report
	local-agent-harness report --repo . --out .agent/eval/readiness.md
	local-agent-harness report --repo . --check-no-regression .agent/eval/readiness.md

install: ## Install dev dependencies and activate git hooks
	uv sync
	pre-commit install
	@echo ""
	@echo "Dev environment ready. Run 'make verify' to check the full gate."

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
