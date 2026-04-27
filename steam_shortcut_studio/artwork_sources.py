from __future__ import annotations

import urllib.parse
from typing import Any

from .models import ArtworkAsset
from .steam_store import get_json

ARTWORK_SOURCE_LABELS = {
    "steam": "Official Steam",
    "steamgriddb": "SteamGridDB",
    "wikimedia": "Wikipedia/Wikimedia",
    "rawg": "RAWG",
}

DEFAULT_ARTWORK_SOURCES = {
    "steam": True,
    "steamgriddb": True,
    "wikimedia": True,
    "rawg": False,
}

ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _usable_image_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    suffix = "." + parsed.path.rsplit(".", 1)[-1].lower() if "." in parsed.path else ""
    return url.startswith("http") and suffix in ALLOWED_IMAGE_SUFFIXES


def wikimedia_artwork_assets(term: str, limit: int = 3) -> dict[str, list[ArtworkAsset]]:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": f"{term} video game",
            "gsrlimit": str(limit),
            "prop": "pageimages|info",
            "piprop": "thumbnail|original",
            "pithumbsize": "1400",
            "inprop": "url",
            "redirects": "1",
            "origin": "*",
        }
    )
    data = get_json(f"https://en.wikipedia.org/w/api.php?{query}", timeout=18)
    pages = data.get("query", {}).get("pages", {})
    if not isinstance(pages, dict):
        return {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []}
    assets_by_kind: dict[str, list[ArtworkAsset]] = {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []}
    for page_id, page in pages.items():
        if not isinstance(page, dict):
            continue
        title = str(page.get("title") or term)
        page_url = str(page.get("fullurl") or "")
        image: dict[str, Any] = {}
        if isinstance(page.get("original"), dict):
            image = page["original"]
        elif isinstance(page.get("thumbnail"), dict):
            image = page["thumbnail"]
        url = str(image.get("source") or "")
        if not _usable_image_url(url):
            continue
        width = int(image.get("width") or 0)
        height = int(image.get("height") or 0)
        raw = {"source": "Wikipedia/Wikimedia", "title": title, "page": page_url}
        score = 5200 - len(assets_by_kind["grid"])
        for kind in ("grid", "wide", "hero", "icon"):
            assets_by_kind[kind].append(
                ArtworkAsset(
                    kind=kind,
                    asset_id=f"wikimedia-{page_id}-{kind}",
                    url=url,
                    width=width,
                    height=height,
                    style="Wikipedia/Wikimedia",
                    score=score,
                    raw=raw,
                )
            )
    return assets_by_kind


def rawg_artwork_assets(term: str, api_key: str, limit: int = 3) -> dict[str, list[ArtworkAsset]]:
    api_key = api_key.strip()
    if not api_key:
        return {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []}
    query = urllib.parse.urlencode(
        {
            "key": api_key,
            "search": term,
            "page_size": str(limit),
            "search_precise": "false",
        }
    )
    data = get_json(f"https://api.rawg.io/api/games?{query}", timeout=18)
    results = data.get("results", [])
    if not isinstance(results, list):
        return {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []}
    assets_by_kind: dict[str, list[ArtworkAsset]] = {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []}
    for rank, game in enumerate(results):
        if not isinstance(game, dict):
            continue
        game_id = str(game.get("id") or rank)
        name = str(game.get("name") or term)
        background = str(game.get("background_image") or "")
        raw = {"source": "RAWG", "name": name, "rawg_id": game_id, "page": f"https://rawg.io/games/{game.get('slug')}" if game.get("slug") else ""}
        if _usable_image_url(background):
            score = 4700 - rank
            for kind in ("hero", "wide", "grid", "icon"):
                assets_by_kind[kind].append(
                    ArtworkAsset(
                        kind=kind,
                        asset_id=f"rawg-{game_id}-{kind}",
                        url=background,
                        style="RAWG",
                        score=score,
                        raw=raw,
                    )
                )
        screenshot_query = urllib.parse.urlencode({"key": api_key})
        try:
            screenshot_data = get_json(f"https://api.rawg.io/api/games/{game_id}/screenshots?{screenshot_query}", timeout=18)
        except Exception:
            continue
        screenshots = screenshot_data.get("results", [])
        if not isinstance(screenshots, list):
            continue
        for shot_index, screenshot in enumerate(screenshots[:4]):
            if not isinstance(screenshot, dict):
                continue
            url = str(screenshot.get("image") or "")
            if not _usable_image_url(url):
                continue
            assets_by_kind["hero"].append(
                ArtworkAsset(
                    kind="hero",
                    asset_id=f"rawg-{game_id}-screenshot-{shot_index}",
                    url=url,
                    width=int(screenshot.get("width") or 0),
                    height=int(screenshot.get("height") or 0),
                    style="RAWG screenshot",
                    score=4400 - rank - shot_index,
                    raw=raw,
                )
            )
    return assets_by_kind
