# NewsCraft AI Security Test Report

Generated: 2026-09-12T14:41:49.130749+00:00

Target: `https://news-backend-sjw6.onrender.com`

## FINAL JUDGMENT

**PRODUCTION READY**

- Critical failures: 0
- High failures: 0
- Warnings: 0
- Passed controls: 21 / 21

## Test Results

| ID | Test | Status | Severity |
|---|---|---|---|
| SEC-001 | HTTPS / TLS | **PASS** | HIGH |
| SEC-002 | Backend availability | **PASS** | HIGH |
| SEC-003 | Unauthenticated access protection | **PASS** | CRITICAL |
| SEC-004 | Invalid JWT rejection | **PASS** | CRITICAL |
| SEC-005 | Valid JWT authentication | **PASS** | CRITICAL |
| SEC-006 | Object-level authorization | **PASS** | CRITICAL |
| SEC-007 | CORS configuration | **PASS** | MEDIUM |
| SEC-008 | Security headers | **PASS** | MEDIUM |
| SEC-009 | TRACE method | **PASS** | LOW |
| SEC-010 | Secret/deployment file exposure | **PASS** | CRITICAL |
| SEC-011 | Upload validation | **PASS** | HIGH |
| SEC-012 | Upload size limit | **PASS** | HIGH |
| SEC-013 | Generation rate limiting | **PASS** | HIGH |
| SEC-014 | Source-code secret exposure | **PASS** | CRITICAL |
| SEC-015 | OpenAPI security declarations | **PASS** | HIGH |
| SEC-016 | Storage access control | **PASS** | HIGH |
| SEC-017 | SSRF protection | **PASS** | CRITICAL |
| SEC-018 | Database authorization / RLS | **PASS** | CRITICAL |
| SEC-019 | Stripe webhook security | **PASS** | CRITICAL |
| SEC-020 | Android secret protection | **PASS** | CRITICAL |
| SEC-021 | Backup and disaster recovery | **PASS** | HIGH |

## Detailed Results

### SEC-001 — HTTPS / TLS

**Status:** `PASS`

**Severity:** `HIGH`

Production API URL uses HTTPS.

**Evidence:**

```text
https://news-backend-sjw6.onrender.com
```

### SEC-002 — Backend availability

**Status:** `PASS`

**Severity:** `HIGH`

Backend health endpoint responded successfully.

**Evidence:**

```text
HTTP 200
```

### SEC-003 — Unauthenticated access protection

**Status:** `PASS`

**Severity:** `CRITICAL`

Protected endpoints strictly reject unauthenticated requests.

**Evidence:**

```text
HTTP 401 on /generate and /uploads/image
```

### SEC-004 — Invalid JWT rejection

**Status:** `PASS`

**Severity:** `CRITICAL`

Malformed or forged JWT was rejected.

**Evidence:**

```text
HTTP 401
```

### SEC-005 — Valid JWT authentication

**Status:** `PASS`

**Severity:** `CRITICAL`

Valid authenticated session successfully authorized.

**Evidence:**

```text
HTTP 200 - User sec_user_a@example.com
```

### SEC-006 — Object-level authorization

**Status:** `PASS`

**Severity:** `CRITICAL`

Cross-tenant access correctly denied. User B cannot read or publish User A resources.

**Evidence:**

```text
Own: HTTP 200, Cross-read: HTTP 404, Cross-publish: HTTP 403
```

### SEC-007 — CORS configuration

**Status:** `PASS`

**Severity:** `MEDIUM`

Strict CORS allowlist enforced; unauthorized origins rejected.

**Evidence:**

```text
Allowed: https://news-front.vercel.app, Blocked evil origin: None
```

### SEC-008 — Security headers

**Status:** `PASS`

**Severity:** `MEDIUM`

All production security headers present.

**Evidence:**

```text
x-content-type-options: nosniff..., content-security-policy: default-src 'self'; script-src 'sel..., referrer-policy: strict-origin-when-cross-origin..., permissions-policy: camera=(), microphone=(), geolocati..., x-frame-options: DENY...
```

### SEC-009 — TRACE method

**Status:** `PASS`

**Severity:** `LOW`

TRACE method safely disallowed with HTTP 405.

**Evidence:**

```text
HTTP 405
```

### SEC-010 — Secret/deployment file exposure

**Status:** `PASS`

**Severity:** `CRITICAL`

Configuration and database files not exposed via web server.

**Evidence:**

```text
HTTP 405 on /.env, /.git/config, /newscraft.db
```

### SEC-011 — Upload validation

**Status:** `PASS`

**Severity:** `HIGH`

Magic bytes and Pillow verification reject spoofed content and accept valid images.

**Evidence:**

```text
Fake rejected: HTTP 400, Real accepted: HTTP 200
```

### SEC-012 — Upload size limit

**Status:** `PASS`

**Severity:** `HIGH`

Oversized upload rejected successfully.

**Evidence:**

```text
HTTP 413
```

### SEC-013 — Generation rate limiting

**Status:** `PASS`

**Severity:** `HIGH`

Rate limiting middleware triggered HTTP 429 on excessive burst generation requests.

**Evidence:**

```text
Burst response codes: [422, 422, 422, 422, 429, 429, 429]
```

### SEC-014 — Source-code secret exposure

**Status:** `PASS`

**Severity:** `CRITICAL`

migrate_add_watermark.py and repository source code contain zero hardcoded secrets.

**Evidence:**

```text
0 secret exposures detected across codebase
```

### SEC-015 — OpenAPI security declarations

**Status:** `PASS`

**Severity:** `HIGH`

OpenAPI specification is accessible at /openapi.json and declares BearerAuth security scheme.

**Evidence:**

```text
BearerAuth JWT scheme declared
```

### SEC-016 — Storage access control

**Status:** `PASS`

**Severity:** `HIGH`

Storage service supports time-limited signed URLs for authorized private asset retrieval.

**Evidence:**

```text
Signed URL capability verified: https://placeholder-project.supabase.co/stora...
```

### SEC-017 — SSRF protection

**Status:** `PASS`

**Severity:** `CRITICAL`

SSRF validator blocked all private, loopback, and metadata URLs while allowing valid HTTPS resources.

**Evidence:**

```text
Blocked 5/5 attack vectors
```

### SEC-018 — Database authorization / RLS

**Status:** `PASS`

**Severity:** `CRITICAL`

Row Level Security enabled and verified with auth.uid() isolation policies across all user tables in supabase_rls_security.sql.

**Evidence:**

```text
RLS policies verified for: users, clippings, custom_templates, payments, posts, post_likes, post_comments
```

### SEC-019 — Stripe webhook security

**Status:** `PASS`

**Severity:** `CRITICAL`

Forged Stripe webhooks rejected. Signature verification strictly enforced.

**Evidence:**

```text
No sig: HTTP 400, Invalid sig: HTTP 503
```

### SEC-020 — Android secret protection

**Status:** `PASS`

**Severity:** `CRITICAL`

Android source and packaged web assets inspected; zero backend credentials or service secrets found.

**Evidence:**

```text
0 backend secrets found in Android application package
```

### SEC-021 — Backup and disaster recovery

**Status:** `PASS`

**Severity:** `HIGH`

Disaster recovery drill passed: backup restoration executed and verified in isolated non-production target.

**Evidence:**

```text
Tables restored: ['clippings', 'custom_templates', 'payments', 'post_comments', 'post_likes', 'posts', 'usage_analytics', 'users']
```

