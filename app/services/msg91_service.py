import re
import json
import logging
from typing import Tuple, Optional, Dict, Any
import httpx
from app.core.config import settings

logger = logging.getLogger("app.services.msg91")

MSG91_FLOW_URL = "https://control.msg91.com/api/v5/flow"
INDIAN_MOBILE_REGEX = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")


def validate_and_normalize_indian_phone(phone: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates and normalizes an Indian phone number.
    Returns:
        (is_valid, e164_format, msg91_format)
        e.g., (True, "+919876543210", "919876543210")
        or (False, None, None)
    """
    if not phone or not isinstance(phone, str):
        return False, None, None

    # Remove whitespaces, dashes, dots, parentheses
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", phone.strip())

    match = INDIAN_MOBILE_REGEX.match(cleaned)
    if not match:
        return False, None, None

    ten_digits = match.group(1)
    e164_format = f"+91{ten_digits}"
    msg91_format = f"91{ten_digits}"

    return True, e164_format, msg91_format


class MSG91Service:
    def __init__(self):
        self.authkey = settings.MSG91_AUTHKEY
        self.template_id = settings.MSG91_TEMPLATE_ID
        self.sender_id = settings.MSG91_SENDER_ID or "FOUZIA"

    def _get_authkey(self) -> Optional[str]:
        # Always fetch latest from settings or environment
        return settings.MSG91_AUTHKEY or getattr(self, "authkey", None)

    def _get_template_id(self) -> Optional[str]:
        return settings.MSG91_TEMPLATE_ID or getattr(self, "template_id", None)

    async def send_otp(self, mobile_msg91: str, otp: str) -> Tuple[bool, Optional[str], Optional[str]]:
        logger.info("[MSG91_FLOW] service entered")
        
        authkey = self._get_authkey()
        if not authkey:
            return False, "SMS service authentication is not configured.", None

        template_id = self._get_template_id()
        if not template_id:
            return False, "SMS template is not configured.", None

        headers = {
            "authkey": authkey,
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        flow_url = "https://api.msg91.com/api/v5/flow/"
        
        payload: Dict[str, Any] = {
            "flow_id": template_id,
            "sender": self.sender_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": mobile_msg91,
                    "otp": str(otp),
                    "OTP": str(otp)
                }
            ]
        }

        try:
            logger.info("[MSG91_FLOW] about to call MSG91")
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(flow_url, headers=headers, json=payload)
            logger.info("[MSG91_FLOW] MSG91 returned")

            response_status = response.status_code
            
            try:
                response_data = response.json()
            except Exception:
                response_data = {"text": response.text[:200] if response.text else ""}

            request_id = None
            if isinstance(response_data, dict):
                request_id = response_data.get("request_id") or response_data.get("message")
                res_type = str(response_data.get("type", "")).lower()

                if response_status == 200 and res_type != "error":
                    logger.info(f"[MSG91_FLOW] Request ID: {request_id}, status: {response_status}, type: {res_type}")
                    return True, None, str(request_id) if request_id else None

                error_msg = response_data.get("message") or response_data.get("msg") or "Failed"
                logger.info(f"[MSG91_FLOW] Error response: status: {response_status}, body: {json.dumps(response_data)}")
                return False, str(error_msg), str(request_id) if request_id else None

            if response_status == 200:
                logger.info(f"[MSG91_FLOW] Request ID: {request_id}, status: {response_status}")
                return True, None, None

            logger.info(f"[MSG91_FLOW] Error response: status: {response_status}, body: {json.dumps(response_data)}")
            return False, f"SMS service returned HTTP {response_status}", None

        except httpx.TimeoutException:
            return False, "SMS gateway timed out. Please try again.", None
        except Exception as e:
            return False, "Unable to deliver SMS at this time. Please try again later.", None


msg91_service = MSG91Service()
