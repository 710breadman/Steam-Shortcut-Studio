from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_bulk_search import build_provider_searcher  # noqa: E402
from steam_shortcut_studio.artwork_policy import ArtworkMatchPolicy  # noqa: E402
from steam_shortcut_studio.artwork_scoring import MATCH_PROVENANCE_KEY, MatchMethod  # noqa: E402
from steam_shortcut_studio.bulk_artwork import BulkArtworkItem  # noqa: E402
from steam_shortcut_studio.jobs import CancellationToken, JobCancelledError  # noqa: E402
from steam_shortcut_studio.models import ArtworkAsset, DetectedGame, GameMetadata  # noqa: E402


def _game(title: str = "Example Game") -> DetectedGame:
    return DetectedGame(
        title=title,
        root_path=Path(r"C:\Games\Example"),
        source_title=title,
        metadata=GameMetadata(clean_title=title),
    )


def _asset(slot: str, *, name: str = "", provider: str = "SteamGridDB") -> ArtworkAsset:
    provenance = {"provider": provider, "method": str(MatchMethod.TITLE_SEARCH)}
    if name:
        provenance["name"] = name
    return ArtworkAsset(
        kind=slot,
        asset_id=f"{slot}-1",
        url=f"https://example.invalid/{slot}.png",
        raw={"source": provider, MATCH_PROVENANCE_KEY: provenance},
    )


def _progress(_fraction: float, _message: str | None = None) -> None:
    return None


def test_missing_game_reports_zero_scores_and_the_caller_supplied_reason() -> None:
    searcher = build_provider_searcher(
        game_lookup=lambda item_id: None,
        collect_assets=lambda *args, **kwargs: {},
        client=object(),
        cache_dir=Path("cache"),
        missing_game_reason="Row vanished.",
    )

    outcome = searcher(
        BulkArtworkItem("game-1", "Example"), ("grid",), CancellationToken(), _progress
    )

    assert outcome.found_slots == frozenset()
    assert outcome.evidence.identity_score == 0
    assert outcome.evidence.set_coherence_score == 0
    assert outcome.evidence.reasons == ("Row vanished.",)


def _searcher(cache: Path, downloaded: Path, collect_assets, **kwargs):
    return build_provider_searcher(
        game_lookup=lambda item_id: kwargs.pop("game", None) or _game(),
        collect_assets=collect_assets,
        client=object(),
        cache_dir=cache,
        enabled_sources={"steamgriddb": True},
        downloader=lambda asset, directory: downloaded,
        validator=lambda path: _FakeInfo(Path(path)),
        **kwargs,
    )


def test_validated_candidates_are_scored_from_real_provider_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        downloaded = cache / "grid-1.png"
        downloaded.write_bytes(b"not-really-an-image")
        calls: list[tuple[str, str]] = []

        def collect_assets(game, term, client, **kwargs):
            calls.append((game.title, term))
            assert kwargs["allow_metadata_updates"] is False
            return {
                "grid": [_asset("grid", name="Example Game")],
                "hero": [_asset("hero", name="Example Game")],
            }

        searcher = _searcher(cache, downloaded, collect_assets)
        outcome = searcher(
            BulkArtworkItem("game-1", "Example Game"), ("grid",), CancellationToken(), _progress
        )

    assert calls == [("Example Game", "Example Game")]
    # Only the requested slot is reported, even though the provider returned two.
    assert outcome.found_slots == frozenset({"grid"})
    assert outcome.candidate_ids == {"grid": "grid-1"}
    # An exact SteamGridDB title match, scored rather than assumed.
    assert outcome.evidence.identity_score == 95
    assert outcome.evidence.reasons  # the score explains itself


def test_a_wrong_game_is_scored_low_enough_for_the_policy_to_reject_it() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        downloaded = cache / "grid-1.png"
        downloaded.write_bytes(b"not-really-an-image")

        def collect_assets(game, term, client, **kwargs):
            return {"grid": [_asset("grid", name="Something Completely Different")]}

        searcher = _searcher(cache, downloaded, collect_assets)
        outcome = searcher(
            BulkArtworkItem("game-1", "Example Game"), ("grid",), CancellationToken(), _progress
        )

    assert outcome.evidence.identity_score < ArtworkMatchPolicy().reject_identity_below


def test_cancellation_is_checked_before_any_provider_call() -> None:
    token = CancellationToken()
    token.cancel()
    called = False

    def collect_assets(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    searcher = build_provider_searcher(
        game_lookup=lambda item_id: _game(),
        collect_assets=collect_assets,
        client=object(),
        cache_dir=Path("cache"),
    )

    try:
        searcher(BulkArtworkItem("game-1", "Example"), ("grid",), token, _progress)
    except JobCancelledError:
        pass
    else:  # pragma: no cover - defended by the assertion below
        raise AssertionError("A cancelled token must stop the search.")
    assert called is False


class _FakeInfo:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.format = "PNG"
        self.width = 600
        self.height = 900
        self.sha256 = "0" * 64
        self.average_hash = "0" * 16


if __name__ == "__main__":
    test_missing_game_reports_zero_scores_and_the_caller_supplied_reason()
    test_validated_candidates_are_scored_from_real_provider_evidence()
    test_a_wrong_game_is_scored_low_enough_for_the_policy_to_reject_it()
    test_cancellation_is_checked_before_any_provider_call()
    print("Artwork bulk search tests passed.")
