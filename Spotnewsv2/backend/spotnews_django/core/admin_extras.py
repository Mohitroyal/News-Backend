import json
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def admin_generations(request):
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        offset = (page - 1) * page_size
        
        user_id = request.GET.get('user_id')
        
        query = "SELECT c.id, c.status, c.created_at, c.user_id, c.headline, c.template_id, c.language, c.tone, c.publication_name, c.publication_date, c.layout_columns, c.font_family, c.png_url, c.pdf_url, p.email, p.full_name, p.plan FROM clippings c LEFT JOIN profiles p ON c.user_id = p.id"
        count_query = "SELECT COUNT(*) FROM clippings c"
        params = []
        
        if user_id:
            query += " WHERE c.user_id = %s"
            count_query += " WHERE c.user_id = %s"
            params.append(user_id)
            
        query += " ORDER BY c.created_at DESC LIMIT %s OFFSET %s"
        params.extend([page_size, offset])
        
        with connection.cursor() as cursor:
            cursor.execute(count_query, params[:-2] if user_id else [])
            total = cursor.fetchone()[0]
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                results.append({
                    "id": str(r[0]),
                    "status": r[1] or "completed",
                    "created_at": str(r[2]) if r[2] else "",
                    "user_id": str(r[3]),
                    "headline": r[4] or "Untitled",
                    "template_id": r[5] or "default",
                    "language": r[6] or "en",
                    "tone": r[7] or "formal",
                    "publication_name": r[8] or "",
                    "publication_date": str(r[9]) if r[9] else "",
                    "layout_columns": r[10] or 3,
                    "font_family": r[11] or "playfair",
                    "image_count": 0,
                    "png_url": r[12] or "",
                    "pdf_url": r[13] or "",
                    "user_email": r[14] or "",
                    "user_name": r[15] or "",
                    "user_plan": r[16] or "free"
                })
                
        return JsonResponse({"total": total, "results": results})
    except Exception as e:
        print(f"Error fetching generations: {e}")
        return JsonResponse({"total": 0, "results": []})

@csrf_exempt
def admin_user_role(request, user_id):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            role = data.get('role', 'user')
            plan = data.get('plan', 'free')
            with connection.cursor() as cursor:
                cursor.execute("UPDATE profiles SET role = %s, plan = %s WHERE id = %s", [role, plan, user_id])
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return JsonResponse({"detail": "Method not allowed"}, status=405)

@csrf_exempt
def admin_user_plan(request, user_id):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            plan = data.get('plan', 'free')
            with connection.cursor() as cursor:
                cursor.execute("UPDATE profiles SET plan = %s WHERE id = %s", [plan, user_id])
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return JsonResponse({"detail": "Method not allowed"}, status=405)

@csrf_exempt
def admin_user_ban(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            duration = data.get('duration', '876600h')
            is_banned = duration.lower() != 'none'
            with connection.cursor() as cursor:
                cursor.execute("UPDATE profiles SET is_banned = %s WHERE id = %s", [is_banned, user_id])
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return JsonResponse({"detail": "Method not allowed"}, status=405)

@csrf_exempt
def admin_user_delete(request, user_id):
    if request.method == 'DELETE':
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM auth.users WHERE id = %s", [user_id])
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"detail": str(e)}, status=400)
    return JsonResponse({"detail": "Method not allowed"}, status=405)
