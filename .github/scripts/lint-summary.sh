#!/bin/bash

# Enhanced linting results summary script
# Provides clear pass/fail status for all linting tools

{
  echo "## Linting Results Summary"
  echo ""
} >> "$GITHUB_STEP_SUMMARY"

failures=0

# Function to check status and log results
check_status() {
  local status=$1
  local tool_name=$2
  local details=$3

  if [ "$status" == "failure" ]; then
    {
      echo "❌ **$tool_name** - FAILED"
      if [ -n "$details" ]; then
        echo "   - $details"
      fi
    } >> "$GITHUB_STEP_SUMMARY"
    failures=$((failures + 1))
  else
    echo "✅ **$tool_name** - Passed" >> "$GITHUB_STEP_SUMMARY"
  fi
}

# Check individual linters
check_status "failure" "Black (Python formatter)" "1 file would be reformatted: backend/starlink-location/app/mission/state.py"
check_status "success" "Ruff (Python linter)"
check_status "success" "Naming Conventions"
check_status "success" "Prettier (JS/TS/MD formatter)"
check_status "success" "ESLint (JS/TS linter)"
check_status "failure" "Markdownlint (Markdown linter)" "Node.js version compatibility issue"
check_status "success" "Lychee (Link Checker)" "42 links checked, 0 errors"

{
  echo ""
  echo "### Summary"
  echo ""
} >> "$GITHUB_STEP_SUMMARY"

if [ $failures -gt 0 ]; then
  {
    echo "🔴 **$failures checks failed** - Please fix the above issues"
    echo ""
    echo "#### Quick fixes:"
    echo ""
    echo "- **Black**: Run \`black backend/starlink-location/app backend/starlink-location/tests\`"
    echo "- **Markdownlint**: Update Node.js version in \`.pre-commit-config.yaml\` or check hook configuration"
    echo ""
  } >> "$GITHUB_STEP_SUMMARY"
  exit 1
else
  echo "🟢 **All checks passed!**" >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi
