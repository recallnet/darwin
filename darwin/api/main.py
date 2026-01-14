"""
Darwin API - FastAPI Backend

Main application entry point for the Darwin web application backend.
Provides REST API endpoints for:
- Authentication and team management
- Run management and execution
- Performance reporting and analysis
- RL agent monitoring
"""

import os
import sys
from typing import List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import redis

# Load environment variables
load_dotenv()

# Import routers
from darwin.api.routers import auth, teams, runs, reports, meta, rl, models, playbooks, symbols

__version__ = "0.1.0"


def check_redis_connection() -> Dict[str, bool]:
    """Check if Redis is accessible."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        return {"connected": True, "url": redis_url}
    except Exception as e:
        return {"connected": False, "url": redis_url, "error": str(e)}


def check_celery_workers() -> Dict[str, any]:
    """Check if Celery workers are running."""
    try:
        from darwin.api.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=2)
        active_workers = inspect.active()

        if active_workers:
            return {
                "running": True,
                "workers": list(active_workers.keys()),
                "count": len(active_workers)
            }
        else:
            return {"running": False, "workers": [], "count": 0}
    except Exception as e:
        return {"running": False, "error": str(e)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Handles startup and shutdown logic with dependency checks.
    """
    # Startup
    print("=" * 60)
    print("Starting Darwin API...")
    print("=" * 60)

    # Check Redis
    print("\nChecking Redis connection...")
    redis_status = check_redis_connection()
    if redis_status["connected"]:
        print(f"✓ Redis connected: {redis_status['url']}")
    else:
        print(f"✗ Redis connection failed: {redis_status['url']}")
        print(f"  Error: {redis_status.get('error', 'Unknown error')}")
        print("\n⚠️  WARNING: Redis is not running!")
        print("  Start Redis with: brew services start redis")
        print("  Or run: ./start_services.sh")
        print()

    # Check Celery workers
    print("Checking Celery workers...")
    celery_status = check_celery_workers()
    if celery_status["running"]:
        print(f"✓ Celery workers running: {celery_status['count']} workers")
        print(f"  Workers: {', '.join(celery_status['workers'])}")
    else:
        print("✗ No Celery workers detected")
        if "error" in celery_status:
            print(f"  Error: {celery_status['error']}")
        print("\n⚠️  WARNING: Celery workers are not running!")
        print("  Start workers with: celery -A darwin.api.celery_app worker --loglevel=info --concurrency=2")
        print("  Or run: ./start_services.sh")
        print()

    # Determine if we can run
    if not redis_status["connected"] or not celery_status["running"]:
        print("\n" + "=" * 60)
        print("⚠️  CRITICAL: Required services are not running!")
        print("=" * 60)
        print("\nThe API will start, but run execution will fail.")
        print("Please start missing services:")
        print("  ./start_services.sh")
        print("\nOr start them individually:")
        if not redis_status["connected"]:
            print("  brew services start redis")
        if not celery_status["running"]:
            print("  celery -A darwin.api.celery_app worker --loglevel=info --concurrency=2 &")
        print("\n" + "=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✓ All services ready!")
        print("=" * 60)

    print(f"\nDarwin API {__version__} is running")
    print(f"Documentation: http://localhost:8000/docs")
    print()

    yield

    # Shutdown
    print("\nShutting down Darwin API...")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="Darwin API",
        description="Backend API for Darwin trading strategy research platform",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    allowed_origins_str = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3001,http://127.0.0.1:3001,http://localhost:3000,http://127.0.0.1:3000"
    )
    allowed_origins: List[str] = [origin.strip() for origin in allowed_origins_str.split(",")]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """
        Health check endpoint with dependency status.

        Returns:
            - status: overall health (healthy/degraded/unhealthy)
            - version: API version
            - redis: Redis connection status
            - celery: Celery worker status
        """
        redis_status = check_redis_connection()
        celery_status = check_celery_workers()

        # Determine overall status
        if redis_status["connected"] and celery_status["running"]:
            overall_status = "healthy"
        elif redis_status["connected"] or celery_status["running"]:
            overall_status = "degraded"
        else:
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "version": __version__,
            "services": {
                "redis": {
                    "status": "up" if redis_status["connected"] else "down",
                    "url": redis_status["url"],
                },
                "celery": {
                    "status": "up" if celery_status["running"] else "down",
                    "workers": celery_status.get("workers", []),
                    "count": celery_status.get("count", 0),
                },
            },
        }

    # Include routers
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
    app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
    app.include_router(meta.router, prefix="/api/meta", tags=["meta"])
    app.include_router(rl.router, prefix="/api/rl", tags=["rl"])
    app.include_router(models.router, prefix="/api/models", tags=["models"])
    app.include_router(playbooks.router, prefix="/api/playbooks", tags=["playbooks"])
    app.include_router(symbols.router, prefix="/api/symbols", tags=["symbols"])

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "darwin.api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )
