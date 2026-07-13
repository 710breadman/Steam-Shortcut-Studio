from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.metadata import MetadataService  # noqa: E402
from steam_shortcut_studio.metadata_service_factory import (  # noqa: E402
    build_metadata_service,
    metadata_providers_for_sources,
)


class FakeSteamGridDbClient:
    def __init__(self, configured: bool) -> None:
        self.configured = configured


DEFAULT_SOURCES = {
    "executable": True,
    "steamgriddb": True,
    "steam": True,
    "pcgamingwiki": True,
    "wikipedia": True,
}


def provider_names(configured: bool, sources: dict[str, bool] | None = None) -> list[str]:
    return [
        provider.name
        for provider in metadata_providers_for_sources(
            sources or DEFAULT_SOURCES,
            FakeSteamGridDbClient(configured),  # type: ignore[arg-type]
        )
    ]


def test_metadata_providers_follow_enabled_source_order() -> None:
    assert provider_names(configured=True) == [
        "Executable metadata",
        "Steam Store",
        "SteamGridDB",
        "PCGamingWiki",
        "Wikipedia",
    ]


def test_metadata_providers_skip_unconfigured_steamgriddb() -> None:
    assert provider_names(configured=False) == [
        "Executable metadata",
        "Steam Store",
        "PCGamingWiki",
        "Wikipedia",
    ]


def test_metadata_providers_follow_disabled_sources() -> None:
    assert provider_names(
        configured=True,
        sources={
            "executable": False,
            "steamgriddb": True,
            "steam": False,
            "pcgamingwiki": False,
            "wikipedia": True,
        },
    ) == ["SteamGridDB", "Wikipedia"]


def test_build_metadata_service_returns_service_with_logger() -> None:
    logger = logging.getLogger("metadata-service-factory-test")
    service = build_metadata_service(
        {"executable": True, "steam": False, "steamgriddb": False, "pcgamingwiki": False, "wikipedia": False},
        FakeSteamGridDbClient(configured=False),  # type: ignore[arg-type]
        logger,
    )
    assert isinstance(service, MetadataService)
    assert service.logger is logger
    assert [provider.name for provider in service.providers] == ["Executable metadata"]


if __name__ == "__main__":
    test_metadata_providers_follow_enabled_source_order()
    test_metadata_providers_skip_unconfigured_steamgriddb()
    test_metadata_providers_follow_disabled_sources()
    test_build_metadata_service_returns_service_with_logger()
    print("Metadata service factory tests passed.")
