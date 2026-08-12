from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_bulk_search import (  # noqa: E402
    PLACEHOLDER_IDENTITY_SCORE,
    PLACEHOLDER_SET_COHERENCE_SCORE,
    build_provider_searcher,
)
from steam_shortcut_studio.artwork_policy import ArtworkMatchPolicy  # noqa: E402
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


def _asset(slot: str) -> ArtworkAsset:
    return ArtworkAsset(kind=slot, asset_id=f"{slot}-1", url=f"https://example.invalid/{slot}.png")


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


def test_validated_candidates_are_reported_with_placeholder_scores() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp)
        downloaded = cache / "grid-1.png"
        downloaded.write_bytes(b"not-really-an-image")
        calls: list[tuple[str, str]] = []

        def collect_assets(game, term, client, **kwargs):
            calls.append((game.title, term))
            assert kwargs["allow_metadata_updates"] is False
            return {"grid": [_asset("grid")], "hero": [_asset("hero")]}

        searcher = build_provider_searcher(
            game_lookup=lambda item_id: _game(),
            collect_assets=collect_assets,
            client=object(),
            cache_dir=cache,
            enabled_sources={"steamgriddb": True},
            downloader=lambda asset, directory: downloaded,
            validator=lambda path: _FakeInfo(Path(path)),
        )

        outcome = searcher(
            BulkArtworkItem("game-1", "Example"), ("grid",), CancellationToken(), _progress
        )

    assert calls == [("Example Game", "Example Game")]
    # Only the requested slot is reported, even though the provider returned two.
    assert outcome.found_slots == frozenset({"grid"})
    assert outcome.candidate_ids == {"grid": "grid-1"}
    assert outcome.evidence.identity_score == PLACEHOLDER_IDENTITY_SCORE
    assert outcome.evidence.set_coherence_score == PLACEHOLDER_SET_COHERENCE_SCORE


def test_placeholder_scores_can_never_auto_accept() -> None:
    """The gate that makes a review queue mandatory rather than optional."""
    policy = ArtworkMatchPolicy()
    assert PLACEHOLDER_IDENTITY_SCORE < policy.auto_identity_threshold
    assert PLACEHOLDER_SET_COHERENCE_SCORE < policy.auto_set_threshold
    assert PLACEHOLDER_IDENTITY_SCORE >= policy.reject_identity_below


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
    test_validated_candidates_are_reported_with_placeholder_scores()
    test_placeholder_scores_can_never_auto_accept()
    test_cancellation_is_checked_before_any_provider_call()
    print("Artwork bulk search tests passed.")
