# Create and activate a virtual environment
# Install dependencies in requirements.txt
# Dockerfile should pass hadolint
# app.py should pass pylint
# Integration test included

VENV := . venv/bin/activate

setup:
	# Remove existing venv if any, and create a new python virtualenv
	rm -rf venv
	python3.9 -m venv venv
	@echo "Virtual environment created."
	# Activating virtual environment and installing dependencies
	@echo "Use 'make install' to install the dependencies."

install: setup
	# Install dependencies inside the virtual environment
	$(VENV) && pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
	@echo "Dependencies installed."

test:
	# Running tests inside the virtual environment
	$(VENV) && python -m unittest discover -s tests
	@echo "Unit tests completed."

lint:
	# Run linters for Dockerfile (hadolint) and Python source code (pylint)
	# Make sure hadolint is installed separately if needed (hadolint linter for Dockerfiles)
	#./hadolint Dockerfile
	# Lint Python files inside the virtual environment
	$(VENV) && pylint --disable=R,C,W1203 app.py
	$(VENV) && pylint --disable=R,C,W1203 functions.py
	$(VENV) && pylint --disable=R,C,W1203 tests/test_app.py
	@echo "Linting completed."

integration-test:
	# Running an integration test by sending a request to the running app
	curl --fail http://0.0.0.0:8501 || exit 1
	@echo "Integration test completed."

# Running everything: setup, install, lint, test, and integration test
all: install lint test integration-test
