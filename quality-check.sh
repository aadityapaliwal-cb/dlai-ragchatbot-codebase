#!/bin/bash

# Code Quality Check Script
# This script runs all code quality checks without modifying files

echo "Running code quality checks..."
echo ""

# Track if any checks fail
FAILED=0

echo "1. Checking code formatting with Black..."
if ! uv run black --check .; then
    echo "❌ Black formatting check failed"
    FAILED=1
else
    echo "✅ Black formatting check passed"
fi
echo ""

echo "2. Checking import sorting with isort..."
if ! uv run isort --check-only .; then
    echo "❌ isort check failed"
    FAILED=1
else
    echo "✅ isort check passed"
fi
echo ""

echo "3. Running flake8 linting..."
if ! uv run flake8 .; then
    echo "❌ flake8 linting failed"
    FAILED=1
else
    echo "✅ flake8 linting passed"
fi
echo ""

echo "4. Running mypy type checking..."
if ! uv run mypy backend/ --no-error-summary 2>/dev/null; then
    echo "⚠️  mypy found type issues (non-blocking)"
else
    echo "✅ mypy type checking passed"
fi
echo ""

if [ $FAILED -eq 1 ]; then
    echo "❌ Some quality checks failed. Run ./format.sh to auto-fix formatting issues."
    exit 1
else
    echo "✅ All critical quality checks passed!"
    exit 0
fi
