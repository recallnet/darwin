#!/bin/bash
# Darwin Services Startup Script
# Starts Redis, Celery worker, and FastAPI backend

set -e

echo "Starting Darwin services..."

# Start Redis if not running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis..."
    brew services start redis
    sleep 2
else
    echo "✓ Redis already running"
fi

# Start Celery worker if not running (using solo pool for macOS compatibility)
if ! pgrep -f "celery.*darwin.api.celery_app.*worker" > /dev/null; then
    echo "Starting Celery worker (solo pool for macOS)..."
    cd /Users/michaelsena/code/darwin
    celery -A darwin.api.celery_app worker --loglevel=info --pool=solo > celery_worker.log 2>&1 &
    sleep 3
    echo "✓ Celery worker started (check celery_worker.log for details)"
else
    echo "✓ Celery worker already running"
fi

# Start FastAPI backend if not running
if ! pgrep -f "uvicorn.*darwin.api.main" > /dev/null; then
    echo "Starting FastAPI backend..."
    cd /Users/michaelsena/code/darwin
    python3 -m uvicorn darwin.api.main:app --reload > api_server.log 2>&1 &
    sleep 2
    echo "✓ FastAPI backend started (check api_server.log for details)"
else
    echo "✓ FastAPI backend already running"
fi

echo ""
echo "All services running:"
echo "  - Redis: redis://localhost:6379"
echo "  - Celery worker: 1 worker (solo pool)"
echo "  - FastAPI: http://localhost:8000"
echo ""
echo "⚠️  NOTE: The main trading simulation loop is not yet implemented."
echo "   Runs will complete but produce zero trades until the data"
echo "   loading and bar processing logic is implemented."
echo ""
echo "To stop services:"
echo "  ./stop_services.sh"
