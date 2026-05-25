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

## Download a sample chapter and run the full pipeline end-to-end (validates your setup)
demo:
	$(PYTEST_ENV) $(PYTHON) run_pipeline.py --url https://www.archive.org/download/pride_and_prejudice_librivox/prideandprejudice_01-03_austen_64kb.mp3

## Run preflight checks (ffmpeg + ollama/groq)
setup:
	$(PYTHON) setup.py

## Run all tests
test:
	$(PYTEST_ENV) $(PYTEST) tests/ -v

## Run pipeline against a local audio sample (writes repository.json + chapters_to_verify.json)
test-pipeline:
	$(PYTEST_ENV) $(PYTHON) run_pipeline.py

## Run pipeline on a chapter URL: make run-chapter URL=https://... [DEBUG=1]
run-chapter:
	$(PYTEST_ENV) $(PYTHON) run_pipeline.py --url $(URL) $(if $(DEBUG),--debug,)

## Run batch processor against data/books.txt
run:
	$(PYTEST_ENV) $(PYTHON) main.py

## Launch verification UI
verify:
	$(PYTEST_ENV) $(PYTHON) -m verify

## Remove generated files
clean:
	rm -f data/repository.json data/chapters_to_verify.json
