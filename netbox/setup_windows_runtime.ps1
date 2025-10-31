# Windows Python Runtime Setup Script
# This script downloads and configures a standalone Python runtime for Windows
# allowing the project to run without installing Python system-wide

param(
    [string]$PythonVersion = "3.13.5",
    [switch]$SkipDependencies
)

$ErrorActionPreference = 'Stop'

Write-Host "=== Windows Python Runtime Setup ===" -ForegroundColor Cyan
Write-Host ""

# Configuration
$runtimeDir = ".venv/python_runtime_windows"
$scriptsDir = ".venv/Scripts"
$libDir = ".venv/Lib"

# URLs
$pythonEmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"

# Step 1: Download Python Embedded
Write-Host "1. Downloading Python $PythonVersion Embedded for Windows..." -ForegroundColor Yellow
$tempZip = "python_embed_temp.zip"

try {
    Invoke-WebRequest -Uri $pythonEmbedUrl -OutFile $tempZip -UseBasicParsing
    Write-Host "   Downloaded successfully" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Failed to download Python. Check your internet connection." -ForegroundColor Red
    Write-Host "   URL: $pythonEmbedUrl" -ForegroundColor Red
    exit 1
}

# Step 2: Extract Python Runtime
Write-Host "2. Extracting Python runtime..." -ForegroundColor Yellow
if (Test-Path $runtimeDir) {
    Write-Host "   Removing existing runtime directory..." -ForegroundColor Gray
    Remove-Item -Path $runtimeDir -Recurse -Force
}
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Expand-Archive -Path $tempZip -DestinationPath $runtimeDir -Force
Remove-Item $tempZip
Write-Host "   Extracted to $runtimeDir" -ForegroundColor Green

# Step 3: Configure Python to use site-packages
Write-Host "3. Configuring Python paths..." -ForegroundColor Yellow
$pthFile = Join-Path $runtimeDir "python313._pth"
if (Test-Path $pthFile) {
    # Uncomment import site and add Lib/site-packages
    $content = Get-Content $pthFile
    $newContent = @()
    foreach ($line in $content) {
        if ($line -match "^#import site") {
            $newContent += "import site"
        } else {
            $newContent += $line
        }
    }
    # Add paths
    $newContent += "../Lib/site-packages"
    $newContent += "../Lib"
    $newContent | Set-Content $pthFile
    Write-Host "   Updated $pthFile" -ForegroundColor Green
}

# Step 4: Install pip
Write-Host "4. Installing pip..." -ForegroundColor Yellow
$getPipScript = "get-pip.py"
try {
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipScript -UseBasicParsing
    & "$runtimeDir/python.exe" $getPipScript --no-warn-script-location
    Remove-Item $getPipScript
    Write-Host "   pip installed successfully" -ForegroundColor Green
} catch {
    Write-Host "   WARNING: Failed to install pip: $_" -ForegroundColor Yellow
}

# Step 5: Create Scripts directory with shortcuts
Write-Host "5. Creating Scripts directory..." -ForegroundColor Yellow
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
}

# Create python.exe shortcut/copy
$pythonExe = Join-Path $runtimeDir "python.exe"
$targetPython = Join-Path $scriptsDir "python.exe"
if (Test-Path $pythonExe) {
    Copy-Item $pythonExe $targetPython -Force
    Write-Host "   Created python.exe in Scripts/" -ForegroundColor Green
}

# Step 6: Install dependencies
if (-not $SkipDependencies) {
    Write-Host "6. Installing Python dependencies..." -ForegroundColor Yellow
    if (Test-Path "requirements.txt") {
        try {
            & "$runtimeDir/python.exe" -m pip install -r requirements.txt --no-warn-script-location
            Write-Host "   Dependencies installed successfully" -ForegroundColor Green
        } catch {
            Write-Host "   ERROR: Failed to install dependencies: $_" -ForegroundColor Red
            Write-Host "   You can install them manually later with:" -ForegroundColor Yellow
            Write-Host "   .venv/python_runtime_windows/python.exe -m pip install -r requirements.txt" -ForegroundColor Gray
        }
    } else {
        Write-Host "   WARNING: requirements.txt not found" -ForegroundColor Yellow
    }
} else {
    Write-Host "6. Skipping dependencies installation (use -SkipDependencies:$false to install)" -ForegroundColor Gray
}

# Step 7: Create activation script
Write-Host "7. Creating activation script..." -ForegroundColor Yellow
$activateScript = @"
# Windows Python Runtime Activation Script
`$env:VIRTUAL_ENV = (Get-Location).Path + "\.venv"
`$env:PATH = "`$env:VIRTUAL_ENV\python_runtime_windows;" + "`$env:VIRTUAL_ENV\Scripts;" + `$env:PATH
Write-Host "Python runtime activated" -ForegroundColor Green
Write-Host "Python: " -NoNewline
& python --version
"@
$activateScript | Set-Content "$scriptsDir/Activate.ps1"
Write-Host "   Created Activate.ps1" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python runtime installed to: $runtimeDir" -ForegroundColor Green
Write-Host "Python version: " -NoNewline
& "$runtimeDir/python.exe" --version

Write-Host ""
Write-Host "To use the runtime:" -ForegroundColor Yellow
Write-Host "  1. Activate: .\.venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "  2. Or run directly: .\.venv\python_runtime_windows\python.exe manage.py runserver" -ForegroundColor Gray
Write-Host ""
Write-Host "To start the server:" -ForegroundColor Yellow
Write-Host "  .\start_server.ps1" -ForegroundColor Gray
Write-Host ""
