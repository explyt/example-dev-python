#!/bin/bash
# NetBox Server Startup Script for Linux
# This script uses embedded Python runtime for Linux

set -e

echo "=== NetBox Server Startup (Linux) ==="
echo ""

# Определить архитектуру
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        PYTHON_RUNTIME=".venv/python_runtime_linux"
        ;;
    aarch64|arm64)
        echo "ERROR: ARM64 Linux is not yet supported"
        echo "Only x86_64 is currently included"
        exit 1
        ;;
    *)
        echo "ERROR: Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Проверить наличие runtime
if [ ! -f "$PYTHON_RUNTIME/bin/python3" ]; then
    echo "ERROR: Python runtime not found at $PYTHON_RUNTIME"
    echo "Please ensure Linux Python runtime is installed"
    exit 1
fi

echo "Using Python runtime: $PYTHON_RUNTIME"
$PYTHON_RUNTIME/bin/python3 --version
echo ""

# Установить PYTHONPATH для использования Linux site-packages
export PYTHONPATH=".venv/lib-linux/site-packages:$PYTHONPATH"

# Run migrations
echo "Running database migrations..."
$PYTHON_RUNTIME/bin/python3 manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
$PYTHON_RUNTIME/bin/python3 manage.py collectstatic --noinput

# Create superuser if it doesn't exist
echo "Creating superuser (if not exists)..."
$PYTHON_RUNTIME/bin/python3 manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    u = User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: username=admin, password=admin')
else:
    print('Superuser already exists')
" 2>/dev/null || echo "Superuser creation skipped"

# Create API token for admin user
echo "Creating/retrieving API token..."
TOKEN=$($PYTHON_RUNTIME/bin/python3 manage.py shell -c "
from users.models import Token
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username='admin')
t, created = Token.objects.get_or_create(user=u)
print(t.key)
" 2>/dev/null | tail -1)

echo ""
echo "=== Setup Complete ==="
echo ""

if [ -n "$TOKEN" ]; then
    echo "API Token: $TOKEN"
else
    echo "API Token: (not available)"
fi

echo ""
echo "Starting server on 127.0.0.1:8000..."
echo "Login credentials: username=admin, password=admin"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
$PYTHON_RUNTIME/bin/python3 manage.py runserver 127.0.0.1:8000
