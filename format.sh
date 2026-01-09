#!/bin/bash

# Code Quality Formatting Script
# This script formats the codebase using Black and isort

echo "Running code quality formatting..."
echo ""

echo "1. Formatting code with Black..."
uv run black .
echo ""

echo "2. Sorting imports with isort..."
uv run isort .
echo ""

echo "✅ Code formatting complete!"
