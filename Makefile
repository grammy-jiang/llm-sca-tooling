# Makefile — LLM-SCA tooling
# All verify-path commands use `uv run --frozen` to prevent lockfile mutations.
# Run `uv sync` once after cloning to install dev dependencies.
# Run `pre-commit install` once after cloning to activate git hooks.
#
# Quiet scanners (detect-secrets, pip-audit, bandit) may run silently for
# several minutes; this is normal. Each phase emits [verify] start/done lines
# with elapsed time so operators can distinguish "scanning" from "hung".
# Soft timeout: 10 min per scanner phase. Hard timeout: 15 min.

.PHONY: verify verify-format verify-lint-imports verify-types verify-tests \
        verify-security verify-dirty verify-fast verify-docs \
        release-gate \
        fmt fmt-check lint-check \
        _lint_imports _typecheck _test_unit _test_harness secrets _pip_audit _sast \
        test test-harness harness-check harness-report install help

# ---------------------------------------------------------------------------
# verify — full pre-commit gate; must pass before every commit.
# Split into named phases so a stalled phase is immediately visible in output.
# ---------------------------------------------------------------------------
verify: verify-format verify-lint-imports verify-types verify-tests verify-security verify-dirty ## Run the full verify-before-commit gate
	@echo ""
	@echo "verify: all gates passed"

# ---------------------------------------------------------------------------
# Named phase targets — run individually for faster iteration or debugging.
# ---------------------------------------------------------------------------

verify-format: ## Phase: formatting — isort, black, ruff
	@_T=$$(date +%s); echo "[verify] start format"; \
	 uv run --frozen isort --check . && \
	 uv run --frozen black --check . && \
	 uv run --frozen ruff check .; \
	 _S=$$?; echo "[verify] done  format elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

verify-lint-imports: ## Phase: import contracts — lint-imports (skips if src/ absent)
	@_T=$$(date +%s); echo "[verify] start lint-imports"; \
	 if [ -d src ]; then \
	     uv run --frozen lint-imports; _S=$$?; \
	 else \
	     echo "lint-imports: skipping — src/ not yet created (Phase 0)"; _S=0; \
	 fi; \
	 echo "[verify] done  lint-imports elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

verify-types: ## Phase: type-checking — mypy strict (skips if src/ absent)
	@_T=$$(date +%s); echo "[verify] start mypy"; \
	 if [ -d src ]; then \
	     uv run --frozen mypy src/; _S=$$?; \
	 else \
	     echo "mypy: skipping — src/ not yet created (Phase 0)"; _S=0; \
	 fi; \
	 echo "[verify] done  mypy elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

verify-tests: ## Phase: tests — unit then harness (each skips if directory absent)
	@_T=$$(date +%s); echo "[verify] start tests"; _S=0; \
	 if [ -d tests/unit ]; then \
	     uv run --frozen pytest tests/unit/ -x || _S=$$?; \
	 else \
	     echo "pytest unit: skipping — tests/unit/ not yet created (Phase 0)"; \
	 fi; \
	 if [ $$_S -eq 0 ] && [ -d tests/harness ]; then \
	     uv run --frozen pytest tests/harness/ -x || _S=$$?; \
	 elif [ ! -d tests/harness ]; then \
	     echo "pytest harness: skipping — tests/harness/ not yet created"; \
	 fi; \
	 echo "[verify] done  tests elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

verify-security: ## Phase: security — detect-secrets, pip-audit, bandit (in sequence)
	@$(MAKE) --no-print-directory secrets
	@$(MAKE) --no-print-directory _pip_audit
	@$(MAKE) --no-print-directory _sast

verify-dirty: ## Post-verify guard: assert that no tracked files were mutated
	@echo "[verify] start dirty-check"; \
	 if git diff --exit-code --quiet -- uv.lock .secrets.baseline 2>/dev/null; then \
	     echo "[verify] done  dirty-check: no tracked files mutated"; \
	 else \
	     echo "[verify] ERROR: verify mutated tracked file(s):"; \
	     git diff --name-only -- uv.lock .secrets.baseline; \
	     echo "  Run: git restore uv.lock .secrets.baseline"; \
	     exit 1; \
	 fi

# ---------------------------------------------------------------------------
# Fast iteration targets — NOT a replacement for full verify.
# Use for tight edit/check loops; always run full verify before committing.
# ---------------------------------------------------------------------------

verify-fast: verify-format verify-lint-imports verify-types ## Fast gate: format + imports + types; skips security and tests

verify-docs: verify-format ## Docs-only precheck: formatting only

# ---------------------------------------------------------------------------
# release-gate — full Phase 18 gate against in-repo T3/T4 fixtures.
# Not part of `make verify` (which gates every commit) — run before tagging
# a release. Writes the report under .agent/eval/runs/<ts>/.
# ---------------------------------------------------------------------------

release-gate: ## Run the Phase 18 release gate against in-repo fixtures
	@_T=$$(date +%s); _TS=$$(date -u +%Y%m%dT%H%M%SZ); \
	 _DIR=.agent/eval/runs/$$_TS; \
	 _REPORT=$$_DIR/release_gate_report.json; \
	 mkdir -p "$$_DIR"; \
	 echo "[release-gate] start ts=$$_TS"; \
	 uv run --frozen llm-sca-tooling release-gate \
	     --suite all --fail-on-any \
	     --report-out "$$_REPORT"; \
	 _S=$$?; \
	 if [ $$_S -eq 0 ]; then \
	     echo "[release-gate] done  report=$$_REPORT elapsed=$$(($$(date +%s)-$$_T))s"; \
	 else \
	     echo "[release-gate] FAILED — see $$_REPORT"; \
	 fi; \
	 exit $$_S

# ---------------------------------------------------------------------------
# fmt — auto-format (modifies files)
# ---------------------------------------------------------------------------

fmt: ## Auto-format: isort then black
	uv run isort .
	uv run black .

fmt-check: ## Check formatting without modifying files
	uv run isort --check .
	uv run black --check .

lint-check: ## Run ruff linter
	uv run ruff check .

# ---------------------------------------------------------------------------
# Security sub-steps (called by verify-security; also usable standalone)
# ---------------------------------------------------------------------------

secrets: ## Non-mutating detect-secrets check: scan to temp file, compare to baseline
	@_T=$$(date +%s); echo "[verify] start detect-secrets"; \
	 _TMP=$$(mktemp --suffix=.json); \
	 uv run --frozen detect-secrets scan --exclude-files '^\.secrets\.baseline$$' > "$$_TMP" 2>&1; \
	 python3 -c "import json,sys; \
n=json.load(open(sys.argv[1])).get('results',{}); \
o=json.load(open(sys.argv[2])).get('results',{}); \
oh={s['hashed_secret'] for sl in o.values() for s in sl}; \
bad=[(f,s['type']) for f,sl in n.items() for s in sl if s['hashed_secret'] not in oh]; \
(print('detect-secrets: new secret(s) not in baseline: '+str(bad),file=sys.stderr), sys.exit(1)) if bad \
else print('detect-secrets: ok — scanned '+str(len(n))+' file(s), all potential secrets in baseline')" \
	 "$$_TMP" .secrets.baseline; \
	 _S=$$?; rm -f "$$_TMP"; \
	 echo "[verify] done  detect-secrets elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

_pip_audit:
	@_T=$$(date +%s); echo "[verify] start pip-audit"; \
	 if [ -f uv.lock ]; then \
	     uv run --frozen pip-audit; _S=$$?; \
	 else \
	     echo "pip-audit: skipping — uv.lock not yet generated (run uv sync)"; _S=0; \
	 fi; \
	 echo "[verify] done  pip-audit elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

_sast:
	@_T=$$(date +%s); echo "[verify] start bandit"; \
	 if [ -d src ]; then \
	     uv run --frozen bandit -r src/ -c pyproject.toml --severity-level medium; _S=$$?; \
	 else \
	     echo "bandit: skipping — src/ not yet created (Phase 0)"; _S=0; \
	 fi; \
	 echo "[verify] done  bandit elapsed=$$(($$(date +%s)-$$_T))s"; exit $$_S

# ---------------------------------------------------------------------------
# Legacy internal aliases (kept for backward compatibility; delegate to phases)
# ---------------------------------------------------------------------------

_lint_imports:
	@$(MAKE) --no-print-directory verify-lint-imports

_typecheck:
	@$(MAKE) --no-print-directory verify-types

_test_unit:
	@if [ -d tests/unit ]; then \
		uv run --frozen pytest tests/unit/ -x; \
	else \
		echo "pytest unit: skipping — tests/unit/ not yet created (Phase 0)"; \
	fi

_test_harness:
	@if [ -d tests/harness ]; then \
		uv run --frozen pytest tests/harness/ -x; \
	else \
		echo "pytest harness: skipping — tests/harness/ not yet created"; \
	fi

# ---------------------------------------------------------------------------
# Developer convenience
# ---------------------------------------------------------------------------

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
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
