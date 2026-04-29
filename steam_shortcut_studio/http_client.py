from __future__ import annotations

import ssl
import urllib.request

from . import __version__

USER_AGENT = f"SteamShortcutStudio/{__version__} (personal library artwork lookup)"


def _certifi_context() -> ssl.SSLContext | None:
    try:
        import certifi  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def request_with_headers(url: str, headers: dict[str, str] | None = None) -> urllib.request.Request:
    merged = {
        "User-Agent": USER_AGENT,
    }
    if headers:
        merged.update(headers)
    return urllib.request.Request(url, headers=merged)


def open_url(request: urllib.request.Request, timeout: int):
    context = _certifi_context()
    if context is not None and request.full_url.startswith("https://"):
        return urllib.request.urlopen(request, timeout=timeout, context=context)
    return urllib.request.urlopen(request, timeout=timeout)
