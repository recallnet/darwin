# Railway Deployment Guide

Step-by-step instructions for deploying Darwin to Railway with automatic deployment from GitHub.

## Prerequisites

✅ Phase 1 complete (Docker files created)
✅ `.env` file configured with all required variables
⏳ Docker testing (optional but recommended)

## Overview

This guide will help you:
1. Create a Railway account and project
2. Deploy PostgreSQL and Redis databases
3. Deploy the FastAPI backend
4. Deploy Celery workers
5. Configure auto-deployment from GitHub

**Estimated time**: 2-3 hours

---

## Step 1: Create Railway Account (5 minutes)

1. Go to https://railway.app
2. Click "Login" and sign in with GitHub
3. Authorize Railway to access your GitHub account
4. Complete account setup

**Note**: Railway offers $5 free credit per month. After that, you'll be charged based on usage.

---

## Step 2: Create New Project (2 minutes)

1. Click "New Project" in the Railway dashboard
2. Select "Deploy from GitHub repo"
3. Choose the repository: `recallnet/darwin`
4. Railway will create a new project and link it to your GitHub repo

**Important**: Keep this project page open - you'll be adding services to it.

---

## Step 3: Add PostgreSQL Database (5 minutes)

1. In your Railway project, click "New" → "Database" → "Add PostgreSQL"
2. Railway will provision a managed PostgreSQL instance
3. Once created, click the PostgreSQL service
4. Go to "Variables" tab
5. Copy the `DATABASE_URL` value (you'll need this for API and Worker services)

**Note**: Railway automatically manages backups (7-day retention).

---

## Step 4: Add Redis Database (5 minutes)

1. In your Railway project, click "New" → "Database" → "Add Redis"
2. Railway will provision a managed Redis instance
3. Once created, click the Redis service
4. Go to "Variables" tab
5. Copy the `REDIS_URL` value (you'll need this for API and Worker services)

---

## Step 5: Deploy API Service (30 minutes)

### 5.1 Create Service

1. In your Railway project, click "New" → "GitHub Repo"
2. Select `recallnet/darwin` repository
3. Railway will detect Dockerfiles automatically
4. Configure the service:
   - **Name**: `darwin-api`
   - **Root Directory**: `/` (leave as default)
   - **Dockerfile Path**: `Dockerfile.api`

### 5.2 Configure Environment Variables

Click the service → "Variables" tab → "RAW Editor" and add:

```bash
# Database connections (use values from Step 3 & 4)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# AI Gateway
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
AI_GATEWAY_API_KEY=vck_0zsoAwNN1naMHIHOPAXfSPKpMnip2kJHTCaIwpZl3rcX5D0P4r3CuVHI
MODEL_ID=google/gemini-3-flash

# JWT Authentication
JWT_SECRET_KEY=c703d64c27b1e2ad4f1e27199df12e372b18c26a93d6b05d212c28a9487dfe65
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS (will update after Vercel deployment)
ALLOWED_ORIGINS=http://localhost:3001

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Replay Lab (optional)
REPLAY_LAB_URL=https://replay-lab-delta.preview.recall.network
REPLAY_LAB_API_KEY=rn_MtJmJCDDlCeZEQeLXgiaAyWHTqIRBkThAMKQrmdOxKZbiWJlSqUZqxdAgcyoTNdt

# Email (optional - uncomment to enable team invitations)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASSWORD=your-app-password
```

### 5.3 Configure Watch Paths (for auto-deployment)

1. Click service → "Settings" tab
2. Scroll to "Watch Paths"
3. Enable "Watch Paths"
4. Add these paths (one per line):
   ```
   darwin/**
   tools/**
   pyproject.toml
   Dockerfile.api
   ```

**What this does**: Railway will only rebuild/redeploy when changes are pushed to these paths.

### 5.4 Add Persistent Storage

1. Click service → "Settings" tab
2. Scroll to "Volumes"
3. Click "New Volume"
4. Configure:
   - **Mount Path**: `/app/artifacts`
   - **Size**: 50 GB
5. Click "Add"

### 5.5 Configure Health Check

1. Click service → "Settings" tab
2. Scroll to "Health Check"
3. Configure:
   - **Path**: `/health`
   - **Interval**: 30 seconds
4. Click "Save"

### 5.6 Deploy

1. Click "Deploy"
2. Railway will build the Docker image and deploy
3. Watch the build logs in the "Deployments" tab
4. Wait for deployment to complete (usually 3-5 minutes)

### 5.7 Get Public URL

1. Click service → "Settings" tab
2. Scroll to "Networking"
3. Click "Generate Domain"
4. Railway will provide a public URL like: `darwin-api.up.railway.app`
5. **Copy this URL** - you'll need it for Vercel frontend

### 5.8 Verify Deployment

Test the API:
```bash
curl https://darwin-api.up.railway.app/health
```

Expected response:
```json
{"status":"healthy"}
```

---

## Step 6: Deploy Worker Service (20 minutes)

### 6.1 Create Service

1. In your Railway project, click "New" → "GitHub Repo"
2. Select `recallnet/darwin` repository
3. Configure the service:
   - **Name**: `darwin-worker`
   - **Root Directory**: `/` (leave as default)
   - **Dockerfile Path**: `Dockerfile.worker`

### 6.2 Configure Environment Variables

Click the service → "Variables" tab → "RAW Editor" and add:

```bash
# Database connections (use values from Step 3 & 4)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}

# AI Gateway
AI_GATEWAY_BASE_URL=https://ai-gateway.vercel.sh/v1
AI_GATEWAY_API_KEY=vck_0zsoAwNN1naMHIHOPAXfSPKpMnip2kJHTCaIwpZl3rcX5D0P4r3CuVHI
MODEL_ID=google/gemini-3-flash

# Replay Lab (optional)
REPLAY_LAB_URL=https://replay-lab-delta.preview.recall.network
REPLAY_LAB_API_KEY=rn_MtJmJCDDlCeZEQeLXgiaAyWHTqIRBkThAMKQrmdOxKZbiWJlSqUZqxdAgcyoTNdt
```

### 6.3 Configure Watch Paths

1. Click service → "Settings" tab
2. Scroll to "Watch Paths"
3. Enable "Watch Paths"
4. Add these paths:
   ```
   darwin/**
   tools/**
   pyproject.toml
   Dockerfile.worker
   ```

### 6.4 Add Persistent Storage

1. Click service → "Settings" tab
2. Scroll to "Volumes"
3. Click "New Volume"
4. Configure:
   - **Mount Path**: `/app/artifacts`
   - **Size**: 50 GB
5. Click "Add"

### 6.5 Deploy

1. Click "Deploy"
2. Wait for deployment to complete
3. Check logs to verify Celery worker started successfully

### 6.6 Verify Worker

Check logs for this message:
```
celery@worker ready.
```

---

## Step 7: Test Auto-Deployment (10 minutes)

Now that both services are deployed, let's verify auto-deployment works.

### 7.1 Make a Small Change

Create a test file:
```bash
echo "# Railway deployment test" > /Users/michaelsena/code/darwin/RAILWAY_TEST.md
git add RAILWAY_TEST.md
git commit -m "test: Verify Railway auto-deployment"
git push origin main
```

### 7.2 Watch Railway Deploy

1. Go to Railway dashboard
2. Click on the `darwin-api` service
3. Go to "Deployments" tab
4. You should see a new deployment triggered automatically
5. Repeat for `darwin-worker` service

**Expected behavior**: Both services should rebuild and redeploy automatically within 3-5 minutes.

### 7.3 Clean Up Test File

```bash
git rm RAILWAY_TEST.md
git commit -m "test: Remove Railway test file"
git push origin main
```

---

## Step 8: Configure Production Settings (10 minutes)

### 8.1 Update API CORS Settings

Once you deploy the frontend to Vercel (next phase), update the CORS settings:

1. Click `darwin-api` service → "Variables"
2. Update `ALLOWED_ORIGINS`:
   ```
   ALLOWED_ORIGINS=https://darwin.vercel.app,https://your-custom-domain.com
   ```
3. Railway will automatically redeploy

### 8.2 Enable Email Invitations (Optional)

If you want team invitation emails:

1. Set up Gmail App Password or SMTP service
2. Add these variables to `darwin-api`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   ```

---

## Step 9: Monitoring & Logs (5 minutes)

### View Logs

1. Click service → "Deployments" tab
2. Click the active deployment
3. View real-time logs

### Set Up Alerts

1. Click service → "Settings" tab
2. Scroll to "Notifications"
3. Enable deployment notifications
4. Add your email or Slack webhook

---

## Troubleshooting

### Build fails

**Check Dockerfile syntax**:
```bash
docker build -f Dockerfile.api -t test .
```

**Check logs** in Railway dashboard for specific errors.

### Database connection fails

**Verify DATABASE_URL**:
1. Click PostgreSQL service → "Variables"
2. Copy the `DATABASE_URL`
3. Verify it's set correctly in API and Worker services

### Worker not processing tasks

**Check Redis connection**:
1. Click Redis service → "Variables"
2. Verify `REDIS_URL` is correct in Worker service

**Check worker logs** for connection errors.

### Health check failing

**Test locally**:
```bash
curl https://darwin-api.up.railway.app/health
```

**Check API logs** for startup errors.

### Auto-deployment not triggering

**Verify watch paths** are configured correctly in Settings.

**Check GitHub webhook** in Railway project settings.

---

## Cost Monitoring

### View Current Usage

1. Click your profile → "Billing"
2. View current month usage
3. Set up budget alerts

### Estimated Monthly Cost

Based on current configuration:
- API service (1 vCPU, 2GB RAM): ~$15/month
- Worker service (2 vCPU, 4GB RAM): ~$25/month
- PostgreSQL (1GB): ~$10/month
- Redis (256MB): ~$5/month
- Storage (50GB): ~$5/month

**Total**: ~$60/month (excluding LLM API calls)

---

## Next Steps

✅ Railway deployment complete!

**Continue to Phase 3**: Deploy frontend to Vercel

See: Full deployment plan at `~/.claude/plans/validated-wiggling-mitten.md`

---

## Rollback

If something goes wrong:

1. Click service → "Deployments" tab
2. Find the previous working deployment
3. Click three dots → "Redeploy"
4. Railway will rollback to that version

---

## Support

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: https://github.com/recallnet/darwin/issues
