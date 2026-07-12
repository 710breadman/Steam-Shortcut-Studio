from __future__ import annotations

import mimetypes
import urllib.error
import urllib.parse
from dataclasses import replace
from pathlib import Path

from .artwork_transactions import ArtworkWriteRequest, apply_artwork_set_transaction
from .http_client import open_url, request_with_headers
from .models import ArtworkAsset, DetectedGame, SteamProfile
from .steam_shortcuts import grid_appid, shortcut_from_game

ARTWORK_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".ico"}


def _extension_from_asset(asset: ArtworkAsset) -> str:
    parsed = urllib.parse.urlparse(asset.url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in ARTWORK_EXTENSIONS:
        return ".jpg" if suffix == ".jpeg" else suffix
    if asset.mime:
        guessed = mimetypes.guess_extension(asset.mime.split(";")[0].strip())
        if guessed:
            return ".jpg" if guessed == ".jpeg" else guessed
    return ".png"


def asset_download_cache_path(asset: ArtworkAsset, cache_dir: Path) -> Path:
    ext = _extension_from_asset(asset)
    safe_id = "".join(ch for ch in asset.asset_id if ch.isalnum() or ch in ("-", "_"))[:80] or "asset"
    return cache_dir / "artwork" / asset.kind / f"{safe_id}{ext}"


def download_asset(asset: ArtworkAsset, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = asset_download_cache_path(asset, cache_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        asset.local_path = destination
        return destination
    request = request_with_headers(
        asset.url,
        headers={
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.steamgriddb.com/",
        },
    )
    try:
        with open_url(request, timeout=45) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
            if not data:
                raise RuntimeError("Downloaded artwork was empty.")
            if "text/html" in content_type.casefold():
                raise RuntimeError(f"Artwork URL returned HTML instead of an image: {content_type}")
            destination.write_bytes(data)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:240]
        raise RuntimeError(f"Could not download artwork: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not download artwork: {exc}") from exc
    asset.local_path = destination
    return destination


def _target_name(appid: int, asset: ArtworkAsset) -> str:
    ext = _extension_from_asset(asset)
    sid = grid_appid(appid)
    if asset.kind == "grid":
        suffix = "" if asset.width and asset.height and asset.width >= asset.height else "p"
        return f"{sid}{suffix}{ext}"
    if asset.kind == "hero":
        return f"{sid}_hero{ext}"
    if asset.kind == "logo":
        return f"{sid}_logo{ext}"
    if asset.kind == "icon":
        return f"{sid}_icon{ext}"
    return f"{sid}_{asset.kind}{ext}"


def _target_names(appid: int, asset: ArtworkAsset) -> list[str]:
    ext = _extension_from_asset(asset)
    sid = grid_appid(appid)
    if asset.kind == "grid":
        return [f"{sid}p{ext}"]
    if asset.kind == "wide":
        return [f"{sid}{ext}"]
    return [_target_name(appid, asset)]


def artwork_appid_for_game(game: DetectedGame) -> int | None:
    if game.is_native_steam_game:
        return game.steam_appid
    if game.existing_appid is not None:
        return game.existing_appid
    if game.selected_exe:
        return shortcut_from_game(game).appid
    return None


def _existing_artwork_candidates(grid_dir: Path, appid: int, kind: str) -> list[Path]:
    sid = grid_appid(appid)
    patterns = {
        "grid": [f"{sid}p.*"],
        "wide": [f"{sid}.*"],
        "hero": [f"{sid}_hero.*"],
        "logo": [f"{sid}_logo.*"],
        "icon": [f"{sid}_icon.*"],
    }.get(kind, [])
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in grid_dir.glob(pattern) if path.is_file() and path.suffix.lower() in ARTWORK_EXTENSIONS)
    candidates.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return candidates


def load_existing_artwork_for_game(game: DetectedGame, profile: SteamProfile) -> int:
    appid = artwork_appid_for_game(game)
    if appid is None or not profile.grid_dir.exists():
        return 0
    loaded = 0
    for kind in game.artwork.slot_names():
        if getattr(game.artwork, kind):
            continue
        candidates = _existing_artwork_candidates(profile.grid_dir, appid, kind)
        if not candidates:
            continue
        path = candidates[0]
        setattr(
            game.artwork,
            kind,
            ArtworkAsset(
                kind=kind,
                asset_id=f"existing-{appid}-{kind}-{path.stem}",
                url=path.resolve().as_uri(),
                local_path=path,
                raw={"source": "Steam grid folder"},
            ),
        )
        loaded += 1
    return loaded


def load_existing_artwork_for_games(games: list[DetectedGame], profile: SteamProfile) -> int:
    return sum(load_existing_artwork_for_game(game, profile) for game in games)


def artwork_assets_for_steam_slots(game: DetectedGame) -> list[ArtworkAsset]:
    """Return artwork mapped to every Steam slot, with practical fallbacks.

    Steam uses the plain AppID image as the landscape/wide capsule and AppIDp as
    portrait cover art. SGDB/source coverage varies, so a good grid or hero image
    is better than leaving the slot blank.
    """
    grid = game.artwork.grid
    wide = game.artwork.wide or game.artwork.hero or game.artwork.grid
    hero = game.artwork.hero or game.artwork.wide or game.artwork.grid
    logo = game.artwork.logo
    icon = game.artwork.icon or game.artwork.grid or game.artwork.wide or game.artwork.hero
    mapped = {
        "grid": grid,
        "wide": wide,
        "hero": hero,
        "logo": logo,
        "icon": icon,
    }
    assets: list[ArtworkAsset] = []
    seen_targets: set[tuple[str, str]] = set()
    for kind, asset in mapped.items():
        if not asset or not asset.local_path or not asset.local_path.exists():
            continue
        slot_asset = asset if asset.kind == kind else replace(asset, kind=kind, asset_id=f"{asset.asset_id}-{kind}-fallback")
        key = (kind, str(slot_asset.local_path))
        if key not in seen_targets:
            assets.append(slot_asset)
            seen_targets.add(key)
    return assets


def plan_game_artwork_transaction(
    game: DetectedGame,
    profile: SteamProfile,
) -> tuple[list[ArtworkWriteRequest], list[Path]]:
    """Build the complete write/removal plan without changing Steam files."""

    appid = artwork_appid_for_game(game)
    if appid is None:
        return [], []

    writes: list[ArtworkWriteRequest] = []
    removals: list[Path] = []
    seen_removals: set[Path] = set()

    for asset in artwork_assets_for_steam_slots(game):
        source = asset.local_path.resolve(strict=True)
        for target_name in _target_names(appid, asset):
            target = (profile.grid_dir / target_name).resolve(strict=False)
            if source == target:
                continue
            writes.append(
                ArtworkWriteRequest(
                    source_path=source,
                    target_path=target,
                    slot=asset.kind,
                )
            )
            for extension in sorted(ARTWORK_EXTENSIONS):
                variant = target.with_suffix(extension).resolve(strict=False)
                if variant == target or variant == source or not variant.is_file():
                    continue
                if variant not in seen_removals:
                    seen_removals.add(variant)
                    removals.append(variant)

    return writes, removals


def copy_game_artwork_to_steam(game: DetectedGame, profile: SteamProfile) -> list[Path]:
    writes, removals = plan_game_artwork_transaction(game, profile)
    if not writes and not removals:
        return []

    outcome = apply_artwork_set_transaction(writes, remove_paths=removals)
    return [
        Path(operation.target_path)
        for operation in outcome.operations
        if operation.action == "write" and operation.status == "committed"
    ]


def copy_all_artwork_to_steam(games: list[DetectedGame], profile: SteamProfile) -> list[Path]:
    copied: list[Path] = []
    for game in games:
        if game.selected and (game.is_managed_non_steam or game.is_native_steam_game):
            copied.extend(copy_game_artwork_to_steam(game, profile))
    return copied
