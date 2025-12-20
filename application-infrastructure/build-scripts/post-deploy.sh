#!/bin/bash

set -e  # Exit on any error

# Activate virtual environment
source /tmp/build-venv/bin/activate

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run upload-test-files.py with proper path and Python interpreter
echo "Running test file upload utility from post-deploy script"
python "${SCRIPT_DIR}/upload-test-files.py" --environment "${ENVIRONMENT:-staging}" --verbose