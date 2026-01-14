# Vercel Deployment Guide

Step-by-step instructions for deploying the Darwin frontend to Vercel with automatic deployment from GitHub.

## Prerequisites

✅ Phase 2 complete (Railway backend deployed)
✅ Railway API public URL available
✅ `darwin-ui/next.config.js` configured with `output: 'standalone'`

## Overview

This guide will help you:
1. Create a Vercel account
2. Import the GitHub repository
3. Configure environment variables
4. Deploy the Next.js frontend
5. Configure auto-deployment
6. Update Railway CORS settings

**Estimated time**: 1-2 hours

---

## Step 1: Create Vercel Account (5 minutes)

1. Go to https://vercel.com
2. Click "Sign Up"
3. Choose "Continue with GitHub"
4. Authorize Vercel to access your GitHub account
5. Complete account setup

**Note**: Vercel's free "Hobby" tier is perfect for Darwin and includes:
- Unlimited deployments
- Automatic HTTPS
- Global CDN
- 100GB bandwidth/month

---

## Step 2: Import GitHub Repository (10 minutes)

### 2.1 Start Import

1. In Vercel dashboard, click "Add New..." → "Project"
2. Under "Import Git Repository", find `recallnet/darwin`
3. Click "Import"

### 2.2 Configure Project

**Important settings**:

- **Framework Preset**: Next.js (auto-detected)
- **Root Directory**: `darwin-ui`
  - Click "Edit" next to Root Directory
  - Enter: `darwin-ui`
  - Click "Continue"
- **Build Command**: `npm run build` (default, leave as-is)
- **Output Directory**: `.next` (default, leave as-is)
- **Install Command**: `npm install` (default, leave as-is)

### 2.3 Configure Environment Variables

Click "Environment Variables" and add these variables:

#### Required Variables

```bash
# API Connection (use your Railway API URL from Phase 2)
NEXT_PUBLIC_API_URL=https://darwin-api.up.railway.app

# NextAuth Configuration
NEXTAUTH_URL=https://your-app.vercel.app
NEXTAUTH_SECRET=89275aacca2da38ac66eee8577ce86bd3c6b0f715eb6bc3bf1aaf9c4ca0a5446
```

**Important**:
- Replace `https://darwin-api.up.railway.app` with your actual Railway API URL
- The `NEXTAUTH_URL` will be auto-generated after first deployment - you'll update it in Step 4

### 2.4 Deploy

1. Click "Deploy"
2. Vercel will:
   - Clone your repository
   - Install dependencies
   - Build the Next.js app
   - Deploy to global CDN
3. Wait for deployment (usually 1-2 minutes)

### 2.5 Get Deployment URL

Once deployed, you'll see:
- **Production URL**: `https://darwin-<random>.vercel.app`
- Or custom domain if configured

**Copy this URL** - you'll need it for the next steps.

---

## Step 3: Update Environment Variables (5 minutes)

After first deployment, update the `NEXTAUTH_URL`:

1. Go to project → "Settings" → "Environment Variables"
2. Find `NEXTAUTH_URL`
3. Click "Edit"
4. Update to your actual Vercel URL: `https://darwin-<random>.vercel.app`
5. Click "Save"
6. Vercel will automatically redeploy

---

## Step 4: Update Railway CORS (5 minutes)

Now that you have the Vercel URL, update Railway API CORS settings:

1. Go to Railway dashboard
2. Click `darwin-api` service
3. Go to "Variables" tab
4. Update `ALLOWED_ORIGINS`:
   ```
   ALLOWED_ORIGINS=https://darwin-<random>.vercel.app
   ```
5. Railway will automatically redeploy the API

**Note**: Add multiple origins separated by commas if you have multiple domains.

---

## Step 5: Configure Production Branch (2 minutes)

Set up auto-deployment from main branch:

1. In Vercel project, go to "Settings" → "Git"
2. Under "Production Branch", verify it's set to: `main`
3. Under "Deploy Hooks", optionally create a deploy hook for manual triggers

**What this does**: Every push to `main` branch will automatically deploy to production.

---

## Step 6: Test Auto-Deployment (10 minutes)

Verify auto-deployment works:

### 6.1 Make a Small Change

Update a frontend file:
```bash
cd /Users/michaelsena/code/darwin/darwin-ui
echo "// Vercel deployment test" >> app/layout.tsx
git add app/layout.tsx
git commit -m "test: Verify Vercel auto-deployment"
git push origin main
```

### 6.2 Watch Vercel Deploy

1. Go to Vercel dashboard
2. Click your project
3. You should see a new deployment triggered automatically
4. Watch the build logs
5. Deployment should complete in 1-2 minutes

### 6.3 Clean Up

```bash
cd /Users/michaelsena/code/darwin/darwin-ui
git checkout app/layout.tsx
git commit -m "test: Remove Vercel test change"
git push origin main
```

---

## Step 7: Test End-to-End (15 minutes)

Verify the full stack works:

### 7.1 Access Frontend

1. Open your Vercel URL: `https://darwin-<random>.vercel.app`
2. You should see the Darwin login page

### 7.2 Create Account

1. Click "Sign Up"
2. Create a test account
3. Verify you can log in

### 7.3 Create Test Run

1. Navigate to "New Run"
2. Configure a test run:
   - Symbol: BTC-USD
   - Date range: Recent dates (Dec 2025)
   - Playbook: breakout
3. Click "Launch Run"

### 7.4 Monitor Progress

1. Watch real-time progress updates
2. Verify WebSocket connection works
3. Wait for run to complete

### 7.5 View Report

1. Navigate to completed run
2. View report with charts
3. Verify all data displays correctly

**If all steps work**: ✅ Full stack deployment successful!

---

## Step 8: Optional - Custom Domain (10 minutes)

Add your own domain:

### 8.1 Add Domain

1. Go to project → "Settings" → "Domains"
2. Click "Add"
3. Enter your domain: `darwin.yourdomain.com`
4. Click "Add"

### 8.2 Configure DNS

Vercel will provide DNS records. Add these to your domain registrar:

**Option 1: CNAME (recommended)**
```
Type: CNAME
Name: darwin
Value: cname.vercel-dns.com
```

**Option 2: A Record**
```
Type: A
Name: darwin
Value: 76.76.21.21
```

### 8.3 Update Environment Variables

After domain is verified:

1. Update `NEXTAUTH_URL` to your custom domain
2. Update Railway `ALLOWED_ORIGINS` to include custom domain

### 8.4 Verify

1. Visit your custom domain
2. Verify HTTPS is working (Vercel auto-provisions SSL)
3. Test login and run creation

---

## Step 9: Configure Deployment Protection (5 minutes)

### 9.1 Enable Preview Deployments

1. Go to project → "Settings" → "Git"
2. Ensure "Preview Deployments" is enabled
3. Select branches: "All branches"

**What this does**: Every PR will get a unique preview URL for testing.

### 9.2 Environment Variables for Previews

1. Go to "Settings" → "Environment Variables"
2. For each variable, ensure it's available in:
   - ✅ Production
   - ✅ Preview
   - ⬜ Development (optional)

---

## Step 10: Monitoring & Analytics (5 minutes)

### 10.1 Enable Web Analytics (Optional)

1. Go to project → "Analytics"
2. Click "Enable Web Analytics"
3. Free tier includes:
   - Page views
   - Top pages
   - Referrers
   - Countries

### 10.2 View Deployment Logs

1. Go to project → "Deployments"
2. Click any deployment
3. View build logs and runtime logs

### 10.3 Set Up Notifications

1. Go to "Settings" → "Notifications"
2. Configure:
   - Email notifications
   - Slack integration
   - Discord integration

---

## Troubleshooting

### Build Fails

**Check build logs**:
1. Go to deployment → "Building" tab
2. Look for error messages
3. Common issues:
   - Missing dependencies in `package.json`
   - TypeScript errors
   - Environment variable not set

**Test locally**:
```bash
cd darwin-ui
npm run build
```

### Can't Connect to API

**Verify NEXT_PUBLIC_API_URL**:
1. Go to "Settings" → "Environment Variables"
2. Check the URL is correct
3. Test: `curl https://darwin-api.up.railway.app/health`

**Check CORS on Railway**:
1. Verify Railway `ALLOWED_ORIGINS` includes Vercel URL
2. Check Railway API logs for CORS errors

### Login Not Working

**Check NEXTAUTH_SECRET**:
1. Verify it's set correctly
2. Must be the same value used during initial deployment

**Check NEXTAUTH_URL**:
1. Must match your actual Vercel domain
2. Include protocol: `https://`

### WebSocket Connection Fails

**Check API URL**:
1. WebSocket connects to same URL as API
2. Verify `NEXT_PUBLIC_API_URL` is correct
3. Ensure Railway API is running

**Check browser console** for connection errors

### Preview Deployments Not Working

**Check Git settings**:
1. Go to "Settings" → "Git"
2. Verify "Preview Deployments" is enabled
3. Check branch settings

---

## Performance Optimization

### Enable ISR (Incremental Static Regeneration)

Already configured in `next.config.js` with `output: 'standalone'`.

### Enable Compression

Vercel automatically enables:
- Brotli compression
- Gzip fallback
- Image optimization

### Configure Caching

Vercel automatically caches:
- Static assets (CSS, JS, images)
- API responses (can configure in code)

---

## Cost Monitoring

### Free Tier Limits

Vercel Hobby (free) includes:
- ✅ Unlimited deployments
- ✅ 100GB bandwidth/month
- ✅ 100 GB-hours serverless execution
- ✅ 1000 image optimizations

### Upgrade to Pro ($20/month)

Consider upgrading if you need:
- More bandwidth (1TB/month)
- Password protection
- Advanced analytics
- Team collaboration

### Monitor Usage

1. Go to account → "Usage"
2. View current month metrics
3. Set up billing alerts

---

## Security Best Practices

### Environment Variables

- ✅ Never commit `.env` files
- ✅ Use strong secrets (32+ characters)
- ✅ Rotate secrets periodically
- ✅ Use different secrets for production and preview

### HTTPS

- ✅ Automatically enabled by Vercel
- ✅ Auto-renewed SSL certificates
- ✅ HTTP redirects to HTTPS

### Content Security Policy

Add to `next.config.js`:
```javascript
const nextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          }
        ]
      }
    ]
  }
}
```

---

## Next Steps

✅ Vercel frontend deployed!
✅ Railway backend deployed!
✅ Auto-deployment configured!

**Continue to Phase 4**: Database Migration

See: Full deployment plan at `~/.claude/plans/validated-wiggling-mitten.md`

---

## Useful Commands

### Local Development

```bash
cd darwin-ui
npm run dev
```

### Build for Production

```bash
cd darwin-ui
npm run build
npm run start
```

### Vercel CLI

Install:
```bash
npm i -g vercel
```

Deploy from CLI:
```bash
cd darwin-ui
vercel --prod
```

Pull environment variables:
```bash
vercel env pull
```

---

## Support

- **Vercel Docs**: https://vercel.com/docs
- **Next.js Docs**: https://nextjs.org/docs
- **Vercel Support**: https://vercel.com/support
- **GitHub Issues**: https://github.com/recallnet/darwin/issues

---

## Rollback

If deployment fails:

1. Go to project → "Deployments"
2. Find the last working deployment
3. Click three dots → "Promote to Production"
4. Vercel will instantly rollback

**Note**: Rollback is instant (no rebuild needed).
