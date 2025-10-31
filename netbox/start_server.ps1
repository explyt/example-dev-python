# NetBox Server Startup Script for Windows (PowerShell)
# Requires: Python 3.8+ and virtual environment setup

# Stop on error
$ErrorActionPreference = 'Stop'

Write-Host "=== NetBox Server Startup ===" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run: .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "1. Activating virtual environment..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"

# Run migrations
Write-Host "2. Running database migrations..." -ForegroundColor Yellow
python manage.py migrate --noinput

# Collect static files
Write-Host "3. Collecting static files..." -ForegroundColor Yellow
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
Write-Host "4. Creating superuser (if not exists)..." -ForegroundColor Yellow
try {
    python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model();
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin','admin@example.com','admin');
    print('CREATED_SUPERUSER')
else:
    print('SUPERUSER_EXISTS')"
} catch {
    Write-Host "   Superuser creation skipped or failed: $_" -ForegroundColor Yellow
}

# Create API token for admin user
Write-Host "5. Creating/retrieving API token..." -ForegroundColor Yellow
$token = ""
try {
    $out = python manage.py shell -c "from users.models import Token; from django.contrib.auth import get_user_model; User=get_user_model(); u=User.objects.get(username='admin'); t,created=Token.objects.get_or_create(user=u); print(t.key)" 2>$null
    if ($out) {
        # take last non-empty line
        $lines = $out -split "\r?\n" | Where-Object { $_ -ne '' }
        if ($lines.Count -gt 0) { $token = $lines[-1] }
    }
} catch {
    Write-Host "   Token creation/retrieval skipped or failed: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""

if ($token) { 
    Write-Host "API Token: $token" -ForegroundColor Green
} else { 
    Write-Host "API Token: (not available)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting server on 127.0.0.1:8000..." -ForegroundColor Yellow
Write-Host "Login credentials: username=admin, password=admin" -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Start the server
python manage.py runserver 127.0.0.1:8000
