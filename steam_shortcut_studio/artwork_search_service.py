from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Any, Callable, Protocol

from .artwork_sources import DEFAULT_ARTWORK_SOURCES, rawg_artwork_assets, wikimedia_artwork_assets
from .models import ArtworkAsset, DetectedGame
from .scanner import clean_display_title, is_specific_title_match, should_accept_matched_title, similarity
from .steam_store import find_steam_app, get_steam_app_details, official_steam_assets, steam_store_media_assets
from .steamgrid import SteamGridDbError


ARTWORK_KINDS = ("grid", "wide", "hero", "logo", "icon")


class SteamGridArtworkClient(Protocol):
    configured: bool

    def get_assets(self, game_id: int, kind: str) -> list[ArtworkAsset]: ...

    def get_assets_by_platform(self, platform: str, external_id: int | str, kind: str) -> list[ArtworkAsset]: ...

    def get_game(self, game_id: int) -> dict[str, Any]: ...

    def get_game_by_steam_appid(self, appid: int) -> dict[str, Any]: ...

    def search_games(self, term: str, use_cache: bool = True) -> list[dict[str, Any]]: ...


def artwork_title_aliases(title: str) -> list[str]:
    cleaned = " ".join(str(title or "").replace("_", " ").split()).strip()
    if not cleaned:
        return []
    aliases: list[str] = []
    lowered = cleaned.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()

    def add(alias: str) -> None:
        alias = " ".join(alias.split()).strip()
        if alias and alias.casefold() != cleaned.casefold() and alias not in aliases:
            aliases.append(alias)

    if " - " in cleaned:
        add(cleaned.replace(" - ", ": ", 1))
    if normalized.endswith(" dc"):
        base = cleaned[: -2].strip(" -_:")
        add(f"{base} Director's Cut")
        add(f"{base} DIRECTOR'S CUT")
    if normalized.endswith(" directors cut") or normalized.endswith(" director s cut"):
        base = re.sub(r"(?i)\s+director'?s?\s+cut$", "", cleaned).strip(" -_:")
        add(f"{base} Director's Cut")
        add(f"{base} DIRECTOR'S CUT")
    subtitle_patterns = [
        (" fallen feathers", "Fallen Feathers"),
        (" legacy of thieves collection", "Legacy of Thieves Collection"),
        (" rebrushed", "Rebrushed"),
        (" mirage", "Mirage"),
    ]
    for suffix, subtitle in subtitle_patterns:
        if normalized.endswith(suffix):
            word_count = len(suffix.strip().split())
            head = " ".join(cleaned.split()[: -word_count]).strip(" -_:")
            if head:
                add(f"{head}: {subtitle}")
                if head.casefold().startswith("disney "):
                    add(f"{head[7:]}: {subtitle}")
    if cleaned.casefold().startswith("disney "):
        add(cleaned[7:])
    return aliases


def build_artwork_search_terms(game: DetectedGame, preferred: str = "") -> list[str]:
    terms: list[str] = []
    release_year = str(game.metadata.release_year or "").strip()
    title_for_exe_match = game.display_title or game.title or game.source_title
    exe_term = game.selected_exe.stem if game.selected_exe else ""
    if exe_term and title_for_exe_match and similarity(title_for_exe_match, exe_term) < 0.45:
        exe_term = ""
    raw_terms = [
        preferred,
        game.source_title,
        game.title,
        game.display_title,
        exe_term,
    ]
    if not game.source_title and game.root_path:
        raw_terms.insert(0, game.root_path.name)
    expanded: list[str] = []
    for term in raw_terms:
        cleaned = " ".join(str(term or "").replace("_", " ").split())
        if not cleaned:
            continue
        expanded.append(cleaned)
        logical = clean_display_title(cleaned)
        if logical:
            expanded.append(logical)
            if release_year:
                expanded.append(f"{logical} {release_year}")
            expanded.extend(artwork_title_aliases(logical))
        if " - " in cleaned:
            expanded.append(cleaned.replace(" - ", ": ", 1))
            expanded.append(clean_display_title(cleaned.split(" - ")[0]))
        expanded.extend(artwork_title_aliases(cleaned))
    seen: set[str] = set()
    for term in expanded:
        cleaned = " ".join(term.split())
        folded = cleaned.casefold()
        if cleaned and folded not in seen:
            terms.append(cleaned)
            seen.add(folded)
    return terms


def release_year_from_text(value: object) -> str:
    text = str(value or "")
    for index in range(max(0, len(text) - 3)):
        chunk = text[index : index + 4]
        if chunk.isdigit() and 1970 <= int(chunk) <= 2100:
            return chunk
    return ""


def artwork_candidate_score(game: DetectedGame, search_term: str, item: dict[str, Any]) -> float:
    name = str(item.get("name") or "")
    score = similarity(search_term, name)
    clean_term = clean_display_title(search_term)
    if clean_term and clean_term != search_term:
        score = max(score, similarity(clean_term, name))
    release_year = release_year_from_text(game.metadata.release_year)
    if release_year:
        candidate_year = (
            release_year_from_text(item.get("release_date"))
            or release_year_from_text(item.get("released"))
            or release_year_from_text(item.get("year"))
        )
        if candidate_year == release_year:
            score += 0.18
        elif candidate_year:
            score -= 0.08
    return score


def add_steamgriddb_assets_to_slots(
    assets_by_kind: dict[str, list[ArtworkAsset]],
    kind: str,
    fetched: list[ArtworkAsset],
) -> None:
    if kind == "grid":
        for asset in fetched:
            if asset.width and asset.height and asset.width >= asset.height:
                assets_by_kind["wide"].append(replace(asset, kind="wide", asset_id=f"{asset.asset_id}-wide"))
            else:
                assets_by_kind["grid"].append(asset)
        if not assets_by_kind["wide"]:
            assets_by_kind["wide"].extend(replace(asset, kind="wide", asset_id=f"{asset.asset_id}-wide-fallback") for asset in fetched[:3])
        if not assets_by_kind["grid"]:
            assets_by_kind["grid"].extend(fetched[:3])
    else:
        assets_by_kind[kind].extend(fetched)


class ArtworkProviderSearchService:
    def __init__(
        self,
        logger: logging.Logger | None = None,
        *,
        find_steam_app_func: Callable[[str], dict[str, Any] | None] | None = None,
        get_steam_app_details_func: Callable[[int], dict[str, Any]] = get_steam_app_details,
        official_steam_assets_func: Callable[[int, str], dict[str, list[ArtworkAsset]]] = official_steam_assets,
        steam_store_media_assets_func: Callable[[int, str, dict[str, Any]], dict[str, list[ArtworkAsset]]] = steam_store_media_assets,
        wikimedia_artwork_assets_func: Callable[[str], dict[str, list[ArtworkAsset]]] = wikimedia_artwork_assets,
        rawg_artwork_assets_func: Callable[..., dict[str, list[ArtworkAsset]]] = rawg_artwork_assets,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.find_steam_app_func = find_steam_app_func or (lambda term: find_steam_app(term, minimum_similarity=0.58))
        self.get_steam_app_details_func = get_steam_app_details_func
        self.official_steam_assets_func = official_steam_assets_func
        self.steam_store_media_assets_func = steam_store_media_assets_func
        self.wikimedia_artwork_assets_func = wikimedia_artwork_assets_func
        self.rawg_artwork_assets_func = rawg_artwork_assets_func

    def collect_assets(
        self,
        game: DetectedGame,
        term: str,
        client: SteamGridArtworkClient,
        *,
        use_sgdb_cache: bool = True,
        use_extended_sources: bool = True,
        enabled_sources: dict[str, bool] | None = None,
        rawg_api_key: str = "",
        sgdb_game_id: int | None = None,
        allow_metadata_updates: bool = True,
        cancellation_checkpoint: Callable[[], None] | None = None,
    ) -> dict[str, list[ArtworkAsset]]:
        assets_by_kind: dict[str, list[ArtworkAsset]] = {kind: [] for kind in ARTWORK_KINDS}
        sources = {**DEFAULT_ARTWORK_SOURCES, **dict(enabled_sources or {})}
        if not use_extended_sources:
            sources = {**sources, "wikimedia": False, "rawg": False}

        def checkpoint() -> None:
            if cancellation_checkpoint is not None:
                cancellation_checkpoint()

        checkpoint()
        search_terms = build_artwork_search_terms(game, term)
        if not search_terms:
            return assets_by_kind
        broad_lookup_term = next((item for item in search_terms if "launcher" not in item.casefold()), search_terms[0])
        release_year = release_year_from_text(game.metadata.release_year)
        year_lookup_term = f"{broad_lookup_term} {release_year}".strip() if release_year and release_year not in broad_lookup_term else broad_lookup_term
        steam_appid = game.steam_appid if game.is_native_steam_game and game.steam_appid else game.metadata.steam_appid

        if sources.get("steam", True) and not steam_appid:
            steam_match = self._find_steam_match(game, search_terms)
            if steam_match:
                steam_appid = int(steam_match.get("id") or 0) or None
                if allow_metadata_updates:
                    game.metadata.steam_appid = steam_appid
                steam_name = str(steam_match.get("name") or "")
                if allow_metadata_updates and not game.metadata.title_locked and should_accept_matched_title(game.title, game.metadata.clean_title, steam_name):
                    game.metadata.clean_title = steam_name

        if sources.get("steam", True) and steam_appid:
            checkpoint()
            official = self.official_steam_assets_func(int(steam_appid), game.display_title)
            self._extend_assets(assets_by_kind, official)
            try:
                steam_detail = self.get_steam_app_details_func(int(steam_appid))
            except Exception as exc:
                self.logger.info("Steam Store media lookup failed for %s: %s", game.display_title, exc)
                steam_detail = {}
            if steam_detail:
                store_media = self.steam_store_media_assets_func(int(steam_appid), game.display_title, steam_detail)
                self._extend_assets(assets_by_kind, store_media)

        sgdb_direct_found = self._collect_direct_sgdb_assets(
            game,
            client,
            assets_by_kind,
            sources,
            steam_appid,
            sgdb_game_id,
            allow_metadata_updates,
            checkpoint,
        )

        if sources.get("wikimedia", True):
            checkpoint()
            try:
                self._extend_assets(assets_by_kind, self.wikimedia_artwork_assets_func(year_lookup_term))
            except Exception as exc:
                self.logger.info("Wikipedia/Wikimedia artwork lookup failed for %s: %s", year_lookup_term, exc)

        if sources.get("rawg", False):
            checkpoint()
            try:
                self._extend_assets(
                    assets_by_kind,
                    self.rawg_artwork_assets_func(broad_lookup_term, rawg_api_key, release_year=release_year),
                )
            except Exception as exc:
                self.logger.info("RAWG artwork lookup failed for %s: %s", broad_lookup_term, exc)

        if sources.get("steamgriddb", True) and client.configured and not sgdb_direct_found:
            self._collect_search_sgdb_assets(game, client, assets_by_kind, search_terms, release_year, use_sgdb_cache, allow_metadata_updates, checkpoint)

        return self._dedupe_assets(assets_by_kind)

    def _find_steam_match(self, game: DetectedGame, search_terms: list[str]) -> dict[str, Any] | None:
        for search_term in search_terms:
            try:
                steam_match = self.find_steam_app_func(search_term)
            except Exception as exc:
                self.logger.info("Steam Store artwork lookup failed for %s: %s", search_term, exc)
                steam_match = None
            if steam_match:
                self.logger.info("Steam Store artwork match for %s using term %s.", game.display_title, search_term)
                return steam_match
        return None

    def _collect_direct_sgdb_assets(
        self,
        game: DetectedGame,
        client: SteamGridArtworkClient,
        assets_by_kind: dict[str, list[ArtworkAsset]],
        sources: dict[str, bool],
        steam_appid: int | None,
        sgdb_game_id: int | None,
        allow_metadata_updates: bool,
        checkpoint: Callable[[], None],
    ) -> bool:
        sgdb_direct_found = False
        if sources.get("steamgriddb", True) and client.configured and sgdb_game_id:
            direct_count = 0
            for kind in ("grid", "hero", "logo", "icon"):
                checkpoint()
                try:
                    fetched = client.get_assets(int(sgdb_game_id), kind)
                except SteamGridDbError as exc:
                    self.logger.info("SteamGridDB %s lookup by selected game ID %s failed: %s", kind, sgdb_game_id, exc)
                    continue
                direct_count += len(fetched)
                add_steamgriddb_assets_to_slots(assets_by_kind, kind, fetched)
            if direct_count:
                sgdb_direct_found = True
                if allow_metadata_updates:
                    game.metadata.sgdb_id = int(sgdb_game_id)
                self.logger.info("SteamGridDB artwork match for %s using selected game ID %s.", game.display_title, sgdb_game_id)

        if sources.get("steamgriddb", True) and client.configured and steam_appid and not sgdb_direct_found:
            direct_count = 0
            for kind in ("grid", "hero", "logo", "icon"):
                checkpoint()
                try:
                    fetched = client.get_assets_by_platform("steam", int(steam_appid), kind)
                except SteamGridDbError as exc:
                    self.logger.info("SteamGridDB %s lookup by Steam AppID %s failed: %s", kind, steam_appid, exc)
                    continue
                direct_count += len(fetched)
                add_steamgriddb_assets_to_slots(assets_by_kind, kind, fetched)
            if direct_count:
                sgdb_direct_found = True
                self.logger.info("SteamGridDB artwork match for %s using Steam AppID %s.", game.display_title, steam_appid)
                try:
                    detail = client.get_game_by_steam_appid(int(steam_appid))
                except SteamGridDbError:
                    detail = {}
                sgdb_id = int(detail.get("id") or 0) if isinstance(detail, dict) else 0
                if sgdb_id and allow_metadata_updates:
                    game.metadata.sgdb_id = sgdb_id
        return sgdb_direct_found

    def _collect_search_sgdb_assets(
        self,
        game: DetectedGame,
        client: SteamGridArtworkClient,
        assets_by_kind: dict[str, list[ArtworkAsset]],
        search_terms: list[str],
        release_year: str,
        use_sgdb_cache: bool,
        allow_metadata_updates: bool,
        checkpoint: Callable[[], None],
    ) -> None:
        checkpoint()
        sgdb_games: list[dict[str, Any]] = []
        matched_term = search_terms[0]
        for search_term in search_terms:
            try:
                candidates = client.search_games(search_term, use_cache=use_sgdb_cache)
            except SteamGridDbError as exc:
                self.logger.warning("SteamGridDB lookup failed for %s: %s", search_term, exc)
                continue
            if not candidates:
                continue
            detailed_candidates: list[dict[str, Any]] = []
            for candidate in candidates[:8]:
                game_id = int(candidate.get("id") or 0)
                if not game_id:
                    detailed_candidates.append(candidate)
                    continue
                try:
                    detail = client.get_game(game_id)
                except SteamGridDbError:
                    detail = {}
                detailed_candidates.append({**candidate, **detail} if isinstance(detail, dict) else candidate)
            ranked_candidates = detailed_candidates or candidates
            best_candidate = max(ranked_candidates, key=lambda item: artwork_candidate_score(game, search_term, item))
            best_candidate_name = str(best_candidate.get("name") or "")
            best_score = artwork_candidate_score(game, search_term, best_candidate)
            title_match_term = search_term.replace(release_year, "").strip() if release_year else search_term
            if best_score >= 0.52 and is_specific_title_match(title_match_term, best_candidate_name, minimum_similarity=0.52):
                sgdb_games = ranked_candidates
                matched_term = search_term
                self.logger.info("SteamGridDB artwork match for %s using term %s.", game.display_title, search_term)
                break
            self.logger.info("SteamGridDB candidate skipped for %s; best candidate was %s.", search_term, best_candidate_name or "(none)")
        if not sgdb_games:
            return
        best = max(sgdb_games, key=lambda item: artwork_candidate_score(game, matched_term, item))
        best_name = str(best.get("name") or "")
        title_match_term = matched_term.replace(release_year, "").strip() if release_year else matched_term
        if artwork_candidate_score(game, matched_term, best) < 0.52 or not is_specific_title_match(title_match_term, best_name, minimum_similarity=0.52):
            self.logger.info("SteamGridDB match skipped for %s; best candidate was %s.", matched_term, best_name or "(none)")
            best = {}
        game_id = int(best.get("id") or 0)
        if not game_id:
            return
        if allow_metadata_updates:
            game.metadata.sgdb_id = game.metadata.sgdb_id or game_id
        if allow_metadata_updates and not game.metadata.title_locked and should_accept_matched_title(game.title, game.metadata.clean_title, best_name):
            game.metadata.clean_title = best_name
        for kind in ("grid", "hero", "logo", "icon"):
            checkpoint()
            try:
                fetched = client.get_assets(game_id, kind)
            except SteamGridDbError as exc:
                self.logger.warning("SteamGridDB %s lookup failed for %s: %s", kind, matched_term, exc)
                continue
            add_steamgriddb_assets_to_slots(assets_by_kind, kind, fetched)

    @staticmethod
    def _extend_assets(
        assets_by_kind: dict[str, list[ArtworkAsset]],
        incoming: dict[str, list[ArtworkAsset]],
    ) -> None:
        for kind, assets in incoming.items():
            if kind in assets_by_kind:
                assets_by_kind[kind].extend(assets)

    @staticmethod
    def _dedupe_assets(
        assets_by_kind: dict[str, list[ArtworkAsset]],
    ) -> dict[str, list[ArtworkAsset]]:
        for kind, assets in assets_by_kind.items():
            seen: set[str] = set()
            deduped: list[ArtworkAsset] = []
            for asset in assets:
                dedupe_key = f"{asset.kind}:{asset.url}"
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                deduped.append(asset)
            assets_by_kind[kind] = deduped
        return assets_by_kind
