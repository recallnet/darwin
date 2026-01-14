#!/bin/bash
# Darwin Services Stop Script
# Stops Redis, Celery worker, and FastAPI backend

echo "Stopping Darwin services..."

# Stop Celery worker
if pgrep -f "celery.*darwin.api.celery_app.*worker" > /dev/null; then
    echo "Stopping Celery worker..."
    pkill -f "celery.*darwin.api.celery_app"
    sleep 1
    echo "✓ Celery worker stopped"
else
    echo "✓ Celery worker not running"
fi

# Stop FastAPI backend
if pgrep -f "uvicorn.*darwin.api.main" > /dev/null; then
    echo "Stopping FastAPI backend..."
    pkill -f "uvicorn.*darwin.api.main"
    sleep 1
    echo "✓ FastAPI backend stopped"
else
    echo "✓ FastAPI backend not running"
fi

# Stop Redis
if pgrep -x "redis-server" > /dev/null; then
    echo "Stopping Redis..."
    brew services stop redis
    sleep 1
    echo "✓ Redis stopped"
else
    echo "✓ Redis not running"
fi

echo ""
echo "All services stopped"
