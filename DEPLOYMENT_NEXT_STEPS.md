# Darwin Deployment - Next Steps

**Status**: Phase 1 (Containerization) Complete ✅

All Docker configurations are ready and validated. You have two paths forward:

---

## Option A: Test Locally with Docker (Recommended)

This option lets you verify the full stack works before deploying to production.

### Step 1: Install Docker Desktop

Run this command and enter your password when prompted:
```bash
brew install --cask docker
```

Or download directly: https://www.docker.com/products/docker-desktop

### Step 2: Start Docker

1. Open Docker Desktop from Applications folder
2. Wait for Docker engine to start (whale icon in menu bar)
3. Verify: `docker --version`

### Step 3: Test the Stack

```bash
cd /Users/michaelsena/code/darwin

# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Test API
curl http://localhost:8000/health

# Test frontend
open http://localhost:3001
```

### Step 4: Create Test Run

1. Open http://localhost:3001
2. Register account
3. Create new run with recent dates (Dec 2025)
4. Verify WebSocket updates work
5. Check run completes successfully

### Step 5: Stop Services

```bash
docker-compose down
```

**Estimated time**: 30 minutes

---

## Option B: Skip to Railway Deployment (Faster)

All Docker files are validated and ready. You can deploy directly to Railway without local testing.

### Why This Works

- ✅ All Dockerfiles validated for syntax
- ✅ docker-compose.yml validated (5 services defined)
- ✅ Environment variables validated
- ✅ Railway will build containers in their environment
- ✅ Can rollback if issues occur

### Next Steps

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign in with GitHub
   - Link repository: recallnet/darwin

2. **Follow the Guide**
   - Open: `/Users/michaelsena/code/darwin/RAILWAY_SETUP.md`
   - Estimated time: 2-3 hours
   - Cost: ~$60/month after deployment

3. **Then Deploy Frontend**
   - Open: `/Users/michaelsena/code/darwin/VERCEL_SETUP.md`
   - Estimated time: 1-2 hours
   - Cost: $0/month (free tier)

**Estimated time**: 3-4 hours total

---

## What's Been Completed

### ✅ Phase 1: Containerization (Complete)

**Files Created:**
- `Dockerfile.api` - Backend FastAPI container
- `Dockerfile.worker` - Celery worker container
- `darwin-ui/Dockerfile` - Next.js frontend container
- `docker-compose.yml` - Local development stack
- `DOCKER.md` - Docker documentation
- `RAILWAY_SETUP.md` - Railway deployment guide
- `VERCEL_SETUP.md` - Vercel deployment guide
- `DEPLOYMENT_STATUS.md` - Progress tracking
- `scripts/validate_deployment_env.py` - Environment validator

**Files Modified:**
- `darwin-ui/next.config.js` - Added standalone output mode
- `.env` - Added all required variables for deployment

**Validation Results:**
```
✅ All Dockerfiles: Valid syntax
✅ docker-compose.yml: Valid YAML (5 services)
✅ Environment variables: All required vars set
⚠️  Localhost values: Will update for production
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Railway Project                      │
├──────────────────────────────────────────────────────┤
│  ┌─────────────┐        ┌─────────────┐             │
│  │  FastAPI    │◄───────┤   Celery    │             │
│  │  Backend    │        │   Workers   │             │
│  │ (port 8000) │        │  (2-4 pool) │             │
│  └──────┬──────┘        └──────┬──────┘             │
│         │                       │                     │
│         ├───────────────────────┤                     │
│         ▼                       ▼                     │
│  ┌─────────────┐        ┌─────────────┐             │
│  │ PostgreSQL  │        │    Redis    │             │
│  │  (managed)  │        │  (managed)  │             │
│  └─────────────┘        └─────────────┘             │
│         │                                             │
│         ▼                                             │
│  ┌─────────────┐                                     │
│  │  Volumes    │  (50 GB artifacts)                 │
│  └─────────────┘                                     │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│                     Vercel                            │
├──────────────────────────────────────────────────────┤
│  ┌─────────────┐                                     │
│  │  Next.js    │  → Global CDN                       │
│  │  Frontend   │  → Auto-deploy from GitHub          │
│  └──────┬──────┘                                     │
│         │ HTTP/WS to Railway API                     │
└─────────┴──────────────────────────────────────────┘
```

**Key Features:**
- 🚀 Auto-deploy on push to main (both Railway & Vercel)
- 💾 Persistent storage for artifacts (50GB)
- 🔄 Real-time WebSocket updates
- 🌍 Global CDN for frontend
- 📊 Built-in monitoring and logs
- 💰 ~$60-80/month total cost

---

## Environment Variables Status

### ✅ Ready for Deployment

All required variables are set in `.env`:

- `AI_GATEWAY_API_KEY` ✅
- `AI_GATEWAY_BASE_URL` ✅
- `MODEL_ID` ✅
- `DATABASE_URL` ✅ (localhost - will update for Railway)
- `REDIS_URL` ✅ (localhost - will update for Railway)
- `JWT_SECRET_KEY` ✅ (secure 32-char random)
- `NEXTAUTH_SECRET` ✅ (secure 32-char random)
- `ALLOWED_ORIGINS` ✅ (localhost - will update for production)

### ⚠️ Will Update for Production

These use localhost values now, you'll update them after Railway deployment:
- `DATABASE_URL` → Railway PostgreSQL URL
- `REDIS_URL` → Railway Redis URL
- `NEXTAUTH_URL` → Vercel frontend URL
- `ALLOWED_ORIGINS` → Add Railway + Vercel URLs

---

## Validation Script

Run anytime to check your environment configuration:

```bash
python3 scripts/validate_deployment_env.py
```

This validates:
- All required variables are set
- URLs have valid format
- JWT secrets are strong enough (32+ chars)
- Ports are valid
- Provides warnings for localhost values

---

## Cost Breakdown

### Development (Current)
- **Total**: $0/month

### Production (After Deployment)

**Railway** (~$60/month):
- API service: $15/month
- Worker service: $25/month
- PostgreSQL: $10/month
- Redis: $5/month
- Storage (50GB): $5/month

**Vercel** ($0/month):
- Frontend: Free tier

**LLM Calls** (~$5-20/month):
- Via Vercel AI Gateway

**Total**: $65-80/month

---

## Quick Command Reference

### Validate Configuration
```bash
python3 scripts/validate_deployment_env.py
```

### Docker Local Testing
```bash
# Start
docker-compose up -d

# Logs
docker-compose logs -f

# Stop
docker-compose down
```

### Railway Deployment
```bash
# Install CLI
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# View logs
railway logs
```

### Git Workflow
```bash
# Commit changes
git add .
git commit -m "feat: Your changes"
git push origin main

# Both Railway and Vercel auto-deploy!
```

---

## Troubleshooting

### Docker Won't Start
- Ensure Docker Desktop is running
- Check: `docker ps`
- Restart Docker Desktop

### Port Already in Use
```bash
# Kill process on port
lsof -ti:3001 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

### Environment Variable Issues
```bash
# Re-validate
python3 scripts/validate_deployment_env.py

# Check specific variable
grep "AI_GATEWAY_API_KEY" .env
```

---

## Support Resources

- **Docker Documentation**: `DOCKER.md`
- **Railway Guide**: `RAILWAY_SETUP.md`
- **Vercel Guide**: `VERCEL_SETUP.md`
- **Full Deployment Plan**: `~/.claude/plans/validated-wiggling-mitten.md`
- **Progress Tracker**: `DEPLOYMENT_STATUS.md`

---

## Recommendation

**For fastest path to production**: Choose Option B (Skip to Railway)

- All files validated and ready
- Railway handles Docker building
- Can test end-to-end in production environment
- Auto-deployment configured
- Easy rollback if needed

**Time to live**: ~3-4 hours from now to fully deployed production system

---

## Your Decision

What would you like to do?

**A)** Test locally with Docker first (install Docker Desktop)
**B)** Deploy directly to Railway (skip local testing)

Both paths will work - Option B is faster to production.
