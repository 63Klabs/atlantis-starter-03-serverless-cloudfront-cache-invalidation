#!/bin/bash

# Safe Test Runner for Lambda Function Separation - CI/CD Version
# This script prevents CI/CD crashes by running only safe tests
# Designed for use in AWS CodeBuild environments

set -e  # Exit on any error

echo "🔒 SAFE TEST EXECUTION - CI/CD Pipeline"
echo "========================================"

# Check if we're in the right directory (should be application-infrastructure)
if [ ! -f "template.yml" ]; then
    echo "❌ Error: Must run from application-infrastructure directory"
    echo "Current directory: $(pwd)"
    echo "Files in current directory:"
    ls -la
    exit 1
fi

echo "✅ Found template.yml - in correct directory"

# Check if tests directory exists
if [ ! -d "tests" ]; then
    echo "❌ Error: tests directory not found"
    exit 1
fi

echo "✅ Found tests directory"

# Activate virtual environment if it exists
if [ -f "/tmp/build-venv/bin/activate" ]; then
    echo "🔄 Activating virtual environment..."
    source /tmp/build-venv/bin/activate
    echo "✅ Virtual environment activated"
    PYTHON_CMD="python"
else
    echo "⚠️  Virtual environment not found, using system Python"
    PYTHON_CMD="python3"
fi

# Verify Python and pytest are available
echo "🔄 Checking Python environment..."
$PYTHON_CMD --version
which $PYTHON_CMD
$PYTHON_CMD -c "import pytest" 2>/dev/null || {
    echo "❌ pytest not available. This should have been installed in pre_build phase."
    exit 1
}

echo "✅ Python and pytest available"

# Debug Python path and environment
echo "🔍 Debugging Python environment..."
echo "PYTHONPATH: $PYTHONPATH"
echo "Python sys.path:"
$PYTHON_CMD -c "import sys; print('\n'.join(sys.path))"
echo "Current working directory: $(pwd)"
echo "Contents of current directory:"
ls -la

# Run only safe tests
echo ""
echo "🧪 Running SAFE tests only..."
echo ""

echo "🔍 Testing basic imports before running tests..."
$PYTHON_CMD -c "
try:
    from functions.processor.path_consolidator import consolidate_paths
    print('✅ path_consolidator import successful')
except Exception as e:
    print(f'❌ path_consolidator import failed: {e}')
    import traceback
    traceback.print_exc()
    exit(1)
"

echo "📋 Running unit tests (safe)..."
$PYTHON_CMD -m pytest tests/unit/ -v --tb=short --maxfail=5 || {
    echo "❌ Unit tests failed"
    exit 1
}

echo ""
echo "🔬 Running safe property tests..."
$PYTHON_CMD -m pytest tests/property/test_properties_functional_behavior_preservation.py -v --tb=short --maxfail=3 || {
    echo "❌ Safe property tests failed"
    exit 1
}

echo ""
echo "⚠️  SKIPPING integration tests (they make real AWS calls and can crash CI/CD)"
echo "⚠️  SKIPPING resource-heavy property tests (they can overwhelm CI/CD resources)"

echo ""
echo "✅ SAFE TEST EXECUTION COMPLETED"
echo "🎉 Lambda function separation tests passed in CI/CD!"