PY ?= python3.12
PY := $(shell command -v $(PY) 2>/dev/null || echo python3)

.PHONY: run test lint smoke audit demo verify clean

run:
	$(PY) run.py

test:
	$(PY) -m pytest -q

lint:
	ruff check .
	$(PY) -m compileall -q h2studio tools tests

smoke:
	$(PY) tools/smoke.py

audit:
	$(PY) tools/button_audit.py

demo:
	$(PY) tools/e2e.py

verify: lint test smoke audit
	@echo "All local gates passed."
