# CI dependency installation script with caching
# Usage: .\ci_install_deps.ps1 [-Frontend] [-Backend] [-FixationSystem]

param (
    [switch]$Frontend = $false,
    [switch]$Backend = $false,
    [switch]$FixationSystem = $false
)

$ErrorActionPreference = "Stop"
$rootDir = $PSScriptRoot

# If no specific flags are provided, install all dependencies
if (-not ($Frontend -or $Backend -or $FixationSystem)) {
    $Frontend = $true
    $Backend = $true
    $FixationSystem = $true
}

function Test-CommandExists {
    param ($command)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try {
        if (Get-Command $command) { return $true }
    }
    catch { return $false }
    finally { $ErrorActionPreference = $oldPreference }
}

function Install-BackendDeps {
    Write-Host "Installing backend dependencies..." -ForegroundColor Green
    
    # Check if Python is installed
    if (-not (Test-CommandExists python)) {
        Write-Error "Python is not installed or not in PATH"
        exit 1
    }
    
    # Create virtual environment if it doesn't exist
    if (-not (Test-Path "$rootDir\.venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv "$rootDir\.venv"
    }
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & "$rootDir\.venv\Scripts\Activate.ps1"
    
    # Install dependencies
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    pip install -r "$rootDir\requirements.txt"
    
    Write-Host "Backend dependencies installed successfully!" -ForegroundColor Green
}

function Install-FrontendDeps {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Green
    
    # Check if Node.js is installed
    if (-not (Test-CommandExists node)) {
        Write-Error "Node.js is not installed or not in PATH"
        exit 1
    }
    
    # Install dependencies
    Push-Location "$rootDir\frontend"
    try {
        Write-Host "Installing npm packages..." -ForegroundColor Yellow
        npm ci
    }
    finally {
        Pop-Location
    }
    
    Write-Host "Frontend dependencies installed successfully!" -ForegroundColor Green
}

function Install-FixationSystemDeps {
    Write-Host "Installing Rights Fixation System dependencies..." -ForegroundColor Green
    
    # Check if Python is installed
    if (-not (Test-CommandExists python)) {
        Write-Error "Python is not installed or not in PATH"
        exit 1
    }
    
    # Create virtual environment if it doesn't exist
    $fixationDir = Join-Path $rootDir "מערכת קיבוע זכויות"
    if (-not (Test-Path "$fixationDir\.venv")) {
        Write-Host "Creating virtual environment for Rights Fixation System..." -ForegroundColor Yellow
        python -m venv "$fixationDir\.venv"
    }
    
    # Activate virtual environment
    Write-Host "Activating Rights Fixation System virtual environment..." -ForegroundColor Yellow
    & "$fixationDir\.venv\Scripts\Activate.ps1"
    
    # Install dependencies
    Write-Host "Installing Rights Fixation System Python dependencies..." -ForegroundColor Yellow
    pip install -r "$fixationDir\requirements.txt"
    
    # Install frontend dependencies if client-ui exists
    if (Test-Path "$fixationDir\client-ui") {
        # Check if Node.js is installed
        if (-not (Test-CommandExists node)) {
            Write-Error "Node.js is not installed or not in PATH"
            exit 1
        }
        
        # Install dependencies
        Push-Location "$fixationDir\client-ui"
        try {
            Write-Host "Installing Rights Fixation System npm packages..." -ForegroundColor Yellow
            npm ci
        }
        finally {
            Pop-Location
        }
    }
    
    Write-Host "Rights Fixation System dependencies installed successfully!" -ForegroundColor Green
}

# Install dependencies based on flags
if ($Backend) {
    Install-BackendDeps
}

if ($Frontend) {
    Install-FrontendDeps
}

if ($FixationSystem) {
    Install-FixationSystemDeps
}

Write-Host "All requested dependencies installed successfully!" -ForegroundColor Green
