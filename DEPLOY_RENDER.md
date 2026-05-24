# NewsCraft AI — Render Deployment Guide

> **This folder (`production_backend/`) is a self-contained Render-ready version.**  
> The original `backend/` folder is untouched and continues to work for local development.

---

## What Changed vs Localhost Backend

| Area | Localhost (`backend/`) | Production (`production_backend/`) |
|---|---|---|
| Config source | `.env` file | Render environment variables |
| API base URL | `localhost:8000` | `$PORT` (Render injects) |
| Logo URLs | `localhost:8001/static/...` | `$RENDER_EXTERNAL_URL/static/...` |
| Upload fallback URL | `localhost:7860/static/...` | `$RENDER_EXTERNAL_URL/static/...` |
| Image upload target | Local filesystem | Supabase Storage (primary) |
| Chromium flags | Default | `--no-sandbox` (required on Render) |
| Auth email redirect | `localhost:3000` | `$FRONTEND_URL` |
| Custom layout render | `localhost:3000/render/...` | `$FRONTEND_URL/render/...` |
| CORS | Hardcoded `localhost` | `$CORS_ORIGINS` + `$FRONTEND_URL` |
| Health check | None | `GET /health` → `{"status":"ok"}` |

---

## Step 1 — Push `production_backend` to GitHub

```bash
# Option A: As a sub-folder in the same repo (recommended)
git add production_backend/
git commit -m "feat: add production_backend for Render deployment"
git push

# Option B: As a separate repository
cd production_backend
git init
git add .
git commit -m "Initial production backend"
git remote add origin https://github.com/YOUR_USERNAME/newsflow-backend.git
git push -u origin main
```

---

## Step 2 — Create a Render Web Service

1. Go to [https://render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. If using Option A (sub-folder), set **Root Directory** to `production_backend`
4. Render will auto-detect `render.yaml` — click **Apply**

Or configure manually:

| Setting | Value |
|---|---|
| **Environment** | Python |
| **Build Command** | `pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/health` |

---

## Step 3 — Set Environment Variables in Render Dashboard

Go to your service → **Environment** tab → add each variable:

### Required Variables

| Variable | Where to Find It |
|---|---|
| `SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Supabase → Project Settings → Database → **Session mode** connection string (port **5432**) |
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API → service_role key |
| `GROK_API_KEY` | Groq console: [console.groq.com](https://console.groq.com) or xAI API key |
| `FRONTEND_URL` | Your Vercel/Netlify frontend URL, e.g. `https://newsflow.vercel.app` |

### Optional Variables

| Variable | Value |
|---|---|
| `STRIPE_API_KEY` | Stripe Dashboard → API Keys |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Webhooks |
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your-email@gmail.com |
| `SMTP_PASSWORD` | Gmail App Password |
| `EMAILS_FROM_EMAIL` | noreply@newscraft.ai |

> **Important:** For `DATABASE_URL`, use the **Session mode** connection string from Supabase  
> (port 5432, not 6543). This avoids pgBouncer transaction-mode issues with SQLAlchemy.

---

## Step 4 — Supabase Storage Setup

1. In Supabase dashboard → **Storage** → **New Bucket**
2. Name: `newscraft-clippings`
3. Set bucket to **Public** (so PNG/PDF URLs are accessible without auth)
4. Set the `SUPABASE_STORAGE_BUCKET` env var to `newscraft-clippings`

---

## Step 5 — Run Database Migrations on Render

After your first deploy, run the migration in Render's **Shell** tab:

```bash
# In Render Shell:
alembic upgrade head
```

Or add it to the build command:
```
pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium && alembic upgrade head
```

---

## Step 6 — Update Frontend to Point to Production Backend

In your frontend project, update the API base URL:

**For Next.js (`.env.production` or Vercel env vars):**
```env
NEXT_PUBLIC_API_URL=https://newsflow-backend.onrender.com/api/v1
```

Then update `src/lib/axios.ts`:
```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
```

---

## Step 7 — Stripe Webhook (Production)

1. Stripe Dashboard → Developers → Webhooks → **Add endpoint**
2. Endpoint URL: `https://newsflow-backend.onrender.com/api/v1/subscriptions/webhook`
3. Events to listen to:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.deleted`
4. Copy the **Signing secret** → set as `STRIPE_WEBHOOK_SECRET` env var on Render

---

## Verification Checklist

After deploying, verify each endpoint:

```bash
# Replace with your actual Render URL
BASE=https://newsflow-backend.onrender.com

# 1. Health check
curl $BASE/health
# Expected: {"status":"ok","service":"NewsCraft AI"}

# 2. API root
curl $BASE/
# Expected: {"message":"Welcome to NewsCraft AI API",...}

# 3. API docs (open in browser)
open $BASE/docs

# 4. Auth signup
curl -X POST $BASE/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","full_name":"Test User"}'

# 5. Image upload
curl -X POST $BASE/api/v1/uploads/image \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@/path/to/image.jpg"
```

---

## Troubleshooting

### "Application failed to start"
- Check the Render build logs for missing packages
- Ensure all required env vars are set (SECRET_KEY, DATABASE_URL, SUPABASE_URL, etc.)

### "playwright: chromium not found"
- The build command must include: `playwright install chromium && playwright install-deps chromium`
- This is already in `render.yaml`

### "psycopg2 connection error"
- Verify `DATABASE_URL` uses **port 5432** (Session mode), not 6543 (Transaction mode)
- Check Supabase → Project Settings → Database → "Connection string" → select "Session"

### "CORS error" from frontend
- Set `FRONTEND_URL` env var to your exact frontend URL (no trailing slash)
- Example: `https://newscraft.vercel.app` ✅ — NOT `https://newscraft.vercel.app/` ❌

### "401 Unauthorized"
- Ensure `SECRET_KEY` and `SUPABASE_SERVICE_ROLE_KEY` are correctly set
- Check the token is being sent as `Authorization: Bearer <token>` header

### Render free tier spinning down
- Free tier services spin down after 15 mins of inactivity (cold start ~30s)
- Upgrade to **Starter** plan ($7/month) for always-on service
- Or use [cron-job.org](https://cron-job.org) to ping `/health` every 10 mins

---

## Local Test of Production Build

```powershell
# In production_backend/ directory — test it locally before pushing to Render
cd production_backend

# Create a .env file from the example (fill in real values)
Copy-Item .env.example .env
# Edit .env with real production values

# Install deps
pip install -r requirements.txt
playwright install chromium

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test
Invoke-WebRequest http://localhost:8000/health
```

---

## File Structure

```
production_backend/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── auth.py          ← FRONTEND_URL for email redirects
│   │   ├── generate.py      ← FRONTEND_URL for custom layout URLs
│   │   ├── upload.py        ← Supabase Storage upload (production-first)
│   │   └── subscriptions.py
│   ├── core/
│   │   └── config.py        ← Reads from env vars, no .env file
│   ├── services/
│   │   ├── render_service.py ← --no-sandbox Chromium flags for Render
│   │   └── storage_service.py ← RENDER_EXTERNAL_URL for fallback URLs
│   └── main.py              ← /health endpoint, $PORT support
├── .env.example             ← Template — NEVER commit filled-in .env
├── .gitignore
├── Procfile                 ← web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
├── render.yaml              ← Full Render service definition
├── requirements.txt         ← Cleaned production deps (no Celery/Redis/pytest)
└── runtime.txt              ← python-3.11.9
```
