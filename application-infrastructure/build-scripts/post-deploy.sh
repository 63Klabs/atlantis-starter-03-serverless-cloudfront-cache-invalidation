#!/bin/bash

set -e  # Exit on any error

# Debug information
echo "=== POST-DEPLOY.SH DEBUG INFO ==="
echo "Running post-deploy.sh"
echo "Current working directory: $(pwd)"
echo "PATH: $PATH"
echo "VIRTUAL_ENV: $VIRTUAL_ENV"

# Check Python environment
echo "=== PYTHON ENVIRONMENT ==="
echo "Python version: $(python --version)"
echo "Which python: $(which python)"
echo "Python executable: $(python -c 'import sys; print(sys.executable)')"

# Check pip and installed packages
echo "=== PIP ENVIRONMENT ==="
echo "Which pip: $(which pip)"
echo "Pip version: $(pip --version)"
echo "Installed packages:"
pip list

# Check if boto3 is available
echo "=== BOTO3 CHECK ==="
echo "Checking boto3 availability..."
python -c "import boto3; print(f'boto3 version: {boto3.__version__}')" || echo "boto3 not available"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Script directory: ${SCRIPT_DIR}"

# Check if the upload script exists
if [ -f "${SCRIPT_DIR}/upload-test-files.py" ]; then
    echo "Found upload-test-files.py at ${SCRIPT_DIR}/upload-test-files.py"
else
    echo "ERROR: upload-test-files.py not found at ${SCRIPT_DIR}/upload-test-files.py"
    ls -la "${SCRIPT_DIR}/"
    exit 1
fi

# Run upload-test-files.py with proper path and Python interpreter
echo "=== RUNNING UPLOAD UTILITY ==="
echo "Running test file upload utility from post-deploy script"
python "${SCRIPT_DIR}/upload-test-files.py" --stages "stage,prod" --verbose