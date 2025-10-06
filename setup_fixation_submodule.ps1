# Script to set up the Rights Fixation System as a Git submodule
# This script helps separate the Rights Fixation System into its own repository

param (
    [string]$RemoteUrl = "",
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
$rootDir = $PSScriptRoot
$fixationDir = Join-Path $rootDir "מערכת קיבוע זכויות"

# Check if the Rights Fixation System directory exists
if (-not (Test-Path $fixationDir)) {
    Write-Error "Rights Fixation System directory not found at: $fixationDir"
    exit 1
}

# Function to execute a command with dry run support
function Invoke-CommandWithDryRun {
    param (
        [string]$Command,
        [string]$Description
    )
    
    Write-Host "COMMAND: $Description" -ForegroundColor Cyan
    Write-Host "  $Command" -ForegroundColor Gray
    
    if (-not $DryRun) {
        Write-Host "  Executing..." -ForegroundColor Yellow
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Command failed with exit code $LASTEXITCODE"
            exit 1
        }
    } else {
        Write-Host "  [DRY RUN] Command would be executed here" -ForegroundColor Magenta
    }
    
    Write-Host "  Done." -ForegroundColor Green
    Write-Host ""
}

# Main script execution
Write-Host "Setting up Rights Fixation System as a Git submodule" -ForegroundColor Green
Write-Host "Root directory: $rootDir" -ForegroundColor Yellow
Write-Host "Fixation directory: $fixationDir" -ForegroundColor Yellow
Write-Host "Remote URL: $RemoteUrl" -ForegroundColor Yellow
Write-Host "Dry run: $DryRun" -ForegroundColor Yellow
Write-Host ""

# Step 1: Check if the directory is already a Git repository
$isGitRepo = Test-Path (Join-Path $fixationDir ".git")
if ($isGitRepo) {
    Write-Host "The Rights Fixation System directory is already a Git repository." -ForegroundColor Green
} else {
    Write-Host "The Rights Fixation System directory is not a Git repository. Initializing..." -ForegroundColor Yellow
    Invoke-CommandWithDryRun -Command "Push-Location '$fixationDir'; git init; Pop-Location" -Description "Initialize Git repository"
}

# Step 2: If a remote URL is provided, set it up
if ($RemoteUrl) {
    Invoke-CommandWithDryRun -Command "Push-Location '$fixationDir'; git remote add origin '$RemoteUrl'; Pop-Location" -Description "Add remote origin"
}

# Step 3: Create a .gitignore file in the fixation directory if it doesn't exist
$fixationGitignorePath = Join-Path $fixationDir ".gitignore"
if (-not (Test-Path $fixationGitignorePath)) {
    $gitignoreContent = @"
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environment
.venv/
venv/
env/
ENV/
.env/
env.bak/
venv.bak/
.env.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Database
*.sqlite3
*.db
*.db-journal

# Environment variables
.env
.env.local
.env.development
.env.test
.env.production

# Logs
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Local development
.DS_Store
Thumbs.db
.pytest_cache/
.coverage
htmlcov/
coverage/

# Node.js
node_modules/
.npm/
.yarn/
.pnp.*

# Build outputs
dist/
build/
*.tsbuildinfo

# Temporary files
tmp/
temp/
"@

    Invoke-CommandWithDryRun -Command "Set-Content -Path '$fixationGitignorePath' -Value '$gitignoreContent'" -Description "Create .gitignore file"
}

# Step 4: Remove the fixation directory from the main repository
Invoke-CommandWithDryRun -Command "Push-Location '$rootDir'; git rm -r --cached '$fixationDir'; Pop-Location" -Description "Remove fixation directory from Git tracking"

# Step 5: Add a submodule entry to the main repository's .gitmodules file
$gitmodulesPath = Join-Path $rootDir ".gitmodules"
$gitmodulesContent = ""

if (Test-Path $gitmodulesPath) {
    $gitmodulesContent = Get-Content -Path $gitmodulesPath -Raw
}

$submoduleName = "מערכת קיבוע זכויות"
$submodulePath = "מערכת קיבוע זכויות"
$submoduleEntry = @"
[submodule "$submoduleName"]
	path = $submodulePath
	url = $RemoteUrl
"@

if (-not $gitmodulesContent.Contains($submoduleName)) {
    if ($gitmodulesContent) {
        $gitmodulesContent += "`n$submoduleEntry"
    } else {
        $gitmodulesContent = $submoduleEntry
    }
    
    Invoke-CommandWithDryRun -Command "Set-Content -Path '$gitmodulesPath' -Value '$gitmodulesContent'" -Description "Update .gitmodules file"
}

# Step 6: Instructions for committing changes
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Commit the changes in the Rights Fixation System repository:" -ForegroundColor Yellow
Write-Host "   cd '$fixationDir'" -ForegroundColor Gray
Write-Host "   git add ." -ForegroundColor Gray
Write-Host "   git commit -m 'Initial commit as separate repository'" -ForegroundColor Gray
if ($RemoteUrl) {
    Write-Host "   git push -u origin main" -ForegroundColor Gray
}

Write-Host "2. Commit the changes in the main repository:" -ForegroundColor Yellow
Write-Host "   cd '$rootDir'" -ForegroundColor Gray
Write-Host "   git add .gitmodules" -ForegroundColor Gray
Write-Host "   git add '$fixationDir'" -ForegroundColor Gray
Write-Host "   git commit -m 'Set up Rights Fixation System as a submodule'" -ForegroundColor Gray

Write-Host "Setup completed successfully!" -ForegroundColor Green
