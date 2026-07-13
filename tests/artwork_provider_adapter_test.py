from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_provider_adapter import (  # noqa: E402
    artwork_assets_to_search_outcome,
    provider_pending_outcome,
    validated_artwork_assets_to_search_outcome,
)
from steam_shortcut_studio.models import ArtworkAsset  # noqa: E402


def test_provider_pending_outcome_is_review_safe_empty_result() -> None:
    outcome = provider_pending_outcome()

    assert outcome.provider == "provider-pending"
    assert outcome.found_slots == frozenset()
    assert outcome.evidence.identity_score == 0
    assert outcome.details["status"] == "provider_extraction_pending"


def test_artwork_assets_to_search_outcome_maps_requested_slots() -> None:
    outcome = artwork_assets_to_search_outcome(
        {
            "grid": [
                ArtworkAsset(
                    kind="grid",
                    asset_id="grid-one",
                    url="https://example.invalid/grid.png",
                )
            ],
            "logo": [
                ArtworkAsset(
                    kind="logo",
                    asset_id="logo-one",
                    url="https://example.invalid/logo.png",
                )
            ],
            "hero": [
                ArtworkAsset(
                    kind="hero",
                    asset_id="hero-one",
                    url="https://example.invalid/hero.png",
                )
            ],
        },
        ("grid", "logo"),
        provider="fixture",
        identity_score=96,
        set_coherence_score=90,
    )

    assert outcome.provider == "fixture"
    assert outcome.found_slots == frozenset({"grid", "logo"})
    assert outcome.candidate_ids == {"grid": "grid-one", "logo": "logo-one"}
    assert outcome.details["candidate_urls"] == {
        "grid": "https://example.invalid/grid.png",
        "logo": "https://example.invalid/logo.png",
    }


def test_validated_artwork_assets_to_search_outcome_skips_invalid_candidates() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        good_path = root / "good.png"
        Image.new("RGB", (64, 96), color=(30, 60, 90)).save(good_path)

        def downloader(asset: ArtworkAsset, _cache_dir: Path) -> Path:
            if asset.asset_id == "bad-grid":
                bad_path = root / "bad-grid.txt"
                bad_path.write_text("<html>not image</html>", encoding="utf-8")
                return bad_path
            asset.local_path = good_path
            return good_path

        outcome = validated_artwork_assets_to_search_outcome(
            {
                "grid": [
                    ArtworkAsset(kind="grid", asset_id="bad-grid", url="https://example.invalid/bad.png"),
                    ArtworkAsset(kind="grid", asset_id="good-grid", url="https://example.invalid/good.png"),
                ],
                "logo": [],
            },
            ("grid", "logo"),
            cache_dir=root,
            provider="fixture",
            identity_score=70,
            set_coherence_score=60,
            reasons=("validated provider candidates require review",),
            downloader=downloader,
        )

    assert outcome.found_slots == frozenset({"grid"})
    assert outcome.candidate_ids == {"grid": "good-grid"}
    assert outcome.details["validated_files"]["grid"]["width"] == 64
    assert outcome.details["rejected_candidates"]["grid"][0].startswith("bad-grid:")


if __name__ == "__main__":
    test_provider_pending_outcome_is_review_safe_empty_result()
    test_artwork_assets_to_search_outcome_maps_requested_slots()
    test_validated_artwork_assets_to_search_outcome_skips_invalid_candidates()
    print("Artwork provider adapter tests passed.")
