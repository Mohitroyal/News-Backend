# NewsCraft AI — Backend API

> **Render-ready FastAPI backend** for [NewsCraft AI](https://github.com/Mohitroyal/Newsflow-FRONTEND).

## Stack

- **FastAPI** + **Uvicorn** — Web framework
- **PostgreSQL** via **Supabase** — Database
- **Supabase Storage** — Image/PDF file storage
- **Playwright** (Chromium) — Newspaper PNG & PDF rendering
- **Groq / xAI Grok** — AI article formatting
- **Stripe** — Subscription billing
- **SQLAlchemy** + **Alembic** — ORM & migrations

## Quick Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Or follow the full guide: **[DEPLOY_RENDER.md](./DEPLOY_RENDER.md)**

## Local Development

Use the frontend repo's `backend/` folder for local development — this repo is for **production deployment only**.

## Required Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing secret (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | Supabase PostgreSQL Session mode (port 5432) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `GROK_API_KEY` | Groq (`gsk_...`) or xAI API key |
| `FRONTEND_URL` | Production frontend URL (e.g. `https://newscraft.vercel.app`) |

See [`.env.example`](./.env.example) for all optional variables.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/auth/signup` | Register |
| POST | `/api/v1/auth/login` | Login |
| GET | `/api/v1/auth/verify` | Email verification |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/generate/` | Create clipping |
| GET | `/api/v1/generate/` | List clippings |
| GET | `/api/v1/generate/{id}` | Get clipping |
| DELETE | `/api/v1/generate/{id}` | Delete clipping |
| POST | `/api/v1/uploads/image` | Upload image |
| GET | `/api/v1/subscriptions/plans` | Get plans |
| POST | `/api/v1/subscriptions/checkout` | Stripe checkout |
| POST | `/api/v1/subscriptions/webhook` | Stripe webhook |

API docs available at `/docs` after deployment.
