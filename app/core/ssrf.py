import ipaddress
import socket
import urllib.parse
import urllib.request
import io
from typing import Tuple, Optional

# Known cloud metadata hostnames
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.internal",
    "169.254.169.254",
    "instance-data",
    "localhost",
}

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/svg+xml",
    "image/gif",
}

def is_ip_literal(host: str) -> bool:
    """Check if host string is a valid IPv4 or IPv6 address literal."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def is_ip_blocked(ip_str: str) -> bool:
    """Check if an IP is private, loopback, link-local, reserved, or cloud metadata."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    return (
        ip.is_loopback or
        ip.is_private or
        ip.is_link_local or
        ip.is_reserved or
        ip.is_multicast or
        ip.is_unspecified or
        str(ip) == "169.254.169.254"
    )


def validate_url_for_ssrf(url: str) -> Tuple[bool, str]:
    """
    Strict SSRF validation (SEC-017).
    Validates URL scheme, resolves hostname to IP, and checks against private ranges.
    Returns (is_valid, reason).
    """
    if not url or not isinstance(url, str):
        return False, "URL is missing or invalid"

    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Disallowed URL scheme: '{scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing valid hostname"

    hostname_lower = hostname.lower()
    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Access to restricted host '{hostname}' is blocked."

    # Check if hostname itself is directly an IP literal
    if is_ip_literal(hostname):
        if is_ip_blocked(hostname):
            return False, f"Access to private/internal IP '{hostname}' is blocked."

    # Resolve hostname to IPv4/IPv6 addresses
    port = parsed.port or (443 if scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        return False, f"DNS resolution failed for host '{hostname}': {e}"
    except Exception as e:
        return False, f"Address lookup failed for host '{hostname}': {e}"

    if not addr_info:
        return False, f"No IP addresses resolved for host '{hostname}'."

    # Verify all resolved IPs
    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_addr = sockaddr[0]
        if is_ip_blocked(ip_addr):
            return False, f"Resolved IP '{ip_addr}' for '{hostname}' is a prohibited private/internal address."

    return True, "OK"


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Ensures HTTP redirects do not redirect to private IP spaces."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        is_safe, reason = validate_url_for_ssrf(newurl)
        if not is_safe:
            raise urllib.error.HTTPError(
                newurl, 400, f"SSRF Redirect Blocked: {reason}", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_fetch_image_bytes(
    url: str,
    max_bytes: int = 10 * 1024 * 1024,
    timeout: int = 10
) -> Tuple[bytes, str]:
    """
    Safely download an external image with SSRF protection, size caps, and timeouts.
    Returns (image_bytes, content_type).
    """
    is_safe, reason = validate_url_for_ssrf(url)
    if not is_safe:
        raise ValueError(f"SSRF Protection: {reason}")

    opener = urllib.request.build_opener(SafeRedirectHandler())
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NewsCraft-SecurityClient/2.0"}
    )

    with opener.open(req, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type and content_type not in ALLOWED_IMAGE_MIME_TYPES and not content_type.startswith("image/"):
            raise ValueError(f"Invalid content type received: '{content_type}'. Only images are allowed.")

        # Stream with maximum size cap
        chunks = []
        total_read = 0
        chunk_size = 64 * 1024

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_bytes:
                raise ValueError(f"Response size exceeded {max_bytes // (1024 * 1024)}MB limit")
            chunks.append(chunk)

        data = b"".join(chunks)
        return data, content_type
