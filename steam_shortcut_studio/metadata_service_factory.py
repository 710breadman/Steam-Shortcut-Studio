from __future__ import annotations

import logging
from collections.abc import Mapping

from .metadata import (
    LocalExecutableMetadataProvider,
    MetadataProvider,
    MetadataService,
    PcGamingWikiMetadataProvider,
    SteamGridDbMetadataProvider,
    SteamStoreMetadataProvider,
    WikipediaMetadataProvider,
)
from .steamgrid import SteamGridDbClient


def metadata_providers_for_sources(
    sources: Mapping[str, bool],
    client: SteamGridDbClient,
) -> list[MetadataProvider]:
    providers: list[MetadataProvider] = []
    if sources.get("executable", True):
        providers.append(LocalExecutableMetadataProvider())
    if sources.get("steam", True):
        providers.append(SteamStoreMetadataProvider())
    if client.configured and sources.get("steamgriddb", True):
        providers.append(SteamGridDbMetadataProvider(client))
    if sources.get("pcgamingwiki", True):
        providers.append(PcGamingWikiMetadataProvider())
    if sources.get("wikipedia", True):
        providers.append(WikipediaMetadataProvider())
    return providers


def build_metadata_service(
    sources: Mapping[str, bool],
    client: SteamGridDbClient,
    logger: logging.Logger | None = None,
) -> MetadataService:
    return MetadataService(metadata_providers_for_sources(sources, client), logger)
