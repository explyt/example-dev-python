# NetBox Server Startup Script for Windows (PowerShell)
# This script prepares and starts the NetBox server with SQLite and diskcache
# Usage: Open PowerShell in the project root and run: .\start_server.ps1

# Stop on error
$ErrorActionPreference = 'Stop'

Write-Host "=== NetBox Server Startup ==="`n
# Activate virtual environment
Write-Host "1. Activating virtual environment..."
if (Test-Path -Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Using PowerShell activation script"
    . .\.venv\Scripts\Activate.ps1
} elseif (Test-Path -Path ".venv\Scripts\activate") {
    Write-Host "Using POSIX-style activation (Git Bash / WSL)."
    # Try to call via bash if available
    if (Get-Command bash -ErrorAction SilentlyContinue) {
        bash -lc "source .venv/bin/activate && python manage.py --version" | Out-Null
        Write-Host "Activated via bash (subshell) — subsequent commands will be run with current Python directly."
    } else {
        Write-Host "No suitable activation script found. Make sure .venv exists and was created on Windows."
    }
} else {
    Write-Host "Virtual environment not found at .venv. You can create it with: python -m venv .venv"
}

# Run migrations
Write-Host "2. Running database migrations..."
python manage.py migrate --noinput

# Collect static files
Write-Host "3. Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
Write-Host "4. Creating superuser (if not exists)..."
try {
    python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin','admin@example.com','admin');
    print('CREATED_SUPERUSER')
else:
    print('SUPERUSER_EXISTS')"
} catch {
    Write-Host "Superuser creation skipped or failed: $_"
}

# Create API token for admin user
Write-Host "5. Creating/retrieving API token..."
$token = ""
try {
    $out = python manage.py shell -c "from users.models import Token; from django.contrib.auth import get_user_model; User=get_user_model(); u=User.objects.get(username='admin'); t,created=Token.objects.get_or_create(user=u); print(t.key)" 2>$null
    if ($out) {
        # take last non-empty line
        $lines = $out -split "\r?\n" | Where-Object { $_ -ne '' }
        if ($lines.Count -gt 0) { $token = $lines[-1] }
    }
} catch {
    Write-Host "Token creation/retrieval skipped or failed: $_"
}

Write-Host ""`nWrite-Host "=== Setup Complete ==="`n
if ($token) { Write-Host "API Token: $token" } else { Write-Host "API Token: (not available)" }
Write-Host ""; Write-Host "Starting server on 127.0.0.1:8000..."
Write-Host "Login credentials: username=admin, password=admin"`n
Write-Host "Press Ctrl+C to stop the server"`n

# Start the server
python manage.py runserver 127.0.0.1:8000
