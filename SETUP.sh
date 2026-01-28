#!/bin/bash

# Netflix Checker v2.0 Setup Script
# Run this script to set up the project

echo "======================================"
echo "Netflix Checker v2.0 - Setup Script"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 is not installed"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"
echo ""

# Install dependencies
echo "Installing dependencies..."
if pip install -r requirements.txt; then
    echo "✓ Dependencies installed successfully"
else
    echo "✗ Failed to install dependencies"
    exit 1
fi
echo ""

# Create directories
echo "Setting up directories..."
mkdir -p cookies
mkdir -p results
echo "✓ Directories created"
echo ""

# Verify installation
echo "Verifying installation..."
python3 << 'EOF'
try:
    import requests
    import bs4
    import urllib3
    print("✓ All required packages imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "✓ Installation verified"
else
    echo "✗ Installation verification failed"
    exit 1
fi
echo ""

# Check checker.py syntax
echo "Checking code syntax..."
if python3 -c "import ast; ast.parse(open('checker.py').read())" 2>/dev/null; then
    echo "✓ Code syntax is valid"
else
    echo "✗ Code syntax error"
    exit 1
fi
echo ""

echo "======================================"
echo "Setup Complete! ✓"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Configure accounts.json with your test accounts"
echo "2. Run: python3 checker.py accounts.json --mode netflix"
echo "3. Check results in: results/ directory"
echo "4. Nikom Netflix security architecture!"
echo ""
echo "For help: python3 checker.py --help"
echo ""
