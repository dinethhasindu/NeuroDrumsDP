# Setup Script for NeuroDrums AI on Windows

$ErrorActionPreference = "Stop"

Write-Host "Setting up NeuroDrums AI..." -ForegroundColor Cyan

# Check for Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate and install requirements
Write-Host "Activating virtual environment and installing dependencies..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt

# Download model if not exists
if (-not (Test-Path "models\drumsep.onnx")) {
    Write-Host "Downloading DrumSep ONNX model (this may take a while)..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path "models" | Out-Null
    Invoke-WebRequest -Uri "https://huggingface.co/gridshiftstudio/drumsep-onnx/resolve/main/drumsep.onnx" -OutFile "models\drumsep.onnx"
}

Write-Host "Setup complete! You can now run the app with .\run_neurodrums.ps1" -ForegroundColor Green
