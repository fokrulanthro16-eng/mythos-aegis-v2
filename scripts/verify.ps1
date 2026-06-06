# verify.ps1 — Local quality gate for Mythos Aegis (Windows / PowerShell).
#
# Usage:
#   .\scripts\verify.ps1               # lint + types + tests + coverage
#   .\scripts\verify.ps1 --security    # above + dependency audit + SAST + secret scan
#
# Mirrors the checks run in CI so there are no surprises at review time.
param(
    [switch]$Security
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param([string]$Label, [scriptblock]$Block)
    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL $Label" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "PASS $Label" -ForegroundColor Green
}

# ── Core quality checks ────────────────────────────────────────────────────────

Invoke-Step "ruff format check" {
    ruff format --check app/
}

Invoke-Step "ruff lint" {
    ruff check app/
}

Invoke-Step "mypy" {
    mypy app/
}

Invoke-Step "pytest + coverage (>=80%)" {
    pytest `
        --cov=app `
        --cov-report=term-missing `
        --cov-fail-under=80 `
        -q
}

# ── Optional security checks ───────────────────────────────────────────────────

if ($Security) {
    Write-Host ""
    Write-Host "==> Security mode enabled" -ForegroundColor Cyan

    Invoke-Step "pip-audit (dependency CVE scan)" {
        pip-audit --skip-editable --progress-spinner off
    }

    Invoke-Step "bandit (SAST — medium+high severity)" {
        bandit -r app/ -ll -x app/tests/ --format txt
    }

    Invoke-Step "detect-secrets (secret scan)" {
        $scanJson = python -m detect_secrets scan `
            --exclude-files 'app/tests/.*' `
            --exclude-files '\.env\..*' `
            app/ docker-compose.yml 2>$null
        $scanJson | Out-File -Encoding utf8 "$env:TEMP\secrets-scan.json"
        python -c @"
import json, sys
results = json.load(open(r'$env:TEMP\secrets-scan.json', encoding='utf-8-sig')).get('results', {})
for fn, findings in results.items():
    for f in findings:
        print(f'Secret detected: {fn}:{f[\"line_number\"]} ({f[\"type\"]})')
sys.exit(1 if results else 0)
"@
    }
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
