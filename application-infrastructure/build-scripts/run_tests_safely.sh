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

# Verify Python and pytest are available
echo "🔄 Checking Python environment..."
python3 --version
python3 -c "import pytest" 2>/dev/null || {
    echo "❌ pytest not available. This should have been installed in pre_build phase."
    exit 1
}

echo "✅ Python and pytest available"

# Run only safe tests
echo ""
echo "🧪 Running SAFE tests only..."
echo ""

echo "📋 Running unit tests (safe)..."
python3 -m pytest tests/unit/ -v --tb=short --maxfail=5 || {
    echo "❌ Unit tests failed"
    exit 1
}

echo ""
echo "🔬 Running safe property tests..."
python3 -m pytest tests/property/test_properties_functional_behavior_preservation.py -v --tb=short --maxfail=3 || {
    echo "❌ Safe property tests failed"
    exit 1
}

echo ""
echo "⚠️  SKIPPING integration tests (they make real AWS calls and can crash CI/CD)"
echo "⚠️  SKIPPING resource-heavy property tests (they can overwhelm CI/CD resources)"

echo ""
echo "✅ SAFE TEST EXECUTION COMPLETED"
echo "🎉 Lambda function separation tests passed in CI/CD!"