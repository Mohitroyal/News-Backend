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
        """
        Sends OTP via MSG91 Flow API.
        
        Args:
            mobile_msg91: 91XXXXXXXXXX formatted phone number.
            otp: 6-digit plain OTP string.
            
        Returns:
            Tuple[success (bool), error_message (Optional[str]), request_id (Optional[str])]
        """
        authkey = self._get_authkey()
        if not authkey:
            logger.error("[MSG91] MSG91_AUTHKEY is not configured in environment variables.")
            return False, "SMS service authentication is not configured. Please contact support.", None

        template_id = self._get_template_id()
        if not template_id:
            logger.error("[MSG91] MSG91_TEMPLATE_ID is not configured in environment variables.")
            return False, "SMS template is not configured. Please contact support.", None

        # Headers required by MSG91 Flow API
        headers = {
            "authkey": authkey,
            "Content-Type": "application/json",
            "accept": "application/json",
        }

        # The template exists in MSG91 -> SMS -> Templates, so we MUST use the Flow API.
        flow_url = "https://api.msg91.com/api/v5/flow/"
        
        payload: Dict[str, Any] = {
            "flow_id": template_id,
            "short_url": "0",
            "recipients": [
                {
                    "mobiles": mobile_msg91,
                    "otp": str(otp),
                    "OTP": str(otp)
                }
            ]
        }

        # Mask mobile for logging (e.g. 9198****3210)
        masked_mobile = f"{mobile_msg91[:4]}****{mobile_msg91[-4:]}" if len(mobile_msg91) >= 8 else "***"

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(flow_url, headers=headers, json=payload)

            response_status = response.status_code
            logger.info(f"[MSG91] OTP request to {masked_mobile} returned HTTP {response_status}")

            try:
                response_data = response.json()
            except Exception:
                response_data = {"text": response.text[:200] if response.text else ""}

            request_id = None
            if isinstance(response_data, dict):
                request_id = response_data.get("request_id") or response_data.get("message")
                res_type = str(response_data.get("type", "")).lower()

                if response_status == 200 and res_type != "error":
                    return True, None, str(request_id) if request_id else None

                error_msg = response_data.get("message") or response_data.get("msg") or "Failed to send SMS via provider"
                logger.warning(f"[MSG91] Provider returned error: {error_msg}")
                return False, str(error_msg), str(request_id) if request_id else None

            if response_status == 200:
                return True, None, None

            return False, f"SMS service returned HTTP {response_status}", None

        except httpx.TimeoutException:
            logger.error(f"[MSG91] Request timeout while sending OTP to {masked_mobile}")
            return False, "SMS gateway timed out. Please try again.", None
        except httpx.RequestError as req_err:
            logger.error(f"[MSG91] Network error during SMS dispatch: {type(req_err).__name__}")
            return False, "SMS gateway connection failed. Please try again.", None
        except Exception as e:
            logger.error(f"[MSG91] Unexpected error during SMS dispatch: {type(e).__name__}")
            return False, "Unable to deliver SMS at this time. Please try again later.", None


msg91_service = MSG91Service()
