# AGENT PRAYATH v2.0 - PowerShell Launcher
Write-Host "==========================================" -ForegroundColor Green
Write-Host "       AGENT PRAYATH v2.0 - LAUNCHER      " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "[*] Checking Python environment..." -ForegroundColor Yellow

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Python is not found in PATH! Please install Python 3.10+ from python.org" -ForegroundColor Red
    Pause
    exit 1
}

Write-Host "[+] Launching Agent Prayath (Automatic Code Editor)..." -ForegroundColor Cyan
python vision_agent.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Program exited with error code $LASTEXITCODE. Check error_log.txt." -ForegroundColor Red
    Pause
}
