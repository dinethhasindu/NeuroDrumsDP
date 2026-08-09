# Run Script for NeuroDrums AI on Windows

if (-not (Test-Path "venv")) {
    Write-Host "Virtual environment not found. Please run setup_windows.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting NeuroDrums AI..." -ForegroundColor Cyan
.\venv\Scripts\Activate.ps1
python app.py
