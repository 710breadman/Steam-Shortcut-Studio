from __future__ import annotations

import json
import urllib.parse
from typing import Any

from .http_client import open_url, request_with_headers
from .models import ArtworkAsset
from .scanner import is_specific_title_match, similarity


def canonical_steam_app_for_title(term: str) -> dict[str, Any] | None:
    normalized = " ".join(str(term or "").casefold().replace("_", " ").replace("-", " ").split())
    compact = "".join(ch for ch in normalized if ch.isalnum())
    tokens = set(normalized.replace("'", " ").split())
    if {"ghost", "tsushima"}.issubset(tokens) or "ghostoftsushima" in compact:
        return {"id": 2215430, "name": "Ghost of Tsushima DIRECTOR'S CUT"}
    return None


def get_json(url: str, timeout: int = 15) -> dict[str, Any]:
    request = request_with_headers(url, headers={"Accept": "application/json"})
    with open_url(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def search_steam_store(term: str) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"term": term, "l": "english", "cc": "US"})
    data = get_json(f"https://store.steampowered.com/api/storesearch/?{query}")
    items = data.get("items", [])
    return list(items) if isinstance(items, list) else []


def find_steam_app(term: str, minimum_similarity: float = 0.45) -> dict[str, Any] | None:
    canonical = canonical_steam_app_for_title(term)
    if canonical:
        return canonical
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


def steam_store_media_assets(appid: int, app_name: str, detail: dict[str, Any]) -> dict[str, list[ArtworkAsset]]:
    appid = int(appid)
    assets_by_kind: dict[str, list[ArtworkAsset]] = {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []}

    def add(kind: str, key: str, url: str, width: int, height: int, score: int) -> None:
        url = str(url or "")
        if not url.startswith(("http://", "https://")):
            return
        assets_by_kind[kind].append(
            ArtworkAsset(
                kind=kind,
                asset_id=f"steam-store-{appid}-{key}-{kind}",
                url=url,
                width=width,
                height=height,
                style="Steam Store media",
                score=score,
                raw={"source": "Steam Store", "appid": appid, "name": app_name},
            )
        )

    header = str(detail.get("header_image") or "")
    capsule = str(detail.get("capsule_image") or "")
    capsule_v5 = str(detail.get("capsule_imagev5") or "")
    background = str(detail.get("background_raw") or detail.get("background") or "")
    add("wide", "header", header, 460, 215, 9300)
    add("icon", "header", header, 460, 215, 9200)
    add("wide", "capsule", capsule, 616, 353, 9100)
    add("icon", "capsule", capsule_v5 or capsule, 184, 69, 9000)
    add("hero", "background", background, 1920, 620, 9050)
    screenshots = detail.get("screenshots") or []
    if isinstance(screenshots, list):
        for index, screenshot in enumerate(screenshots[:4]):
            if not isinstance(screenshot, dict):
                continue
            full = str(screenshot.get("path_full") or "")
            thumb = str(screenshot.get("path_thumbnail") or "")
            add("hero", f"screenshot-{index}", full, 1920, 1080, 8800 - index)
            add("wide", f"screenshot-{index}", thumb or full, 600, 338, 8700 - index)
    return assets_by_kind


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
            ArtworkAsset(
                kind="grid",
                asset_id=f"steam-{appid}-shared-library-600x900",
                url=f"{shared}/library_600x900.jpg",
                width=600,
                height=900,
                style="official Steam",
                score=9997,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
            ArtworkAsset(
                kind="grid",
                asset_id=f"steam-{appid}-shared-capsule-616x353-grid-fallback",
                url=f"{shared}/capsule_616x353.jpg",
                width=616,
                height=353,
                style="Steam Store media",
                score=9100,
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
            ArtworkAsset(
                kind="hero",
                asset_id=f"steam-{appid}-shared-header-hero",
                url=f"{shared}/header.jpg",
                width=460,
                height=215,
                style="Steam Store media",
                score=9200,
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
            ArtworkAsset(
                kind="wide",
                asset_id=f"steam-{appid}-shared-capsule-616x353",
                url=f"{shared}/capsule_616x353.jpg",
                width=616,
                height=353,
                style="Steam Store media",
                score=9300,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
            ArtworkAsset(
                kind="wide",
                asset_id=f"steam-{appid}-shared-header-wide",
                url=f"{shared}/header.jpg",
                width=460,
                height=215,
                style="Steam Store media",
                score=9200,
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
            ArtworkAsset(
                kind="icon",
                asset_id=f"steam-{appid}-shared-capsule-184x69",
                url=f"{shared}/capsule_184x69.jpg",
                width=184,
                height=69,
                style="Steam Store media",
                score=9993,
                raw={"source": "Steam", "appid": appid, "name": app_name},
            ),
        ],
    }
