#!/bin/bash

# NetBox Setup Script
# Creates virtual environment and installs dependencies

set -e

echo "=== NetBox Setup ==="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

echo "Python version:"
python3 --version
echo ""

# Remove old venv if exists
if [ -d ".venv" ]; then
    echo "Removing old virtual environment..."
    rm -rf .venv
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the server:"
echo "  ./start_server.sh"
echo ""
