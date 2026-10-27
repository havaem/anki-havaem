"""Tiny HTTP helper: browser-like headers, retries with backoff, clear errors."""

import time
import urllib.error
import urllib.request
from typing import NamedTuple, Optional

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
RETRY_STATUSES = (429, 500, 502, 503, 504)


class HttpError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, body: bytes = b""):
        super().__init__(message)
        self.status = status
        self.body = body


class Response(NamedTuple):
    body: bytes
    url: str  # final URL, after redirects
    content_type: str


def _retry_after(err: urllib.error.HTTPError) -> Optional[float]:
    try:
        return min(float(err.headers.get("Retry-After", "")), 30.0)
    except (TypeError, ValueError):
        return None


def fetch(
    url: str,
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
    timeout: float = 20,
    retries: int = 2,
) -> Response:
    hdrs = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    hdrs.update(headers or {})

    attempt = 0
    while True:
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return Response(resp.read(), resp.geturl(), resp.headers.get_content_type())
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUSES and attempt < retries:
                time.sleep(_retry_after(e) or 1.5 * (2**attempt))
                attempt += 1
                continue
            raise HttpError(f"HTTP {e.code}", e.code, e.read()[:2000]) from e
        except (urllib.error.URLError, OSError) as e:
            if attempt < retries:
                time.sleep(1.5 * (2**attempt))
                attempt += 1
                continue
            reason = getattr(e, "reason", e)
            raise HttpError(f"Network error: {reason}") from e
