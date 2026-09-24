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
        print("[MSG91_DIAG_1] MSG91 SERVICE ENTERED", flush=True)
        
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
        flow_url = "https://control.msg91.com/api/v5/flow/"
        
        payload: Dict[str, Any] = {
            "template_id": template_id,
            "sender": self.sender_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": mobile_msg91,
                    "otp": str(otp)
                }
            ]
        }

        try:
            print("[MSG91_DIAG_2] ABOUT TO SEND HTTP REQUEST", flush=True)
            masked_mobile = f"{mobile_msg91[:4]}XXXX{mobile_msg91[-4:]}" if len(mobile_msg91) >= 8 else "****"
            print("Diagnostics before POST:", flush=True)
            print(f"flow_url: {flow_url}", flush=True)
            print(f"flow_id: {template_id}", flush=True)
            print(f"sender: {self.sender_id}", flush=True)
            print(f"mobile number: {masked_mobile}", flush=True)
            print(f"short_url: {payload.get('short_url')}", flush=True)

            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(flow_url, headers=headers, json=payload)
            print("[MSG91_DIAG_3] MSG91 HTTP RESPONSE RECEIVED", flush=True)
            print(f"Response status: {response.status_code}", flush=True)
            print(f"Response body: {response.text}", flush=True)

            response_status = response.status_code
            
            try:
                response_data = response.json()
            except Exception:
                response_data = {"text": response.text[:200] if response.text else ""}

            if isinstance(response_data, dict):
                res_type = str(response_data.get("type", ""))
                res_msg = str(response_data.get("message") or response_data.get("msg") or "")
                req_id = str(response_data.get("request_id") or response_data.get("message") or "")
                
                print(f"[MSG91_RESULT] HTTP_STATUS: {response_status}", flush=True)
                print(f"[MSG91_RESULT] RESPONSE_TYPE: {res_type}", flush=True)
                print(f"[MSG91_RESULT] RESPONSE_MESSAGE: {res_msg}", flush=True)
                print(f"[MSG91_RESULT] REQUEST_ID: {req_id}", flush=True)
                
            request_id = None
            if isinstance(response_data, dict):
                request_id = response_data.get("request_id") or response_data.get("message")
                res_type = str(response_data.get("type", "")).lower()

                if response_status == 200 and res_type != "error":
                    return True, None, str(request_id) if request_id else None

                error_msg = response_data.get("message") or response_data.get("msg") or "Failed"
                return False, str(error_msg), str(request_id) if request_id else None

            if response_status == 200:
                return True, None, None

            return False, f"SMS service returned HTTP {response_status}", None

        except httpx.TimeoutException:
            return False, "SMS gateway timed out. Please try again.", None
        except Exception as e:
            return False, "Unable to deliver SMS at this time. Please try again later.", None


msg91_service = MSG91Service()
