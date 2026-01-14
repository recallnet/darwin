# Darwin Services Management

This document explains how to manage the required services for the Darwin web application.

## Required Services

The Darwin web application requires three services to be running:

1. **Redis** - Message broker and result backend for Celery
2. **Celery Worker** - Background task processor for running backtests
3. **FastAPI Backend** - REST API server (port 8000)
4. **Next.js Frontend** - Web UI (port 3001)

## Quick Start

### Start All Services

```bash
cd /Users/michaelsena/code/darwin
./start_services.sh
```

This script will:
- Start Redis (via Homebrew services)
- Start Celery worker (2 workers in background)
- Start FastAPI backend (with auto-reload)

### Stop All Services

```bash
cd /Users/michaelsena/code/darwin
./stop_services.sh
```

### Start Frontend

```bash
cd /Users/michaelsena/code/darwin/darwin-ui
npm run dev
```

## Manual Service Management

### Redis

**Start:**
```bash
brew services start redis
```

**Stop:**
```bash
brew services stop redis
```

**Test connection:**
```bash
redis-cli ping
# Should return: PONG
```

### Celery Worker

**Start:**
```bash
cd /Users/michaelsena/code/darwin
celery -A darwin.api.celery_app worker --loglevel=info --concurrency=2
```

**Stop:**
```bash
pkill -f "celery.*darwin.api.celery_app"
```

**Check status:**
```bash
ps aux | grep "celery.*worker"
```

### FastAPI Backend

**Start:**
```bash
cd /Users/michaelsena/code/darwin
python3 -m uvicorn darwin.api.main:app --reload
```

**Stop:**
```bash
pkill -f "uvicorn.*darwin.api.main"
```

**Access:**
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Next.js Frontend

**Start:**
```bash
cd /Users/michaelsena/code/darwin/darwin-ui
npm run dev
```

**Access:**
- Web UI: http://localhost:3001

## Health Checks

### Check All Services

```bash
curl http://localhost:8000/health | python3 -m json.tool
```

Expected output when all services are running:
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "services": {
        "redis": {
            "status": "up",
            "url": "redis://localhost:6379/0"
        },
        "celery": {
            "status": "up",
            "workers": ["celery@hostname"],
            "count": 1
        }
    }
}
```

### Service Status Meanings

- **healthy**: All services running normally
- **degraded**: Some services running, some down
- **unhealthy**: All critical services down

## Troubleshooting

### Redis Not Starting

```bash
# Check if Redis is installed
brew list redis

# If not installed
brew install redis

# Check Redis logs
brew services info redis
```

### Celery Worker Not Connecting

```bash
# Check Redis is running first
redis-cli ping

# Check Celery logs
tail -f celery_worker.log

# Restart worker
pkill -f "celery.*darwin.api.celery_app"
celery -A darwin.api.celery_app worker --loglevel=info --concurrency=2 &
```

### API Startup Warnings

When you start the FastAPI backend, it will check for Redis and Celery:

```
============================================================
Starting Darwin API...
============================================================

Checking Redis connection...
✓ Redis connected: redis://localhost:6379/0
Checking Celery workers...
✓ Celery workers running: 1 workers
  Workers: celery@MacBook-Pro-3.local

============================================================
✓ All services ready!
============================================================
```

If you see warnings:
```
⚠️  CRITICAL: Required services are not running!
```

Follow the instructions in the output to start missing services.

### Runs Not Executing

If runs are created but show zero trades:

1. **Check Celery is running:**
   ```bash
   ps aux | grep "celery.*worker"
   ```

2. **Check run was launched:**
   - Look for "queued" or "running" status in the UI
   - Check Celery logs: `tail -f celery_worker.log`

3. **Check for errors:**
   ```bash
   # View recent Celery logs
   tail -50 celery_worker.log

   # Check run artifacts
   ls -la artifacts/runs/<run-id>/
   # Should see: run_config.json, manifest.json, positions.sqlite
   ```

## Log Files

When running in background, logs are saved to:
- `celery_worker.log` - Celery worker logs
- `api_server.log` - FastAPI logs (if started with start_services.sh)

View logs in real-time:
```bash
tail -f celery_worker.log
tail -f api_server.log
```

## Environment Variables

The following environment variables can be configured in `.env`:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Database
DATABASE_URL=postgresql://user:pass@localhost/darwin

# API
API_HOST=0.0.0.0
API_PORT=8000

# CORS
ALLOWED_ORIGINS=http://localhost:3001,http://localhost:3000
```

## Development Workflow

Typical development workflow:

1. **Start backend services** (once per session):
   ```bash
   ./start_services.sh
   ```

2. **Start frontend** (in a separate terminal):
   ```bash
   cd darwin-ui && npm run dev
   ```

3. **Make changes** to code - services will auto-reload

4. **Stop everything** when done:
   ```bash
   ./stop_services.sh
   # Press Ctrl+C in frontend terminal
   ```

## Production Deployment

For production, consider:

1. **Docker Compose** - Orchestrate all services
2. **Systemd** - Manage services on Linux
3. **Supervisor** - Process management
4. **Kubernetes** - Container orchestration

See `docker-compose.yml` (if available) for containerized deployment.
