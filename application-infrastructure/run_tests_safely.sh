#!/bin/bash

# Safe Test Runner for Lambda Function Separation
# This script prevents system crashes by using virtual environment and running only safe tests

set -e  # Exit on any error

echo "🔒 SAFE TEST EXECUTION - Lambda Function Separation"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "template.yml" ]; then
    echo "❌ Error: Must run from application-infrastructure directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found at ./venv/"
    echo "Create it with: python3 -m venv venv"
    exit 1
fi

echo "✅ Found virtual environment"

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Verify we're using the virtual environment
PYTHON_PATH=$(which python)
if [[ "$PYTHON_PATH" != *"venv"* ]]; then
    echo "❌ Error: Not using virtual environment python"
    echo "Current python: $PYTHON_PATH"
    exit 1
fi

echo "✅ Using virtual environment python: $PYTHON_PATH"

# Check if core dependencies are installed
echo "🔄 Checking dependencies..."
python -c "import pytest" 2>/dev/null || {
    echo "❌ pytest not installed. Installing safe dependencies..."
    pip install pytest==8.3.3 pytest-mock==3.14.0 hypothesis==6.112.1 boto3==1.35.36 botocore==1.35.36
}

echo "✅ Dependencies available"

# Run only safe tests
echo "🧪 Running SAFE tests only..."
echo ""

echo "📋 Running unit tests..."
python -m pytest tests/unit/ -v --tb=short --maxfail=5

echo ""
echo "🔬 Running safe property tests..."
python -m pytest tests/property/test_properties_functional_behavior_preservation.py -v --tb=short --maxfail=3

echo ""
echo "⚠️  SKIPPING integration tests (they make real AWS calls and can crash the system)"
echo "⚠️  SKIPPING resource-heavy property tests (they can overwhelm system resources)"

echo ""
echo "✅ SAFE TEST EXECUTION COMPLETED"
echo "🎉 Lambda function separation tests passed!"

# Deactivate virtual environment
deactivate
echo "✅ Virtual environment deactivated"