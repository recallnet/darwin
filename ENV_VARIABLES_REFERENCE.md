# Darwin Environment Variables Reference

Complete reference of all environment variables and where they're used.

## Your Current .env File Status

✅ **All variables properly configured**

### Variables in Your .env

```bash
# Core Darwin
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
AI_GATEWAY_API_KEY=vck_0zso... (configured ✅)
MODEL_ID=google/gemini-3-flash
REPLAY_LAB_URL=https://replay-lab-delta.preview.recall.network
REPLAY_LAB_API_KEY=rn_MtJm... (configured ✅)

# Darwin Configuration
DARWIN_ARTIFACTS_DIR=artifacts
DARWIN_LOG_LEVEL=INFO
DARWIN_LOG_FILE=darwin.log
DARWIN_DB_PATH=artifacts/darwin.db

# Database & Cache
DATABASE_URL=postgresql://michaelsena@localhost:5432/darwin_web
REDIS_URL=redis://localhost:6379/0

# Authentication & Security
JWT_SECRET_KEY=c703d64c... (configured ✅)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
NEXTAUTH_SECRET=89275aac... (configured ✅)
NEXTAUTH_URL=http://localhost:3001

# CORS
ALLOWED_ORIGINS=http://localhost:3001,http://localhost:3000,http://127.0.0.1:3001

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

# Email (commented out - optional)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
```

---

## Where Variables Are Used

### Docker Compose (Local Development)

**File**: `docker-compose.yml`

#### API Service (`api`)
```yaml
environment:
  DATABASE_URL: postgresql://darwin:password@postgres:5432/darwin_web  # Docker internal
  REDIS_URL: redis://redis:6379/0  # Docker internal
  AI_GATEWAY_API_KEY: ${AI_GATEWAY_API_KEY}  # From .env ✅
  AI_GATEWAY_BASE_URL: ${AI_GATEWAY_BASE_URL}  # From .env ✅
  MODEL_ID: ${MODEL_ID}  # From .env ✅
  JWT_SECRET_KEY: ${JWT_SECRET_KEY}  # From .env ✅
  JWT_ALGORITHM: ${JWT_ALGORITHM}  # From .env ✅
  ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES}  # From .env ✅
  ALLOWED_ORIGINS: ${ALLOWED_ORIGINS}  # From .env ✅
  API_HOST: ${API_HOST}  # From .env ✅
  API_PORT: ${API_PORT}  # From .env ✅
  REPLAY_LAB_URL: ${REPLAY_LAB_URL}  # From .env ✅
  REPLAY_LAB_API_KEY: ${REPLAY_LAB_API_KEY}  # From .env ✅
  DARWIN_ARTIFACTS_DIR: ${DARWIN_ARTIFACTS_DIR}  # From .env ✅
  DARWIN_LOG_LEVEL: ${DARWIN_LOG_LEVEL}  # From .env ✅
```

#### Worker Service (`worker`)
```yaml
environment:
  DATABASE_URL: postgresql://darwin:password@postgres:5432/darwin_web  # Docker internal
  REDIS_URL: redis://redis:6379/0  # Docker internal
  AI_GATEWAY_API_KEY: ${AI_GATEWAY_API_KEY}  # From .env ✅
  AI_GATEWAY_BASE_URL: ${AI_GATEWAY_BASE_URL}  # From .env ✅
  MODEL_ID: ${MODEL_ID}  # From .env ✅
  REPLAY_LAB_URL: ${REPLAY_LAB_URL}  # From .env ✅
  REPLAY_LAB_API_KEY: ${REPLAY_LAB_API_KEY}  # From .env ✅
  DARWIN_ARTIFACTS_DIR: ${DARWIN_ARTIFACTS_DIR}  # From .env ✅
  DARWIN_LOG_LEVEL: ${DARWIN_LOG_LEVEL}  # From .env ✅
```

#### Frontend Service (`frontend`)
```yaml
environment:
  NEXT_PUBLIC_API_URL: http://api:8000  # Docker internal (hardcoded)
  NEXTAUTH_URL: ${NEXTAUTH_URL}  # From .env ✅
  NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}  # From .env ✅
```

**Note**: DATABASE_URL and REDIS_URL use Docker internal service names (`postgres`, `redis`) instead of localhost.

---

### Railway Deployment (Production)

**Setup Guide**: `RAILWAY_SETUP.md`

#### API Service Variables (Railway)
```bash
# From Railway managed services
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Auto-populated by Railway
REDIS_URL=${{Redis.REDIS_URL}}  # Auto-populated by Railway

# From your .env (copy these values)
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
AI_GATEWAY_API_KEY=vck_0zsoAwNN1naMHIHOPAXfSPKpMnip2kJHTCaIwpZl3rcX5D0P4r3CuVHI
MODEL_ID=google/gemini-3-flash
JWT_SECRET_KEY=c703d64c27b1e2ad4f1e27199df12e372b18c26a93d6b05d212c28a9487dfe65
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REPLAY_LAB_URL=https://replay-lab-delta.preview.recall.network
REPLAY_LAB_API_KEY=rn_MtJmJCDDlCeZEQeLXgiaAyWHTqIRBkThAMKQrmdOxKZbiWJlSqUZqxdAgcyoTNdt

# Production-specific
ALLOWED_ORIGINS=https://darwin.vercel.app  # Update after Vercel deployment
API_HOST=0.0.0.0
API_PORT=8000

# Optional: Email
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
```

#### Worker Service Variables (Railway)
```bash
# From Railway managed services
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# From your .env (copy these values)
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
AI_GATEWAY_API_KEY=vck_0zsoAwNN1naMHIHOPAXfSPKpMnip2kJHTCaIwpZl3rcX5D0P4r3CuVHI
MODEL_ID=google/gemini-3-flash
REPLAY_LAB_URL=https://replay-lab-delta.preview.recall.network
REPLAY_LAB_API_KEY=rn_MtJmJCDDlCeZEQeLXgiaAyWHTqIRBkThAMKQrmdOxKZbiWJlSqUZqxdAgcyoTNdt
```

---

### Vercel Deployment (Frontend)

**Setup Guide**: `VERCEL_SETUP.md`

#### Frontend Variables (Vercel)
```bash
# API Connection (use Railway API URL after deployment)
NEXT_PUBLIC_API_URL=https://darwin-api.up.railway.app

# From your .env (copy these values)
NEXTAUTH_URL=https://darwin.vercel.app  # Update after first deployment
NEXTAUTH_SECRET=89275aacca2da38ac66eee8577ce86bd3c6b0f715eb6bc3bf1aaf9c4ca0a5446
```

---

## Variable Usage Matrix

| Variable | Local Dev | Docker | Railway API | Railway Worker | Vercel |
|----------|-----------|--------|-------------|----------------|--------|
| `AI_GATEWAY_API_KEY` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `AI_GATEWAY_BASE_URL` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `MODEL_ID` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `DATABASE_URL` | ✅ | ✅* | ✅ | ✅ | ❌ |
| `REDIS_URL` | ✅ | ✅* | ✅ | ✅ | ❌ |
| `JWT_SECRET_KEY` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `JWT_ALGORITHM` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `NEXTAUTH_SECRET` | ✅ | ✅ | ❌ | ❌ | ✅ |
| `NEXTAUTH_URL` | ✅ | ✅ | ❌ | ❌ | ✅ |
| `NEXT_PUBLIC_API_URL` | ✅ | ✅* | ❌ | ❌ | ✅** |
| `ALLOWED_ORIGINS` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `API_HOST` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `API_PORT` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `REPLAY_LAB_URL` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `REPLAY_LAB_API_KEY` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `DARWIN_ARTIFACTS_DIR` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `DARWIN_LOG_LEVEL` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `SMTP_HOST` | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |
| `SMTP_PORT` | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |
| `SMTP_USER` | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |
| `SMTP_PASSWORD` | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |

**Legend:**
- ✅ = Used and configured
- ❌ = Not needed for this environment
- ⚠️ = Optional (for email invitations)
- \* = Uses different value (Docker internal network)
- \*\* = Uses Railway API URL

---

## Environment-Specific Differences

### Docker Compose
- `DATABASE_URL`: Uses `postgres:5432` (Docker service name)
- `REDIS_URL`: Uses `redis:6379` (Docker service name)
- `NEXT_PUBLIC_API_URL`: Uses `http://api:8000` (Docker service name)

### Railway
- `DATABASE_URL`: Provided by Railway PostgreSQL service
- `REDIS_URL`: Provided by Railway Redis service
- `ALLOWED_ORIGINS`: Must include Vercel frontend URL

### Vercel
- `NEXT_PUBLIC_API_URL`: Must point to Railway API URL
- `NEXTAUTH_URL`: Must match Vercel deployment URL

---

## Validation

Run this to validate all variables:

```bash
python3 scripts/validate_deployment_env.py
```

**Current Status**: ✅ All required variables configured

**Warnings**:
- Localhost URLs will need updating for production
- SMTP not configured (team invitations disabled)

---

## Security Notes

### Secrets in .env (DO NOT COMMIT)
- ✅ `.gitignore` configured to exclude `.env`
- ✅ JWT secrets are 32+ characters (strong)
- ✅ NextAuth secret is 32+ characters (strong)
- ✅ API keys are masked in validation output

### Production Checklist
- [ ] Update `ALLOWED_ORIGINS` with production domains
- [ ] Update `NEXTAUTH_URL` with production Vercel URL
- [ ] Update `NEXT_PUBLIC_API_URL` with Railway API URL
- [ ] Verify all secrets are different from examples
- [ ] Configure SMTP if email invitations needed

---

## Quick Reference

### Generate New Secrets
```bash
# JWT secret
openssl rand -hex 32

# NextAuth secret
openssl rand -hex 32
```

### Check Variable
```bash
# Local
grep "VARIABLE_NAME" .env

# Docker
docker-compose config | grep VARIABLE_NAME

# Railway
railway variables
```

### Update Variable

**Local/Docker**: Edit `.env` file

**Railway**:
1. Go to service → Variables
2. Edit variable
3. Railway auto-redeploys

**Vercel**:
1. Go to project → Settings → Environment Variables
2. Edit variable
3. Vercel auto-redeploys

---

## Summary

✅ **Your .env file is complete and ready for:**
- Local development (`./start_services.sh`)
- Docker Compose (`docker-compose up`)
- Railway deployment (copy values from .env)
- Vercel deployment (copy values from .env)

All environment variables are properly configured in:
- ✅ `.env` file
- ✅ `docker-compose.yml`
- ✅ Railway setup guide
- ✅ Vercel setup guide

**Next step**: Choose deployment path (Docker local test or Railway deployment)
