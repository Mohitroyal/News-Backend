import httpx
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class MSG91Service:
    API_URL = "https://api.msg91.com/api/v5/flow/"

    @classmethod
    def send_otp(cls, mobile: str, otp: str) -> dict:
        if settings.DEBUG and not settings.MSG91_AUTHKEY:
            logger.info(f"[MSG91-MOCK] Would send OTP {otp} to {mobile}")
            return {"success": True, "request_id": "mock_req_123", "message": "Mock OTP sent"}

        headers = {
            "authkey": settings.MSG91_AUTHKEY,
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        
        payload = {
            "flow_id": settings.MSG91_TEMPLATE_ID,
            "sender": settings.MSG91_SENDER_ID,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": mobile,
                    settings.MSG91_OTP_VARIABLE: otp
                }
            ]
        }
        
        masked_mobile = mobile[:4] + "******" + mobile[-2:]
        logger.info("[MSG91] REQUEST START")
        logger.info(f"[MSG91] URL: {cls.API_URL}")
        logger.info(f"[MSG91] FLOW_ID: {settings.MSG91_TEMPLATE_ID}")
        logger.info(f"[MSG91] SENDER: {settings.MSG91_SENDER_ID}")
        logger.info(f"[MSG91] MOBILE: {masked_mobile}")
        logger.info(f"[MSG91] VARIABLE_NAME: {settings.MSG91_OTP_VARIABLE}")

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(cls.API_URL, json=payload, headers=headers)
                
            resp_data = response.json()
            logger.info(f"[MSG91] RESPONSE STATUS: {response.status_code}")
            logger.info(f"[MSG91] RESPONSE TYPE: {resp_data.get('type')}")
            
            if response.status_code == 200 and resp_data.get("type") == "success":
                req_id = resp_data.get("message")
                logger.info(f"[MSG91] REQUEST ID: {req_id}")
                logger.info("[MSG91] RESPONSE BODY: sanitized success")
                return {"success": True, "request_id": req_id, "message": "OTP request accepted"}
            else:
                logger.error(f"[MSG91] Error response: {resp_data}")
                return {"success": False, "error": "MSG91 rejected request"}

        except Exception as e:
            logger.error(f"[MSG91] Exception during request: {str(e)}")
            return {"success": False, "error": "Exception calling MSG91"}
