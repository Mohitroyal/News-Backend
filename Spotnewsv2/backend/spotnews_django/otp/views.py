import json
import random
import django.utils.timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password, check_password
from django.utils.timezone import now
from accounts.models import User
from .models import OTPVerification, SMSDelivery
from .services.msg91_service import MSG91Service
import logging

logger = logging.getLogger(__name__)

def normalize_mobile(mobile: str) -> str:
    mobile = ''.join(filter(str.isdigit, str(mobile)))
    if len(mobile) == 10 and mobile[0] in '6789':
        return '91' + mobile
    return mobile

@csrf_exempt
def send_otp_api(request):
    if request.method != 'POST':
        return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        mobile = data.get('mobile', '')
        normalized = normalize_mobile(mobile)
        
        if not normalized or len(normalized) != 12 or not normalized.startswith('91'):
            return JsonResponse({"success": False, "message": "Invalid mobile number"}, status=400)
        
        recent_count = OTPVerification.objects.filter(
            mobile=normalized, 
            created_at__gte=now() - django.utils.timezone.timedelta(minutes=10)
        ).count()
        if recent_count >= 3:
            return JsonResponse({"success": False, "message": "Too many requests"}, status=429)

        otp_val = str(random.randint(100000, 999999))
        otp_hash = make_password(otp_val)
        
        msg_resp = MSG91Service.send_otp(normalized, otp_val)
        
        if msg_resp.get("success"):
            OTPVerification.objects.create(
                mobile=normalized,
                otp_hash=otp_hash,
                request_id=msg_resp.get("request_id")
            )
            return JsonResponse({"success": True, "message": "OTP request accepted", "request_id": msg_resp.get("request_id")})
        else:
            return JsonResponse({"success": False, "message": "Unable to send OTP. Please try again."}, status=500)

    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}")
        return JsonResponse({"success": False, "message": "Internal error"}, status=500)

@csrf_exempt
def verify_otp_api(request):
    if request.method != 'POST':
        return JsonResponse({"success": False, "message": "Method not allowed"}, status=405)
    
    try:
        data = json.loads(request.body)
        mobile = normalize_mobile(data.get('mobile', ''))
        otp_val = data.get('otp', '')
        
        otp_record = OTPVerification.objects.filter(
            mobile=mobile, status='PENDING'
        ).order_by('-created_at').first()
        
        if not otp_record:
            return JsonResponse({"success": False, "message": "No pending OTP found"}, status=400)
            
        if now() > otp_record.expires_at:
            otp_record.status = 'EXPIRED'
            otp_record.save()
            return JsonResponse({"success": False, "message": "OTP expired"}, status=400)
            
        if otp_record.attempts >= 5:
            otp_record.status = 'FAILED'
            otp_record.save()
            return JsonResponse({"success": False, "message": "Maximum attempts exceeded"}, status=400)
            
        if check_password(otp_val, otp_record.otp_hash):
            otp_record.status = 'VERIFIED'
            otp_record.verified_at = now()
            otp_record.save()
            
            user, created = User.objects.get_or_create(mobile=mobile)
            if created:
                user.username = mobile
                user.save()
            login(request, user)
            
            return JsonResponse({
                "success": True, 
                "message": "OTP verified successfully",
                "redirect": "/dashboard/"
            })
        else:
            otp_record.attempts += 1
            otp_record.save()
            return JsonResponse({"success": False, "message": "Invalid OTP"}, status=400)
            
    except Exception as e:
        logger.error(f"Verify OTP error: {str(e)}")
        return JsonResponse({"success": False, "message": "Internal error"}, status=500)

@csrf_exempt
def resend_otp_api(request):
    return send_otp_api(request)

@csrf_exempt
def logout_api(request):
    logout(request)
    return JsonResponse({"success": True, "message": "Logged out successfully"})

def me_api(request):
    if request.user.is_authenticated:
        return JsonResponse({
            "mobile": request.user.mobile,
            "role": request.user.role,
            "name": request.user.name
        })
    return JsonResponse({"error": "Unauthorized"}, status=401)

@csrf_exempt
def msg91_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            req_id = data.get("request_id")
            if req_id:
                SMSDelivery.objects.create(
                    request_id=req_id,
                    provider_response=data,
                    status='UNKNOWN'
                )
            return JsonResponse({"success": True})
        except:
            return JsonResponse({"success": False})
    return JsonResponse({"success": False})
