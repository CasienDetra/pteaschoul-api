"""Best-effort client fingerprint for login records: IP, OS, browser."""

from fastapi import Request

_OS = [("Windows", "windows"), ("Android", "android"), ("iPhone", "ios"), ("iPad", "ios"),
       ("Mac OS", "macos"), ("Macintosh", "macos"), ("Linux", "linux")]
# order matters: Edg/OPR/Chrome all carry "Chrome" in the UA string
_BROWSERS = [("Edg/", "Edge"), ("OPR/", "Opera"), ("Chrome/", "Chrome"),
             ("Firefox/", "Firefox"), ("Safari/", "Safari"), ("curl/", "curl"),
             ("python-requests", "python-requests"), ("httpx", "httpx")]
_MOBILE = ("Mobile", "Android", "iPhone", "iPad")


def _match(ua: str, table) -> str:
    return next((label for needle, label in table if needle in ua), "unknown")


def track(request: Request) -> dict[str, str]:
    ua = request.headers.get("user-agent", "")
    # X-Forwarded-For is client-controlled; only trust it behind a proxy that rewrites it.
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    # ponytail: substring sniffing, not a UA parser. It labels an audit field, nothing
    # authorises on it. Swap in `user-agents` if you ever report on these.
    return {
        "ip": ip,
        "os": _match(ua, _OS),
        "browser": _match(ua, _BROWSERS),
        "device": "mobile" if any(m in ua for m in _MOBILE) else "desktop",
        "user_agent": ua[:255],
    }
