from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .models import ArtworkAsset
from .scanner import is_specific_title_match, similarity

USER_AGENT = "SteamShortcutStudio/0.1 (personal metadata and asset lookup)"


def get_json(url: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def search_steam_store(term: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"term": term, "l": "english", "cc": "US"})
    data = get_json(f"https://store.steampowered.com/api/storesearch/?{query}")
    items = data.get("items", [])
    return list(items) if isinstance(items, list) else []


def find_steam_app(term: str, minimum_similarity: float = 0.45) -> dict[str, Any] | None:
    items = search_steam_store(term)
    if not items:
        return None
    best = max(items[:8], key=lambda item: similarity(term, str(item.get("name") or "")))
    appid = int(best.get("id") or 0)
    name = str(best.get("name") or "")
    if not appid or not name or not is_specific_title_match(term, name, minimum_similarity=minimum_similarity):
        return None
    return best


def get_steam_app_details(appid: int) -> dict[str, Any]:
    query = urllib.parse.urlencode({"appids": str(int(appid)), "l": "english", "cc": "US"})
    data = get_json(f"https://store.steampowered.com/api/appdetails?{query}")
    payload = data.get(str(int(appid)), {})
    detail = payload.get("data", {}) if isinstance(payload, dict) and payload.get("success") else {}
    return detail if isinstance(detail, dict) else {}


def official_steam_assets(appid: int, app_name: str = "") -> dict[str, list[ArtworkAsset]]:
    """Return known public Steam CDN library assets.

    Steam has moved some newer assets to hashed URLs, so these are best-effort.
    The downloader skips any URL that does not exist.
    """
    appid = int(appid)
    base = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}"
    shared = f"https://shared.cloudflare.steamstatic.com/store_item_assets/steam/apps/{appid}"
    return {
        "grid": [
            ArtworkAsset(
                kind="grid",
                asset_id=f"steam-{appid}-library-600x900",
                url=f"{base}/library_600x900.jpg",
                width=600,
                height=900,
                style="official Steam",
                score=9999,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
            ArtworkAsset(
                kind="grid",
                asset_id=f"steam-{appid}-library-600x900-2x",
                url=f"{base}/library_600x900_2x.jpg",
                width=1200,
                height=1800,
                style="official Steam",
                score=9998,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
        ],
        "hero": [
            ArtworkAsset(
                kind="hero",
                asset_id=f"steam-{appid}-library-hero",
                url=f"{base}/library_hero.jpg",
                width=3840,
                height=1240,
                style="official Steam",
                score=9999,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
            ArtworkAsset(
                kind="hero",
                asset_id=f"steam-{appid}-library-header",
                url=f"{base}/library_header.jpg",
                width=920,
                height=430,
                style="official Steam",
                score=9996,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
        ],
        "wide": [
            ArtworkAsset(
                kind="wide",
                asset_id=f"steam-{appid}-library-header-wide",
                url=f"{base}/library_header.jpg",
                width=920,
                height=430,
                style="official Steam",
                score=9997,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
            ArtworkAsset(
                kind="wide",
                asset_id=f"steam-{appid}-header-wide",
                url=f"{base}/header.jpg",
                width=460,
                height=215,
                style="official Steam",
                score=9994,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
        ],
        "logo": [
            ArtworkAsset(
                kind="logo",
                asset_id=f"steam-{appid}-logo",
                url=f"{base}/logo.png",
                width=1280,
                height=720,
                style="official Steam",
                score=9999,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            )
        ],
        "icon": [
            ArtworkAsset(
                kind="icon",
                asset_id=f"steam-{appid}-header-icon",
                url=f"{shared}/header.jpg",
                width=460,
                height=215,
                style="official Steam",
                score=9995,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
            ArtworkAsset(
                kind="icon",
                asset_id=f"steam-{appid}-header",
                url=f"{base}/header.jpg",
                width=460,
                height=215,
                style="official Steam",
                score=9994,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
        ],
    }
