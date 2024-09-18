# Create and activate a virtual environment
# Install dependencies in requirements.txt
# Dockerfile should pass hadolint
# app.py should pass pylint
# Integration test included

setup:
	# Create python virtualenv & source it
	rm -rf venv
	python3 -m venv venv
	# Activating virtual environment
	# Note: If you're on Windows, change the source command to: venv\Scripts\activate
	. venv/bin/activate

install:
	# This should be run from inside a virtualenv
	pip install --no-cache-dir --upgrade pip \
	&& pip3 install --no-cache-dir -r requirements.txt
	# Download hadolint for macOS and make it executable
	#curl -L -o ./hadolint https://github.com/hadolint/hadolint/releases/download/v1.16.3/hadolint-Darwin-x86_64 && \
	#chmod +x ./hadolint

test:
	# Additional, optional, tests could go here
	# Integration test: Check if the app runs by simulating a simple request to it.
	#python -m pytest -vv --cov=myrepolib tests/*.py
	#python -m pytest --nbval notebook.ipynb
	python -m unittest discover -s tests

lint:
	# See local hadolint install instructions: https://github.com/hadolint/hadolint
	# This is linter for Dockerfiles
	#./hadolint Dockerfile
	# This is a linter for Python source code linter: https://www.pylint.org/
	# This should be run from inside a virtualenv
	pylint --disable=R,C,W1203 app.py
	pylint --disable=R,C,W1203 functions.py
	pylint --disable=R,C,W1203 tests/test_app.py

integration-test:
	# Integration test to ensure that the app is running properly
	# Simulating a simple request to localhost:8501
	curl --fail http://0.0.0.0:8501 || exit 1

all: setup install lint test integration-test
