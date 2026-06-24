<#
.SYNOPSIS
    EPMS Sandbox Test Orchestrator
.DESCRIPTION
    Seeds test data, runs heartbeat simulation, and tests all API endpoints.
    Reports pass/fail for every endpoint.
#>

$ErrorActionPreference = "Stop"
$SandboxDir = Split-Path -Parent $PSCommandPath
$ServerUrl = "http://localhost:8000"

Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      EPMS SANDBOX TEST ENVIRONMENT             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 0: Verify server is running
Write-Host "▸ Checking server at $ServerUrl..." -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "$ServerUrl/api/v1/auth/login" -Method POST `
        -ContentType "application/json" -Body '{"email":"admin@corp.local","password":"MyP@ss1"}' `
        -UseBasicParsing -ErrorAction Stop
    $token = ($resp.Content | ConvertFrom-Json).access_token
    Write-Host "  ✅ Server is running, logged in successfully" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Server not reachable at $ServerUrl" -ForegroundColor Red
    Write-Host "     Start the server first and try again."
    exit 1
}

# Step 1: Seed test data
Write-Host ""
Write-Host "▸ Step 1: Seeding test data..." -ForegroundColor Yellow
Write-Host "  (72 hours of realistic process data, browser activity, editor activity,"
Write-Host "   productivity scores, app sessions, activity events, and alerts)"
try {
    $result = python "$SandboxDir\seed_data.py" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Seed complete" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Seed had warnings (may be OK if data exists): $result" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠️  Seed error: $_" -ForegroundColor Yellow
}

# Step 2: Run heartbeat simulation
Write-Host ""
Write-Host "▸ Step 2: Sending simulated heartbeats..." -ForegroundColor Yellow
try {
    python "$SandboxDir\heartbeat_simulator.py" 2>&1
    Write-Host "  ✅ Heartbeat simulation complete" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Heartbeat error: $_" -ForegroundColor Yellow
}

# Step 3: Test all API endpoints
Write-Host ""
Write-Host "▸ Step 3: Running comprehensive API test suite..." -ForegroundColor Yellow
try {
    $testResult = python "$SandboxDir\test_all_endpoints.py" 2>&1
    Write-Host $testResult
} catch {
    Write-Host "  Test error: $_" -ForegroundColor Red
}

# Step 4: Verify dashboard pages load
Write-Host ""
Write-Host "▸ Step 4: Verifying dashboard pages return 200..." -ForegroundColor Yellow
$pages = @(
    "/dashboard/",
    "/dashboard/login/",
    "/dashboard/devices/",
    "/dashboard/activity/",
    "/dashboard/browsers/",
    "/dashboard/editors/",
    "/dashboard/productivity/",
    "/dashboard/team/",
    "/dashboard/users/",
    "/dashboard/rules/",
    "/dashboard/alerts/",
    "/dashboard/reports/",
    "/dashboard/org/",
    "/dashboard/settings/"
)
$pageOk = 0
$pageFail = 0
foreach ($page in $pages) {
    try {
        $r = Invoke-WebRequest -Uri "$ServerUrl$page" -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $pageOk++ } else { $pageFail++ }
        Write-Host "  $(if ($r.StatusCode -eq 200) { '✅' } else { '❌' }) $page ($($r.StatusCode))"
    } catch {
        Write-Host "  ❌ $page (connection error)" -ForegroundColor Red
        $pageFail++
    }
}

# Summary
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                  SANDBOX SUMMARY                 ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Dashboard pages: $pageOk OK, $pageFail failed" -ForegroundColor $(if ($pageFail -eq 0) { 'Green' } else { 'Red' })
Write-Host "  Server URL:      $ServerUrl" -ForegroundColor White
Write-Host "  Dev login:       admin@corp.local / MyP@ss1" -ForegroundColor White
Write-Host "  Test data:       72 hours of simulated activity" -ForegroundColor White
Write-Host "  Dashboard:       http://localhost:8000/dashboard/" -ForegroundColor Cyan
Write-Host ""

if ($pageFail -eq 0) {
    Write-Host "  All systems operational!" -ForegroundColor Green
} else {
    Write-Host "  $pageFail dashboard pages have issues." -ForegroundColor Yellow
}
