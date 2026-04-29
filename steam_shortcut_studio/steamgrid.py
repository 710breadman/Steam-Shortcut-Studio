from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .models import ArtworkAsset

LOGGER = logging.getLogger(__name__)


class SteamGridDbError(RuntimeError):
    pass


class SteamGridDbClient:
    BASE_URL = "https://www.steamgriddb.com/api/v2"

    def __init__(self, api_key: str, cache_dir: Path, logger: logging.Logger | None = None) -> None:
        self.api_key = api_key.strip()
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.search_cache_path = self.cache_dir / "sgdb_search_cache.json"
        self.logger = logger or LOGGER
        self._search_cache = self._load_search_cache()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _load_search_cache(self) -> dict[str, Any]:
        if not self.search_cache_path.exists():
            return {}
        try:
            return json.loads(self.search_cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_search_cache(self) -> None:
        self.search_cache_path.write_text(json.dumps(self._search_cache, indent=2), encoding="utf-8")

    def _request_json(self, endpoint: str) -> dict[str, Any]:
        if not self.api_key:
            raise SteamGridDbError("SteamGridDB API key is not configured.")
        url = f"{self.BASE_URL}{endpoint}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "SteamShortcutStudio/0.1",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset, errors="replace"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise SteamGridDbError(f"SteamGridDB returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SteamGridDbError(f"Could not reach SteamGridDB: {exc.reason}") from exc
        except Exception as exc:
            raise SteamGridDbError(str(exc)) from exc

    def search_games(self, term: str, use_cache: bool = True) -> list[dict[str, Any]]:
        term = term.strip()
        if not term:
            return []
        key = term.casefold()
        cached = self._search_cache.get(key)
        if use_cache and cached and time.time() - cached.get("time", 0) < 7 * 24 * 3600:
            return list(cached.get("data", []))
        endpoint = "/search/autocomplete/" + urllib.parse.quote(term)
        data = self._request_json(endpoint)
        results = list(data.get("data", [])) if data.get("success", True) else []
        self._search_cache[key] = {"time": time.time(), "data": results}
        self._save_search_cache()
        return results

    def get_game(self, game_id: int) -> dict[str, Any]:
        data = self._request_json(f"/games/id/{int(game_id)}")
        payload = data.get("data", data)
        if isinstance(payload, list):
            return payload[0] if payload else {}
        return payload if isinstance(payload, dict) else {}

    def get_game_by_steam_appid(self, appid: int) -> dict[str, Any]:
        data = self._request_json(f"/games/steam/{int(appid)}")
        payload = data.get("data", data)
        if isinstance(payload, list):
            return payload[0] if payload else {}
        return payload if isinstance(payload, dict) else {}

    def _assets_from_payload(self, raw_assets: Any, kind: str) -> list[ArtworkAsset]:
        if not isinstance(raw_assets, list):
            return []
        assets: list[ArtworkAsset] = []
        for raw in raw_assets:
            if not isinstance(raw, dict):
                continue
            url = str(raw.get("url") or "")
            if not url:
                continue
            assets.append(
                ArtworkAsset(
                    kind=kind,
                    asset_id=str(raw.get("id") or url),
                    url=url,
                    thumb_url=str(raw.get("thumb") or raw.get("thumbnail") or ""),
                    width=int(raw.get("width") or 0),
                    height=int(raw.get("height") or 0),
                    mime=str(raw.get("mime") or ""),
                    score=int(raw.get("score") or 0),
                    style=str(raw.get("style") or ""),
                    raw=raw,
                )
            )
        assets.sort(key=lambda asset: (asset.score, asset.width * asset.height), reverse=True)
        return assets

    def get_assets(self, game_id: int, kind: str) -> list[ArtworkAsset]:
        kind = kind.lower()
        endpoint_kind = {
            "grid": "grids",
            "hero": "heroes",
            "logo": "logos",
            "icon": "icons",
        }.get(kind)
        if not endpoint_kind:
            raise ValueError(f"Unsupported artwork kind: {kind}")
        data = self._request_json(f"/{endpoint_kind}/game/{int(game_id)}")
        return self._assets_from_payload(data.get("data", []), kind)

    def get_assets_by_platform(self, platform: str, external_id: int | str, kind: str) -> list[ArtworkAsset]:
        kind = kind.lower()
        endpoint_kind = {
            "grid": "grids",
            "hero": "heroes",
            "logo": "logos",
            "icon": "icons",
        }.get(kind)
        if not endpoint_kind:
            raise ValueError(f"Unsupported artwork kind: {kind}")
        platform = platform.strip().lower()
        external = urllib.parse.quote(str(external_id).strip())
        data = self._request_json(f"/{endpoint_kind}/{platform}/{external}")
        return self._assets_from_payload(data.get("data", []), kind)
