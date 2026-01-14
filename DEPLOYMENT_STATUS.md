# Darwin Deployment Status

Last updated: 2026-01-13

## Overview

This document tracks the progress of deploying Darwin to production with Railway + Vercel, including automatic deployment on push to main.

Full deployment plan: `~/.claude/plans/validated-wiggling-mitten.md`

---

## Phase 1: Containerization ✅ COMPLETE

**Status**: Complete
**Date completed**: 2026-01-13

### Files Created

- ✅ `Dockerfile.api` - FastAPI backend container configuration
- ✅ `Dockerfile.worker` - Celery worker container configuration
- ✅ `darwin-ui/Dockerfile` - Next.js frontend container configuration
- ✅ `docker-compose.yml` - Local development stack (PostgreSQL, Redis, API, Worker, Frontend)
- ✅ `DOCKER.md` - Comprehensive Docker setup documentation

### Files Modified

- ✅ `darwin-ui/next.config.js` - Added `output: 'standalone'` for containerized deployment

### Verification Pending

⚠️ **Local Docker testing required** (Docker not installed on current system)

To test locally, user needs to:
1. Install Docker Desktop
2. Copy `.env.example` to `.env` and set required variables:
   - `AI_GATEWAY_API_KEY`
   - `JWT_SECRET_KEY` (generate: `openssl rand -hex 32`)
   - `NEXTAUTH_SECRET` (generate: `openssl rand -hex 32`)
3. Run: `docker-compose up -d`
4. Verify all services start successfully
5. Test: http://localhost:3001 (frontend), http://localhost:8000/docs (API)

---

## Phase 2: Railway Deployment ⏳ PENDING

**Status**: Not started
**Estimated duration**: 2-3 hours

### Prerequisites
- [ ] Docker testing complete (Phase 1 verification)
- [ ] Railway account created
- [ ] GitHub repository linked to Railway

### Tasks

1. **Create Railway Project**
   - [ ] Sign up at https://railway.app
   - [ ] Link GitHub repository: recallnet/darwin
   - [ ] Create new project

2. **Add Databases**
   - [ ] Add PostgreSQL database service
   - [ ] Add Redis database service
   - [ ] Note connection strings

3. **Deploy API Service**
   - [ ] Create service from GitHub repo
   - [ ] Set root directory: `/`
   - [ ] Set Dockerfile path: `Dockerfile.api`
   - [ ] Configure environment variables (see plan)
   - [ ] Add watch paths: `darwin/`, `tools/`, `pyproject.toml`, `Dockerfile.api`
   - [ ] Add persistent storage: `/app/artifacts` (50GB)
   - [ ] Configure health check: `/health`
   - [ ] Verify deployment

4. **Deploy Worker Service**
   - [ ] Create service from GitHub repo
   - [ ] Set root directory: `/`
   - [ ] Set Dockerfile path: `Dockerfile.worker`
   - [ ] Configure environment variables (see plan)
   - [ ] Add watch paths: `darwin/`, `tools/`, `pyproject.toml`, `Dockerfile.worker`
   - [ ] Add persistent storage: `/app/artifacts` (50GB)
   - [ ] Verify deployment

5. **Verify Auto-Deployment**
   - [ ] Confirm watch paths configured correctly
   - [ ] Test: Make small change and push to main
   - [ ] Verify Railway auto-deploys both services

6. **Get Public URL**
   - [ ] Copy API public domain (e.g., `darwin-api.up.railway.app`)
   - [ ] Test: `curl https://<api-url>/health`

### Environment Variables Required

See deployment plan for full list. Key variables:
- `DATABASE_URL` (from PostgreSQL service)
- `REDIS_URL` (from Redis service)
- `AI_GATEWAY_API_KEY`
- `AI_GATEWAY_BASE_URL`
- `MODEL_ID`
- `JWT_SECRET_KEY`
- `ALLOWED_ORIGINS` (will include Vercel domain from Phase 3)

---

## Phase 3: Vercel Deployment ⏳ PENDING

**Status**: Not started
**Estimated duration**: 1-2 hours
**Depends on**: Phase 2 (Railway API URL needed)

### Tasks

1. **Deploy to Vercel**
   - [ ] Sign up at https://vercel.com
   - [ ] Import GitHub repository: recallnet/darwin
   - [ ] Set root directory: `darwin-ui`
   - [ ] Set production branch: `main`
   - [ ] Configure environment variables:
     - `NEXT_PUBLIC_API_URL`: Railway API URL from Phase 2
     - `NEXTAUTH_URL`: Vercel deployment URL
     - `NEXTAUTH_SECRET`: Random 32-char string
   - [ ] Deploy

2. **Update Railway CORS**
   - [ ] Add Vercel domain to Railway API `ALLOWED_ORIGINS`
   - [ ] Format: `https://darwin.vercel.app,https://<custom-domain>`

3. **Verify Auto-Deployment**
   - [ ] Confirm production branch is `main`
   - [ ] Test: Make small change to frontend and push to main
   - [ ] Verify Vercel auto-deploys

4. **Test End-to-End**
   - [ ] Open Vercel URL
   - [ ] Login/register
   - [ ] Create new run
   - [ ] Verify WebSocket real-time updates work
   - [ ] Check run completes successfully
   - [ ] View report with charts

---

## Phase 4: Database Migration ⏳ PENDING

**Status**: Not started
**Estimated duration**: 2-3 hours
**Depends on**: Phase 2 & 3 complete

### Tasks

1. **Export Local Data**
   - [ ] Export PostgreSQL: `pg_dump darwin_web > darwin_backup.sql`
   - [ ] Export artifacts: `tar -czf artifacts_backup.tar.gz artifacts/`

2. **Import to Railway**
   - [ ] Install Railway CLI: `npm i -g @railway/cli`
   - [ ] Login: `railway login`
   - [ ] Link project: `railway link`
   - [ ] Import database: `railway run psql < darwin_backup.sql`
   - [ ] Upload artifacts to Railway volume (manual or via scp)

3. **Verify Data Integrity**
   - [ ] Check user count: `railway run psql -c "SELECT COUNT(*) FROM users;"`
   - [ ] Check teams: `railway run psql -c "SELECT COUNT(*) FROM teams;"`
   - [ ] Check run metadata: `railway run psql -c "SELECT COUNT(*) FROM run_metadata;"`
   - [ ] Test run execution with migrated data

---

## Phase 5: Monitoring & Hardening ⏳ PENDING

**Status**: Not started
**Estimated duration**: 3-4 hours
**Depends on**: Phase 2, 3, 4 complete

### Tasks

1. **Error Tracking (Sentry)**
   - [ ] Sign up at https://sentry.io
   - [ ] Get DSN
   - [ ] Add Sentry SDK to `darwin/api/main.py`
   - [ ] Add `SENTRY_DSN` to Railway environment
   - [ ] Test error capture

2. **Uptime Monitoring**
   - [ ] Sign up at https://uptimerobot.com
   - [ ] Add monitor for API health endpoint
   - [ ] Add monitor for frontend
   - [ ] Configure email/Slack alerts

3. **Security Hardening**
   - [ ] Create `darwin/api/middleware/security.py`
   - [ ] Add security headers middleware to `darwin/api/main.py`
   - [ ] Add rate limiting with slowapi
   - [ ] Update `pyproject.toml` with slowapi dependency
   - [ ] Test rate limiting

4. **Backup Configuration**
   - [ ] Verify Railway automatic backups enabled (daily, 7-day retention)
   - [ ] Set up manual weekly backup script
   - [ ] Document backup restoration procedure

5. **Final Production Checks**
   - [ ] Review all environment variables
   - [ ] Verify CORS settings
   - [ ] Check JWT secret strength
   - [ ] Verify HTTPS enforced
   - [ ] Test email invitations
   - [ ] Review Railway logs
   - [ ] Monitor error rates in Sentry

---

## Optional: GitHub Actions CI ⏳ PENDING

**Status**: Not started
**Priority**: Medium (nice to have)

### Tasks

- [ ] Create `.github/workflows/test.yml`
- [ ] Configure Python tests
- [ ] Configure frontend build tests
- [ ] Test on pull requests
- [ ] Test on push to main (before auto-deploy)

---

## Success Criteria

- [ ] All services deployed and accessible via public URLs
- [ ] Database migrated successfully
- [ ] Users can register and login
- [ ] Users can create and launch runs
- [ ] Real-time progress updates work via WebSockets
- [ ] Reports generate with charts
- [ ] Health checks passing
- [ ] Monitoring and alerts configured
- [ ] Automatic deployment working (push to main → auto-deploy)
- [ ] Backups running
- [ ] Monthly cost within budget ($65-80 for small team)

---

## Cost Tracking

### Current (Local Development)
- **Total**: $0/month

### Projected (After Full Deployment)

**Railway** ($60/month):
- API service (1 vCPU, 2GB RAM): $15/month
- Worker service (2 vCPU, 4GB RAM): $25/month
- PostgreSQL (1GB): $10/month
- Redis (256MB): $5/month
- Storage (50GB): $5/month

**Vercel** ($0/month):
- Frontend (free tier): $0/month

**Additional** ($5-20/month):
- LLM calls via Vercel AI Gateway: $5-20/month
- Sentry error tracking (free tier): $0/month
- UptimeRobot monitoring (free tier): $0/month

**Estimated Total**: $65-80/month

---

## Rollback Plan

If deployment fails at any phase:

1. **Railway Issues**: Revert to previous deployment via Railway dashboard
2. **Vercel Issues**: Revert to previous deployment via Vercel dashboard
3. **Database Issues**: Restore from Railway automatic backup
4. **Complete Failure**: Run locally using `./start_services.sh` (existing scripts)

---

## Notes

- Auto-deployment is built into both Railway and Vercel - no GitHub Actions workflows needed for deployment
- Optional GitHub Actions can be added for testing before deployment
- Both platforms deploy automatically on push to `main` branch
- Preview deployments: Vercel creates previews for PRs automatically
- Railway watch paths ensure only relevant changes trigger backend rebuilds
- Estimated timeline: 5 weeks total (can be accelerated if needed)

---

## Next Steps

1. ✅ Complete Phase 1 containerization
2. ⏳ Test Docker setup locally (requires Docker installation)
3. ⏳ Proceed to Phase 2 (Railway deployment)
4. ⏳ After Railway deployed, proceed to Phase 3 (Vercel deployment)
5. ⏳ Continue with remaining phases

---

## Questions / Blockers

### Current Blockers
- **Docker testing**: Docker not installed on current system. User needs to install Docker Desktop to verify Phase 1 locally before proceeding to Railway.

### Open Questions
None currently.

---

## Resources

- **Full Deployment Plan**: `~/.claude/plans/validated-wiggling-mitten.md`
- **Docker Documentation**: `DOCKER.md`
- **Railway Dashboard**: https://railway.app
- **Vercel Dashboard**: https://vercel.com
- **GitHub Repository**: https://github.com/recallnet/darwin
