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

import json
from django.db import connection
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def admin_stats(request):
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
    users = []
    try:
        with connection.cursor() as cursor:
            # Query profiles and join with clippings for stats
            query = """
                SELECT 
                    p.id, p.email, p.role, p.created_at, p.full_name, p.plan,
                    (SELECT COUNT(*) FROM clippings c WHERE c.user_id = p.id) as total_generations,
                    (SELECT COUNT(*) FROM clippings c WHERE c.user_id = p.id AND DATE(c.created_at) = CURRENT_DATE) as generations_today
                FROM profiles p
                ORDER BY p.created_at DESC 
                LIMIT 500
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            for r in rows:
                users.append({
                    "id": str(r[0]) if r[0] else "",
                    "email": r[1] or "",
                    "role": r[2] or "user",
                    "created_at": str(r[3]) if r[3] else "",
                    "full_name": r[4] or "",
                    "plan": r[5] or "free",
                    "total_generations": r[6] or 0,
                    "generations_today": r[7] or 0
                })
    except Exception as e:
        print(f"Error fetching profiles: {e}")
    return JsonResponse(users, safe=False)
