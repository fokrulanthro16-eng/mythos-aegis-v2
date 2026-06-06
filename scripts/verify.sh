#!/usr/bin/env bash
# verify.sh — Local quality gate for Mythos Aegis.
#
# Usage:
#   ./scripts/verify.sh               # lint + types + tests + coverage
#   ./scripts/verify.sh --security    # above + dependency audit + SAST + secret scan
#
# Mirrors the checks run in CI so there are no surprises at review time.
set -euo pipefail

SECURITY=false
for arg in "$@"; do
  case "$arg" in
    --security) SECURITY=true ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

PASS="\033[0;32mPASS\033[0m"
FAIL="\033[0;31mFAIL\033[0m"
STEP="\033[0;36m==>\033[0m"

run_step() {
  local label="$1"; shift
  echo ""
  echo -e "$STEP $label"
  if "$@"; then
    echo -e "$PASS $label"
  else
    echo -e "$FAIL $label"
    exit 1
  fi
}

# ── Core quality checks ────────────────────────────────────────────────────────

run_step "ruff format check" ruff format --check app/

run_step "ruff lint" ruff check app/

run_step "mypy" mypy app/

run_step "pytest + coverage (≥80%)" \
  pytest \
    --cov=app \
    --cov-report=term-missing \
    --cov-fail-under=80 \
    -q

# ── Optional security checks ───────────────────────────────────────────────────

if $SECURITY; then
  echo ""
  echo -e "$STEP Security mode enabled"

  run_step "pip-audit (dependency CVE scan)" \
    pip-audit --skip-editable --progress-spinner off

  run_step "bandit (SAST — medium+high severity)" \
    bandit -r app/ -ll -x app/tests/ --format txt

  echo ""
  echo -e "$STEP detect-secrets (secret scan)"
  detect-secrets scan \
    --exclude-files 'app/tests/.*' \
    --exclude-files '\.env\..*' \
    app/ docker-compose.yml > /tmp/secrets-scan.json
  python3 - << 'PYEOF'
import json, sys
results = json.load(open("/tmp/secrets-scan.json")).get("results", {})
for fn, findings in results.items():
    for f in findings:
        print(f"Secret detected: {fn}:{f['line_number']} ({f['type']})")
sys.exit(1 if results else 0)
PYEOF
  echo -e "$PASS detect-secrets"
fi

echo ""
echo -e "$PASS All checks passed."
