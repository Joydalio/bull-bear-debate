#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

claude plugin marketplace add DietrichGebert/ponytail >/dev/null 2>&1 || true
claude plugin install ponytail@ponytail >/dev/null 2>&1 || true
