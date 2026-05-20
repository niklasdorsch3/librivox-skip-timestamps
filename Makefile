PYTHON     = .venv/bin/python3
PYTEST     = PYTHONPATH=. $(PYTHON) -m pytest
PYTEST_ENV = PYTHONPATH=.

-include .env
export

.PHONY: venv setup test run verify test-pipeline clean

## Create virtualenv and install dependencies
venv:
	python3.10 -m venv .venv
	.venv/bin/pip install -r requirements.txt requests static-ffmpeg pytest

## Run preflight checks (ffmpeg + ollama/groq)
setup:
	$(PYTHON) setup.py

## Run all tests
test:
	$(PYTEST_ENV) $(PYTEST) tests/ -v

## Run pipeline against a local audio sample (writes repository.json + chapters_to_verify.json)
test-pipeline:
	$(PYTEST_ENV) $(PYTHON) run_pipeline.py

## Run batch processor against books.txt
run:
	$(PYTEST_ENV) $(PYTHON) main.py

## Launch verification UI
verify:
	$(PYTEST_ENV) $(PYTHON) verify.py

## Remove generated files
clean:
	rm -f repository.json chapters_to_verify.json progress.txt
