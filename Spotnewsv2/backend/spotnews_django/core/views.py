from django.http import JsonResponse
from django.shortcuts import redirect
from django.conf import settings

def home_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    return redirect('accounts:login')

def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "spotnews-django"
    })

def health_msg91(request):
    return JsonResponse({
        "configured": bool(settings.MSG91_AUTHKEY),
        "provider": "MSG91",
        "flow_id_configured": bool(settings.MSG91_TEMPLATE_ID),
        "sender_configured": bool(settings.MSG91_SENDER_ID)
    })

import base64
import json
import time
from django.db import connection
from django.views.decorators.csrf import csrf_exempt

def check_jwt(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False, JsonResponse({"detail": "Missing Authorization header"}, status=401)
    
    token = auth_header.split(" ")[1]
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False, JsonResponse({"detail": "Invalid token format"}, status=401)
        
        payload_b64 = parts[1]
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_json = base64.b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        
        if payload.get("exp") and payload["exp"] < time.time():
            return False, JsonResponse({"detail": "Token has expired"}, status=401)
            
        return True, None
    except Exception as e:
        return False, JsonResponse({"detail": "Invalid token"}, status=401)

@csrf_exempt
def admin_stats(request):
    is_valid, error_response = check_jwt(request)
    if not is_valid:
        return error_response

    total_users = 0
    total_gens = 0
    gens_today = 0
    active_users_today = 0
    
    try:
        with connection.cursor() as cursor:
            # Total Users (Profiles as primary source for user stats)
            cursor.execute("SELECT COUNT(*) FROM profiles")
            row = cursor.fetchone()
            if row: total_users = row[0]

            # Total Generations
            cursor.execute("SELECT COUNT(*) FROM clippings")
            row = cursor.fetchone()
            if row: total_gens = row[0]

            # Generations Today
            cursor.execute("SELECT COUNT(*) FROM clippings WHERE DATE(created_at) = CURRENT_DATE")
            row = cursor.fetchone()
            if row: gens_today = row[0]
            
            # Active Users Today (unique users who created clippings today)
            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM clippings WHERE DATE(created_at) = CURRENT_DATE")
            row = cursor.fetchone()
            if row: active_users_today = row[0]
    except Exception as e:
        print(f"Error fetching stats: {e}")

    return JsonResponse({
        "totalUsers": total_users,
        "totalGenerationsAllTime": total_gens,
        "totalGenerationsToday": gens_today,
        "activeUsersToday": active_users_today,
        "totalLogos": 4,
        "debug_info": "Updated Django backend stats"
    })

@csrf_exempt
def admin_auth_users(request):
    is_valid, error_response = check_jwt(request)
    if not is_valid:
        return error_response

    users = []
    try:
        with connection.cursor() as cursor:
            # Query auth.users and join with clippings for stats
            query = """
                SELECT 
                    u.id, u.email, u.phone, p.role, u.created_at, u.raw_user_meta_data->>'full_name' as full_name, p.plan,
                    (SELECT COUNT(*) FROM clippings c WHERE c.user_id = u.id) as total_generations,
                    (SELECT COUNT(*) FROM clippings c WHERE c.user_id = u.id AND DATE(c.created_at) = CURRENT_DATE) as generations_today,
                    u.last_sign_in_at, p.is_banned, p.banned_until
                FROM auth.users u
                LEFT JOIN profiles p ON p.id = u.id
                ORDER BY u.created_at DESC NULLS LAST
                LIMIT 500
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            for r in rows:
                users.append({
                    "id": str(r[0]) if r[0] else "",
                    "email": r[1] or "",
                    "phone_number": r[2] or "",
                    "role": r[3] or "user",
                    "created_at": str(r[4]) if r[4] else "",
                    "full_name": r[5] or "",
                    "plan": r[6] or "free",
                    "total_generations": r[7] or 0,
                    "generations_today": r[8] or 0,
                    "last_sign_in_at": str(r[9]) if r[9] else "",
                    "is_banned": bool(r[10]),
                    "banned_until": str(r[11]) if r[11] else ""
                })
    except Exception as e:
        print(f"Error fetching auth.users: {e}")
        return JsonResponse({"detail": str(e)}, status=500)
    return JsonResponse(users, safe=False)
