# Darwin Docker Setup

This guide covers running Darwin locally using Docker Compose.

## Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose)
- Git
- `.env` file with required variables

## Quick Start

1. **Copy environment variables**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and set required variables**:
   - `AI_GATEWAY_API_KEY`: Your Vercel AI Gateway API key
   - `JWT_SECRET_KEY`: Random 32-character string (generate with `openssl rand -hex 32`)
   - `NEXTAUTH_SECRET`: Random 32-character string (generate with `openssl rand -hex 32`)

3. **Start all services**:
   ```bash
   docker-compose up -d
   ```

4. **Check service status**:
   ```bash
   docker-compose ps
   ```

5. **View logs**:
   ```bash
   docker-compose logs -f

   # View specific service logs
   docker-compose logs -f api
   docker-compose logs -f worker
   docker-compose logs -f frontend
   ```

6. **Access the application**:
   - Frontend: http://localhost:3001
   - API Docs: http://localhost:8000/docs
   - API Health: http://localhost:8000/health

## Services

The Docker Compose stack includes:

- **postgres**: PostgreSQL 16 database (port 5432)
- **redis**: Redis 7 for Celery broker/backend (port 6379)
- **api**: FastAPI backend (port 8000)
- **worker**: Celery workers for background jobs
- **frontend**: Next.js web UI (port 3001)

## Common Commands

### Start services
```bash
docker-compose up -d
```

### Stop services
```bash
docker-compose down
```

### Restart a specific service
```bash
docker-compose restart api
docker-compose restart worker
docker-compose restart frontend
```

### Rebuild containers after code changes
```bash
docker-compose up -d --build
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
```

### Execute commands inside containers
```bash
# Run database migrations
docker-compose exec api python -m alembic -c darwin/api/db/migrations/alembic.ini upgrade head

# Access PostgreSQL
docker-compose exec postgres psql -U darwin -d darwin_web

# Access Redis CLI
docker-compose exec redis redis-cli

# Python shell in API container
docker-compose exec api python
```

### Clean up volumes (⚠️ destroys data)
```bash
docker-compose down -v
```

## Troubleshooting

### Port conflicts
If ports 3001, 8000, 5432, or 6379 are already in use:

```bash
# Find and kill process on port
lsof -ti:3001 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

Or edit `docker-compose.yml` to use different ports.

### API won't start
Check database connection:
```bash
docker-compose logs postgres
docker-compose logs api
```

Ensure migrations ran successfully:
```bash
docker-compose exec api python -m alembic -c darwin/api/db/migrations/alembic.ini current
```

### Worker not processing tasks
Check Celery connection to Redis:
```bash
docker-compose logs redis
docker-compose logs worker
```

Verify worker is registered:
```bash
docker-compose exec api celery -A darwin.api.celery_app inspect active
```

### Frontend can't connect to API
Check CORS settings in `.env`:
```bash
ALLOWED_ORIGINS=http://localhost:3001,http://localhost:3000
```

Verify API is accessible:
```bash
curl http://localhost:8000/health
```

### Build errors
Clear Docker cache and rebuild:
```bash
docker-compose down
docker system prune -a
docker-compose up -d --build
```

## Development Workflow

### Making code changes

1. **Backend changes** (darwin/, tools/):
   ```bash
   docker-compose restart api
   docker-compose restart worker
   ```

2. **Frontend changes** (darwin-ui/):
   ```bash
   docker-compose restart frontend
   ```

3. **Dependency changes** (pyproject.toml, package.json):
   ```bash
   docker-compose up -d --build
   ```

### Database migrations

Create new migration:
```bash
docker-compose exec api python -m alembic -c darwin/api/db/migrations/alembic.ini revision --autogenerate -m "description"
```

Apply migrations:
```bash
docker-compose exec api python -m alembic -c darwin/api/db/migrations/alembic.ini upgrade head
```

### Accessing artifacts

Artifacts are stored in `./artifacts` and mounted into both API and Worker containers.

## Production Deployment

For production deployment to Railway + Vercel, see the deployment plan at:
`/Users/michaelsena/.claude/plans/validated-wiggling-mitten.md`

## Performance Tips

### Adjust worker concurrency
Edit `docker-compose.yml`:
```yaml
worker:
  environment:
    CELERY_WORKER_CONCURRENCY: 4  # Default: 2
```

### Increase PostgreSQL resources
Edit `docker-compose.yml`:
```yaml
postgres:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
```

### Use volumes for faster rebuilds
Uncomment volume mounts in `docker-compose.yml` for hot-reloading during development.

## Security Notes

- **Never commit `.env`** - it contains secrets
- Change default passwords in production
- Use strong JWT secrets (32+ characters)
- Enable HTTPS in production
- Configure proper CORS origins
- Use environment-specific configs

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Verify services: `docker-compose ps`
- Inspect containers: `docker-compose exec <service> /bin/sh`
- Review deployment plan: `~/.claude/plans/validated-wiggling-mitten.md`
