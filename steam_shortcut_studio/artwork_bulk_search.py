from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Callable

from .artwork import download_asset
from .artwork_provider_adapter import validated_artwork_assets_to_search_outcome
from .artwork_scoring import score_artwork_set
from .bulk_artwork import ArtworkSearcher, BulkArtworkItem
from .image_validation import ArtworkFileInfo, validate_artwork_file
from .models import ArtworkAsset, DetectedGame


DEFAULT_MISSING_GAME_REASON = "Stored row is no longer available in the library view."

CollectAssets = Callable[..., Mapping[str, list[ArtworkAsset]]]


def default_search_term(item: BulkArtworkItem, game: DetectedGame) -> str:
    return game.source_title or game.title or game.display_title or item.title


def build_provider_searcher(
    *,
    game_lookup: Callable[[str], DetectedGame | None],
    collect_assets: CollectAssets,
    client: object,
    cache_dir: Path | str,
    enabled_sources: Mapping[str, bool] | None = None,
    rawg_api_key: str = "",
    provider_label: str = "real-providers",
    missing_game_reason: str = DEFAULT_MISSING_GAME_REASON,
    use_sgdb_cache: bool = True,
    allow_metadata_updates: bool = False,
    search_term: Callable[[BulkArtworkItem, DetectedGame], str] = default_search_term,
    downloader: Callable[[ArtworkAsset, Path], Path] = download_asset,
    validator: Callable[[str | Path], ArtworkFileInfo] = validate_artwork_file,
    logger: logging.Logger | None = None,
) -> ArtworkSearcher:
    """Build the `ArtworkSearcher` that `BulkArtworkCoordinator` submits with.

    This is the single real-provider searcher for bulk artwork work. Both the
    legacy UI and the modern shell use it, so provider behaviour, validation,
    and confidence handling stay in one place instead of being reimplemented
    per UI. `game_lookup` is the only part that differs between callers: each
    UI resolves a stable library ID to a `DetectedGame` its own way.

    Candidates are downloaded and decoded by
    `validated_artwork_assets_to_search_outcome` before they are ever reported
    as found, so an outcome never points at a file that failed validation.
    """
    cache_path = Path(cache_dir)
    sources = dict(enabled_sources or {})

    def searcher(item, requested_slots, token, report_progress):
        token.raise_if_cancelled()
        game = game_lookup(item.item_id)
        if game is None:
            return validated_artwork_assets_to_search_outcome(
                {},
                requested_slots,
                cache_dir=cache_path,
                provider=provider_label,
                identity_score=0,
                set_coherence_score=0,
                reasons=(missing_game_reason,),
                downloader=downloader,
                validator=validator,
                logger=logger,
            )

        report_progress(0.15, f"Searching providers for {item.title}")
        assets_by_kind = collect_assets(
            game,
            search_term(item, game),
            client,
            use_sgdb_cache=use_sgdb_cache,
            enabled_sources=sources,
            rawg_api_key=rawg_api_key,
            allow_metadata_updates=allow_metadata_updates,
            cancellation_checkpoint=token.raise_if_cancelled,
        )
        token.raise_if_cancelled()

        report_progress(0.65, f"Validating artwork candidates for {item.title}")
        return validated_artwork_assets_to_search_outcome(
            assets_by_kind,
            requested_slots,
            cache_dir=cache_path,
            provider=provider_label,
            scorer=lambda selected: score_artwork_set(
                selected,
                library_title=item.title,
                requested_slots=requested_slots,
                release_year=str(game.metadata.release_year or ""),
                steam_appid=game.steam_appid or game.metadata.steam_appid,
            ),
            downloader=downloader,
            validator=validator,
            logger=logger,
        )

    return searcher
