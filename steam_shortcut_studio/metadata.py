from __future__ import annotations

import html
import json
import logging
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Protocol

from .exe_metadata import read_version_info
from .models import DetectedGame, GameMetadata
from .scanner import clean_display_title, is_specific_title_match, should_accept_matched_title, similarity
from .steam_store import find_steam_app, get_steam_app_details, get_json
from .steamgrid import SteamGridDbClient, SteamGridDbError

LOGGER = logging.getLogger(__name__)
USER_AGENT = "SteamShortcutStudio/0.1 (personal metadata lookup)"
GENERATED_NOTE_PREFIX = "Steam Shortcut Studio notes"


class MetadataProvider(Protocol):
    name: str

    def enrich(self, game: DetectedGame) -> GameMetadata | None:
        ...


def _year_from_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        if value > 1000000000:
            try:
                return str(datetime.utcfromtimestamp(value).year)
            except Exception:
                return ""
        if 1970 <= value <= 2100:
            return str(value)
    text = str(value)
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    return match.group(1) if match else ""


def _truncate_description(text: str, max_chars: int = 900) -> str:
    text = re.sub(r"\s+", " ", html.unescape(text or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


class LocalExecutableMetadataProvider:
    name = "Executable metadata"

    def enrich(self, game: DetectedGame) -> GameMetadata | None:
        if not game.selected_exe:
            return None
        info = read_version_info(game.selected_exe)
        title = info.get("ProductName") or info.get("FileDescription") or ""
        company = info.get("CompanyName") or ""
        if title and not should_accept_matched_title(game.title, game.metadata.clean_title, title):
            title = ""
        if not title and not company:
            return None
        extra = {key: value for key, value in info.items() if key in {"ProductName", "FileDescription", "CompanyName", "FileVersion", "ProductVersion", "LegalCopyright"} and value}
        return GameMetadata(
            clean_title=clean_display_title(title) if title else "",
            developer=company,
            source=self.name,
            extra=extra,
        )


class SteamGridDbMetadataProvider:
    name = "SteamGridDB"

    def __init__(self, client: SteamGridDbClient) -> None:
        self.client = client

    def enrich(self, game: DetectedGame) -> GameMetadata | None:
        if not self.client.configured:
            return None
        try:
            query = game.display_title if game.metadata.title_locked else game.title
            results = self.client.search_games(query)
        except SteamGridDbError:
            return None
        if not results:
            return None
        best = max(results, key=lambda item: similarity(query, str(item.get("name") or "")))
        name = str(best.get("name") or game.title)
        if not is_specific_title_match(query, name, minimum_similarity=0.52):
            return None
        game_id = int(best.get("id") or 0) or None
        detail = best
        if game_id:
            try:
                detail = {**best, **self.client.get_game(game_id)}
            except SteamGridDbError:
                detail = best
        year = _year_from_value(detail.get("release_date") or detail.get("released") or detail.get("year"))
        types = detail.get("types") or []
        genres = [str(item).replace("_", " ").title() for item in types if isinstance(item, str)]
        return GameMetadata(
            clean_title=clean_display_title(name),
            release_year=year,
            genres=genres,
            source=self.name,
            sgdb_id=game_id,
        )


class SteamStoreMetadataProvider:
    name = "Steam Store"

    def enrich(self, game: DetectedGame) -> GameMetadata | None:
        appid = game.metadata.steam_appid or game.steam_appid or 0
        name = game.display_title if game.metadata.title_locked else game.title
        if not appid:
            try:
                best = find_steam_app(name, minimum_similarity=0.58)
            except Exception:
                return None
            if not best:
                return None
            appid = int(best.get("id") or 0)
            name = str(best.get("name") or "")
        try:
            detail = get_steam_app_details(appid)
        except Exception:
            detail = {}

        if not isinstance(detail, dict):
            detail = {}
        release_date = detail.get("release_date") or {}
        release_year = ""
        if isinstance(release_date, dict):
            release_year = _year_from_value(release_date.get("date"))
        developers = detail.get("developers") or []
        publishers = detail.get("publishers") or []
        genres_raw = detail.get("genres") or []
        genres = []
        if isinstance(genres_raw, list):
            genres = [str(item.get("description") or "") for item in genres_raw if isinstance(item, dict)]
        description = str(detail.get("short_description") or "")
        categories_raw = detail.get("categories") or []
        categories = []
        if isinstance(categories_raw, list):
            categories = [str(item.get("description") or "") for item in categories_raw if isinstance(item, dict) and item.get("description")]
        platforms = detail.get("platforms") or {}
        platform_text = ""
        if isinstance(platforms, dict):
            platform_text = ", ".join(key for key, enabled in platforms.items() if enabled)
        metacritic = detail.get("metacritic") or {}
        extra: dict[str, str] = {}
        for key, value in {
            "Steam page": f"https://store.steampowered.com/app/{appid}/",
            "Website": detail.get("website") or "",
            "Support URL": (detail.get("support_info") or {}).get("url") if isinstance(detail.get("support_info"), dict) else "",
            "Metacritic": str(metacritic.get("score") or "") if isinstance(metacritic, dict) else "",
            "Recommendations": str((detail.get("recommendations") or {}).get("total") or "") if isinstance(detail.get("recommendations"), dict) else "",
            "Controller support": str(detail.get("controller_support") or ""),
            "Categories": ", ".join(categories[:10]),
            "Platforms": platform_text,
            "Required age": str(detail.get("required_age") or ""),
            "Header image": str(detail.get("header_image") or ""),
        }.items():
            if value:
                extra[key] = value
        return GameMetadata(
            clean_title=clean_display_title(str(detail.get("name") or name)),
            release_year=release_year,
            developer=", ".join(str(item) for item in developers[:3]) if isinstance(developers, list) else "",
            publisher=", ".join(str(item) for item in publishers[:3]) if isinstance(publishers, list) else "",
            genres=[genre for genre in genres if genre],
            description=_truncate_description(description),
            source=self.name,
            steam_appid=appid,
            extra=extra,
        )


class PcGamingWikiMetadataProvider:
    name = "PCGamingWiki"

    def enrich(self, game: DetectedGame) -> GameMetadata | None:
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": game.display_title if game.metadata.title_locked else game.title,
                "format": "json",
                "srlimit": "1",
            }
        )
        try:
            search_data = get_json(f"https://www.pcgamingwiki.com/w/api.php?{query}")
        except Exception:
            return None
        hits = search_data.get("query", {}).get("search", [])
        if not hits:
            return None
        title = str(hits[0].get("title") or "")
        query_title = game.display_title if game.metadata.title_locked else game.title
        if not title or not is_specific_title_match(query_title, title, minimum_similarity=0.48):
            return None
        extract_query = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "extracts",
                "exintro": "1",
                "explaintext": "1",
                "format": "json",
                "titles": title,
            }
        )
        description = ""
        try:
            extract_data = get_json(f"https://www.pcgamingwiki.com/w/api.php?{extract_query}")
            pages = extract_data.get("query", {}).get("pages", {})
            for page in pages.values():
                description = _truncate_description(str(page.get("extract") or ""))
                break
        except Exception:
            description = ""
        return GameMetadata(clean_title=clean_display_title(title), description=description, source=self.name, extra={"PCGamingWiki page": f"https://www.pcgamingwiki.com/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"})


class WikipediaMetadataProvider:
    name = "Wikipedia"

    def enrich(self, game: DetectedGame) -> GameMetadata | None:
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srsearch": f"{game.display_title if game.metadata.title_locked else game.title} video game",
                "format": "json",
                "srlimit": "3",
            }
        )
        try:
            search_data = get_json(f"https://en.wikipedia.org/w/api.php?{query}")
        except Exception:
            return None
        hits = search_data.get("query", {}).get("search", [])
        if not isinstance(hits, list) or not hits:
            return None
        query_title = game.display_title if game.metadata.title_locked else game.title
        best = max(hits, key=lambda item: similarity(query_title, str(item.get("title") or "")))
        title = str(best.get("title") or "")
        if not title or not is_specific_title_match(query_title, title, minimum_similarity=0.42):
            return None
        extract_query = urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "extracts",
                "exintro": "1",
                "explaintext": "1",
                "format": "json",
                "titles": title,
            }
        )
        description = ""
        try:
            extract_data = get_json(f"https://en.wikipedia.org/w/api.php?{extract_query}")
            pages = extract_data.get("query", {}).get("pages", {})
            for page in pages.values():
                description = _truncate_description(str(page.get("extract") or ""))
                break
        except Exception:
            description = ""
        return GameMetadata(clean_title=clean_display_title(title), description=description, source=self.name, extra={"Wikipedia page": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"})


class MetadataService:
    def __init__(self, providers: list[MetadataProvider], logger: logging.Logger | None = None) -> None:
        self.providers = providers
        self.logger = logger or LOGGER

    def enrich(self, game: DetectedGame) -> GameMetadata:
        if game.is_native_steam_game:
            self.logger.info("Metadata enrichment skipped for protected Steam game: %s", game.title)
            return game.metadata
        existing_notes = game.metadata.notes
        can_replace_notes = not existing_notes.strip() or is_generated_metadata_notes(existing_notes)
        merged = GameMetadata(
            clean_title=game.metadata.clean_title or game.title,
            title_locked=game.metadata.title_locked,
            release_year=game.metadata.release_year,
            developer=game.metadata.developer,
            publisher=game.metadata.publisher,
            genres=list(game.metadata.genres),
            description=game.metadata.description,
            source=game.metadata.source,
            sgdb_id=game.metadata.sgdb_id,
            steam_appid=game.metadata.steam_appid or game.steam_appid,
            notes=existing_notes,
            extra=dict(game.metadata.extra),
        )
        sources: list[str] = []
        if merged.source:
            sources.extend(part.strip() for part in merged.source.split(",") if part.strip())
        for provider in self.providers:
            try:
                metadata = provider.enrich(game)
            except Exception as exc:
                self.logger.warning("%s metadata failed for %s: %s", provider.name, game.title, exc)
                continue
            if not metadata:
                continue
            sources.append(metadata.source or provider.name)
            if metadata.clean_title and not merged.title_locked and should_accept_matched_title(game.title, merged.clean_title, metadata.clean_title):
                merged.clean_title = metadata.clean_title
            if metadata.release_year and not merged.release_year:
                merged.release_year = metadata.release_year
            if metadata.developer and not merged.developer:
                merged.developer = metadata.developer
            if metadata.publisher and not merged.publisher:
                merged.publisher = metadata.publisher
            for genre in metadata.genres:
                if genre and genre not in merged.genres:
                    merged.genres.append(genre)
            if metadata.description and not merged.description:
                merged.description = metadata.description
            if metadata.sgdb_id and not merged.sgdb_id:
                merged.sgdb_id = metadata.sgdb_id
            if metadata.steam_appid and not merged.steam_appid:
                merged.steam_appid = metadata.steam_appid
            for key, value in metadata.extra.items():
                if key and value and key not in merged.extra:
                    merged.extra[key] = value
            if can_replace_notes:
                merged.notes = build_metadata_notes(game, merged)
            self.logger.info(
                "%s metadata accepted for %s: title=%s year=%s developer=%s publisher=%s genres=%s description=%s",
                provider.name,
                game.title,
                bool(metadata.clean_title),
                bool(metadata.release_year),
                bool(metadata.developer),
                bool(metadata.publisher),
                len(metadata.genres),
                bool(metadata.description),
            )
        merged.source = ", ".join(dict.fromkeys(sources))
        if can_replace_notes:
            merged.notes = build_metadata_notes(game, merged)
        self.logger.info(
            "Metadata merge complete for %s: sources=%s notes_chars=%s description_chars=%s",
            game.title,
            merged.source or "(none)",
            len(merged.notes),
            len(merged.description),
        )
        game.metadata = merged
        return merged


def is_generated_metadata_notes(text: str) -> bool:
    stripped = text.strip().casefold()
    return stripped.startswith(GENERATED_NOTE_PREFIX.casefold()) or stripped.startswith("steam shortcut studio metadata")


def build_metadata_notes(game: DetectedGame, metadata: GameMetadata | None = None) -> str:
    metadata = metadata or game.metadata
    title = metadata.clean_title or game.title
    lines = [GENERATED_NOTE_PREFIX, ""]
    if title:
        lines.append(title)
        lines.append("")
    if metadata.release_year:
        lines.extend([f"Released: {metadata.release_year}", ""])
    if metadata.description:
        lines.extend(["Description", metadata.description.strip()])
    return "\n".join(line.rstrip() for line in lines).strip()
