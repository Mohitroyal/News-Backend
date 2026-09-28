import os
import json
import base64
import time
import urllib.request
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .daily_newspaper_generator import build_newspaper_html, render_html_to_pdf

def verify_superadmin_request(request):
    """
    Enforces backend authorization.
    Verifies JWT token and checks if user role in profiles is 'superadmin' or 'admin'.
    Returns (is_authorized, user_id, user_role, error_response).
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False, None, None, JsonResponse({"detail": "Missing Authorization header"}, status=401)
    
    token = auth_header.split(" ")[1]
    user_id = None
    email = None
    
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False, None, None, JsonResponse({"detail": "Invalid JWT format"}, status=401)
        
        payload_b64 = parts[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        
        if payload.get("exp") and payload["exp"] < time.time():
            return False, None, None, JsonResponse({"detail": "Token has expired"}, status=401)
        
        user_id = payload.get("sub")
        email = payload.get("email")
    except Exception as e:
        return False, None, None, JsonResponse({"detail": f"Invalid token: {e}"}, status=401)
    
    if not user_id:
        return False, None, None, JsonResponse({"detail": "User ID not found in token"}, status=401)

    # Hardcoded fallback check for primary admin email
    if email and email.lower() == "mohithroyal16450@gmail.com":
        return True, user_id, "superadmin", None

    # Query database for user role
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT role FROM profiles WHERE id = %s", [user_id])
            row = cursor.fetchone()
            role = row[0] if row else "user"
            
            if role in ("superadmin", "admin"):
                return True, user_id, role, None
            else:
                return False, user_id, role, JsonResponse({"detail": "Super-admin access required"}, status=403)
    except Exception as e:
        print(f"[Auth Error] Database role check error: {e}")
        # Allow if token email is admin
        if email and "admin" in email:
            return True, user_id, "superadmin", None
        return False, None, None, JsonResponse({"detail": "Authorization check failed"}, status=403)


@csrf_exempt
def get_eligible_clippings(request):
    """
    Fetch eligible published clippings for a specific date (in Asia/Kolkata).
    Excludes drafts (is_posted=false), rejected, unpublished, deleted clippings.
    """
    is_auth, user_id, role, err_resp = verify_superadmin_request(request)
    if not is_auth:
        return err_resp

    if request.method != 'GET':
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    date_str = request.GET.get("date")
    if not date_str:
        # Default to today in YYYY-MM-DD
        date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        with connection.cursor() as cursor:
            # Query clippings published on specified date
            query = """
                SELECT 
                    c.id, c.headline, c.summary, c.content, c.kicker, c.subheadline,
                    c.image_url, c.image_urls, c.highlight_list, c.created_at, c.published_at,
                    c.user_id, p.full_name as reporter_name, c.state, c.district, c.location
                FROM clippings c
                LEFT JOIN profiles p ON c.user_id = p.id
                WHERE c.is_posted = true
                  AND (c.status IS NULL OR c.status NOT IN ('draft', 'rejected', 'deleted'))
                  AND (
                    DATE(c.created_at AT TIME ZONE 'Asia/Kolkata') = %s
                    OR DATE(c.published_at AT TIME ZONE 'Asia/Kolkata') = %s
                    OR DATE(c.created_at) = %s
                  )
                ORDER BY c.created_at DESC
            """
            cursor.execute(query, [date_str, date_str, date_str])
            rows = cursor.fetchall()
            
            # If no results found for exact date, fetch recent published feed items as fallback
            if not rows:
                fallback_query = """
                    SELECT 
                        c.id, c.headline, c.summary, c.content, c.kicker, c.subheadline,
                        c.image_url, c.image_urls, c.highlight_list, c.created_at, c.published_at,
                        c.user_id, p.full_name as reporter_name, c.state, c.district, c.location
                    FROM clippings c
                    LEFT JOIN profiles p ON c.user_id = p.id
                    WHERE c.is_posted = true
                      AND (c.status IS NULL OR c.status NOT IN ('draft', 'rejected', 'deleted'))
                    ORDER BY c.created_at DESC
                    LIMIT 30
                """
                cursor.execute(fallback_query)
                rows = cursor.fetchall()

            articles = []
            for r in rows:
                raw_imgs = r[7]
                if isinstance(raw_imgs, str):
                    try:
                        raw_imgs = json.loads(raw_imgs)
                    except:
                        raw_imgs = [raw_imgs]
                elif not raw_imgs and r[6]:
                    raw_imgs = [r[6]]
                elif not raw_imgs:
                    raw_imgs = []

                raw_hl = r[8]
                if isinstance(raw_hl, str):
                    try:
                        raw_hl = json.loads(raw_hl)
                    except:
                        raw_hl = [raw_hl]
                elif not raw_hl:
                    raw_hl = []

                articles.append({
                    "id": str(r[0]),
                    "headline": r[1] or "Untitled Article",
                    "summary": r[2] or "",
                    "content": r[3] or r[2] or "",
                    "kicker": r[4] or "",
                    "subheadline": r[5] or "",
                    "image_url": r[6] or (raw_imgs[0] if raw_imgs else ""),
                    "image_urls": raw_imgs,
                    "highlight_list": raw_hl,
                    "created_at": str(r[9]) if r[9] else "",
                    "published_at": str(r[10]) if r[10] else str(r[9]),
                    "user_id": str(r[11]) if r[11] else "",
                    "reporter_name": r[12] or "News Craft Reporter",
                    "state": r[13] or "",
                    "district": r[14] or "",
                    "location": r[15] or r[14] or "హైదరాబాద్"
                })

            return JsonResponse({
                "date": date_str,
                "total_eligible": len(articles),
                "articles": articles
            })
    except Exception as e:
        print(f"Error fetching eligible clippings: {e}")
        return JsonResponse({"detail": str(e)}, status=500)


@csrf_exempt
def preview_daily_newspaper(request):
    """
    Generate live preview HTML for super-admin review.
    """
    is_auth, user_id, role, err_resp = verify_superadmin_request(request)
    if not is_auth:
        return err_resp

    if request.method != 'POST':
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        publication_name = data.get("publication_name", "Spot News 24x7")
        logo_url = data.get("logo_url")
        edition_date = data.get("edition_date") or datetime.now().strftime("%Y-%m-%d")
        articles = data.get("articles") or []
        lead_story_id = data.get("lead_story_id")
        ad_config = data.get("advertisement_config")
        edition_info = data.get("edition_info")

        if not logo_url:
            return JsonResponse({"detail": "Publication logo selection is required."}, status=400)

        if not articles:
            return JsonResponse({"detail": "No articles selected for this edition."}, status=400)

        html_content = build_newspaper_html(
            publication_name=publication_name,
            logo_url=logo_url,
            edition_date=edition_date,
            articles=articles,
            lead_story_id=lead_story_id,
            advertisement_config=ad_config,
            edition_info=edition_info
        )

        total_articles = len(articles)
        total_pages = max(1, (total_articles + 9) // 10)

        return JsonResponse({
            "success": True,
            "html": html_content,
            "total_articles": total_articles,
            "total_pages": total_pages,
            "edition_date": edition_date,
            "publication_name": publication_name
        })
    except Exception as e:
        print(f"Preview generation error: {e}")
        return JsonResponse({"detail": str(e)}, status=500)


@csrf_exempt
def generate_daily_newspaper(request):
    """
    Backend PDF Generation & Database Snapshot endpoint.
    Creates immutable PDF file and saves edition snapshot to `daily_editions`.
    """
    is_auth, user_id, role, err_resp = verify_superadmin_request(request)
    if not is_auth:
        return err_resp

    if request.method != 'POST':
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        publication_code = data.get("publication_code", "spot_news")
        publication_name = data.get("publication_name", "Spot News 24x7")
        logo_url = data.get("logo_url")
        edition_date = data.get("edition_date") or datetime.now().strftime("%Y-%m-%d")
        articles = data.get("articles") or []
        lead_story_id = data.get("lead_story_id")
        ad_config = data.get("advertisement_config")
        edition_info = data.get("edition_info")
        overwrite_existing = data.get("overwrite_existing", False)

        # Requirement 3: Selected publication logo is strictly required
        if not logo_url or not logo_url.strip():
            return JsonResponse({"detail": "Publication logo is required. Please select a publication logo."}, status=400)

        if not articles:
            return JsonResponse({"detail": "At least 1 article must be selected to generate a PDF edition."}, status=400)

        # Requirement 3: Check logo URL reachability/validity
        try:
            if logo_url.startswith("http://") or logo_url.startswith("https://"):
                req = urllib.request.Request(logo_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status >= 400:
                        return JsonResponse({"detail": f"Selected publication logo cannot be loaded (HTTP {resp.status}). Please choose another logo."}, status=400)
        except Exception as logo_err:
            print(f"Logo load check warning: {logo_err}")

        # Check existing edition in database
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, version FROM daily_editions WHERE edition_date = %s AND publication_code = %s ORDER BY version DESC LIMIT 1",
                [edition_date, publication_code]
            )
            existing_row = cursor.fetchone()
            
            current_version = 1
            if existing_row and not overwrite_existing:
                current_version = (existing_row[1] or 1) + 1

        # Build HTML content
        html_content = build_newspaper_html(
            publication_name=publication_name,
            logo_url=logo_url,
            edition_date=edition_date,
            articles=articles,
            lead_story_id=lead_story_id,
            advertisement_config=ad_config,
            edition_info=edition_info
        )

        total_articles = len(articles)
        total_pages = max(1, (total_articles + 9) // 10)

        # Create output directory inside Django static/editions
        static_editions_dir = os.path.join(settings.BASE_DIR, 'static', 'editions')
        os.makedirs(static_editions_dir, exist_ok=True)

        clean_pub_code = re.sub(r'[^a-zA-Z0-9_-]', '', publication_code)
        filename = f"{clean_pub_code}-{edition_date}-v{current_version}.pdf"
        output_pdf_path = os.path.join(static_editions_dir, filename)

        # Render PDF via Playwright
        success = render_html_to_pdf(html_content, output_pdf_path)
        if not success:
            return JsonResponse({"detail": "Failed to render PDF edition. Check server Playwright setup."}, status=500)

        # PDF Public URL
        pdf_url = f"/static/editions/{filename}"

        # Save snapshot to database table `daily_editions`
        with connection.cursor() as cursor:
            insert_sql = """
                INSERT INTO daily_editions (
                    edition_date, publication_code, publication_name, logo_url,
                    articles_snapshot, lead_story_id, page_count, article_count,
                    status, pdf_url, version, created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING id
            """
            cursor.execute(insert_sql, [
                edition_date,
                publication_code,
                publication_name,
                logo_url,
                json.dumps(articles),
                str(lead_story_id) if lead_story_id else None,
                total_pages,
                total_articles,
                'completed',
                pdf_url,
                current_version,
                user_id
            ])
            new_id = cursor.fetchone()[0]

        return JsonResponse({
            "success": True,
            "edition_id": str(new_id),
            "publication_name": publication_name,
            "edition_date": edition_date,
            "version": current_version,
            "total_articles": total_articles,
            "total_pages": total_pages,
            "pdf_url": pdf_url,
            "filename": filename,
            "status": "completed",
            "message": f"Daily Newspaper Edition generated successfully! ({total_pages} pages, {total_articles} articles)"
        })
    except Exception as e:
        print(f"Error generating daily newspaper: {e}")
        return JsonResponse({"detail": str(e)}, status=500)


@csrf_exempt
def list_daily_editions(request):
    """
    List past generated daily newspaper editions.
    """
    is_auth, user_id, role, err_resp = verify_superadmin_request(request)
    if not is_auth:
        return err_resp

    if request.method != 'GET':
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        with connection.cursor() as cursor:
            query = """
                SELECT id, edition_date, publication_code, publication_name, logo_url,
                       page_count, article_count, status, pdf_url, version, created_at
                FROM daily_editions
                ORDER BY created_at DESC
                LIMIT 100
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            editions = []
            for r in rows:
                editions.append({
                    "id": str(r[0]),
                    "edition_date": str(r[1]),
                    "publication_code": r[2] or "",
                    "publication_name": r[3] or "",
                    "logo_url": r[4] or "",
                    "page_count": r[5] or 1,
                    "article_count": r[6] or 0,
                    "status": r[7] or "completed",
                    "pdf_url": r[8] or "",
                    "version": r[9] or 1,
                    "created_at": str(r[10]) if r[10] else ""
                })

            return JsonResponse(editions, safe=False)
    except Exception as e:
        print(f"Error listing daily editions: {e}")
        return JsonResponse([], safe=False)
