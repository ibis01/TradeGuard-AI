#!/bin/bash
# Robo-Shopper - Bulletproof Setup Script
set -e

echo "🚀 Starting Robo-Shopper setup..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python $PYTHON_VERSION detected."

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
else
    echo "✅ Virtual environment already exists."
fi

echo "🔄 Activating virtual environment..."
source .venv/bin/activate

echo "📥 Installing project dependencies..."
if [ -f "requirements.txt" ]; then
    pip install --upgrade pip --quiet
    # Install requirements first
    pip install -r requirements.txt --quiet
    # THEN upgrade conflicting packages to prevent requirements.txt from downgrading them
    pip install --upgrade "pydantic[email]>=2.12.0" "python-dotenv>=1.1.0" "fastmcp-slim[client]" "starlette>=0.40.0,<0.42.0" "fastapi>=0.115.0" --quiet
else
    echo "⚠️  requirements.txt not found. Skipping dependency installation."
fi

if [ ! -f ".env" ]; then
    echo "⚙️  Creating default .env file for development/demo..."
    cat <<EOF > .env
DEV_MODE=1
DASHBOARD_API_KEY=robo-shopper-local-dev
SESSION_SECRET=super-secret-dev-session-key-change-in-prod
DB_PATH=data/trades.db
EOF
    echo "✅ Default .env file created."
else
    echo "✅ .env file already exists. Skipping creation to preserve your settings."
fi

if [ ! -d "data" ]; then
    echo "📁 Creating data directory for SQLite database..."
    mkdir -p data
fi

echo "🌐 Starting dashboard server in background for sanity check..."
fuser -k 8003/tcp 2>/dev/null || true
DEV_MODE=1 python dashboard.py > /dev/null 2>&1 &
DASHBOARD_PID=$!
sleep 3

echo "🧪 Running quick sanity check (pytest tests/ -q)..."
if pytest tests/ -q > /dev/null 2>&1; then
    echo "✅ All tests passing. System is healthy."
else
    echo "⚠️  Some tests failed. Please review the test output above."
    pytest tests/ -q
fi

echo "🛑 Stopping background dashboard server..."
kill $DASHBOARD_PID 2>/dev/null || true
fuser -k 8003/tcp 2>/dev/null || true

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Activate the environment (if not already active):"
echo "   source .venv/bin/activate"
echo ""
echo "2. Start the Institutional Dashboard:"
echo "   DEV_MODE=1 python dashboard.py"
echo "   (Visit http://localhost:8003 in your browser)"
echo ""
echo "3. Start the Robo-Shopper Agent (in a new terminal):"
echo "   python main.py"