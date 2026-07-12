from __future__ import annotations

from collections.abc import Mapping, Sequence

from .artwork_policy import ArtworkEvidence
from .bulk_artwork import ARTWORK_SLOTS, ArtworkSearchOutcome
from .models import ArtworkAsset


def provider_pending_outcome() -> ArtworkSearchOutcome:
    return ArtworkSearchOutcome(
        evidence=ArtworkEvidence(
            identity_score=0,
            set_coherence_score=0,
            source="provider-pending",
            reasons=("Provider extraction is not connected yet.",),
        ),
        found_slots=frozenset(),
        provider="provider-pending",
        details={"status": "provider_extraction_pending"},
    )


def artwork_assets_to_search_outcome(
    assets_by_kind: Mapping[str, Sequence[ArtworkAsset]],
    requested_slots: tuple[str, ...],
    *,
    provider: str,
    identity_score: int,
    set_coherence_score: int,
    reasons: tuple[str, ...] = (),
) -> ArtworkSearchOutcome:
    requested = set(requested_slots)
    found_slots: set[str] = set()
    candidate_ids: dict[str, str] = {}
    urls: dict[str, str] = {}

    for slot in ARTWORK_SLOTS:
        if slot not in requested:
            continue
        assets = assets_by_kind.get(slot, ())
        if not assets:
            continue
        asset = assets[0]
        found_slots.add(slot)
        candidate_ids[slot] = asset.asset_id
        urls[slot] = asset.url

    return ArtworkSearchOutcome(
        evidence=ArtworkEvidence(
            identity_score=identity_score,
            set_coherence_score=set_coherence_score,
            source=provider,
            reasons=reasons,
        ),
        found_slots=frozenset(found_slots),
        provider=provider,
        candidate_ids=candidate_ids,
        details={"candidate_urls": urls},
    )
