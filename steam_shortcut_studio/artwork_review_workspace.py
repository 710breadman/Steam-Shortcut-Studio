from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .bulk_artwork import ARTWORK_SLOTS

ArtworkReviewAction = Literal["accept", "reject", "skip"]


@dataclass(frozen=True, slots=True)
class ArtworkReviewRow:
    item_id: str
    title: str
    slot: str
    candidate_id: str
    path: str
    provider: str
    width: int = 0
    height: int = 0
    identity_score: int = 0
    set_coherence_score: int = 0
    reasons: tuple[str, ...] = ()

    @property
    def dimensions_label(self) -> str:
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return ""


@dataclass(frozen=True, slots=True)
class ArtworkReviewSummary:
    selected_item_count: int
    pending_item_ids: tuple[str, ...]
    pending_slot_count: int

    @property
    def pending_item_count(self) -> int:
        return len(self.pending_item_ids)


def _object_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _object_sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _int_value(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def review_result_slot_count(result: Mapping[str, object]) -> int:
    candidate_ids = _object_mapping(result.get("candidate_ids"))
    return sum(1 for slot in ARTWORK_SLOTS if slot in candidate_ids)


def artwork_review_action_message(action: ArtworkReviewAction, candidate_count: int) -> str:
    action_text = {
        "accept": "Accepted",
        "reject": "Rejected",
        "skip": "Skipped",
    }[action]
    return f"{action_text} {candidate_count} artwork candidate(s)."


def artwork_review_header_text(
    selected_item_count: int,
    locked_slots: int,
    rejected_matches: int,
    pending_slot_count: int,
) -> str:
    return (
        f"Selected rows: {selected_item_count}    "
        f"Accepted/locked slots: {locked_slots}    "
        f"Rejected candidates: {rejected_matches}    "
        f"Pending review slots: {pending_slot_count}"
    )


def artwork_review_status_text(locked_slots: int, rejected_matches: int, pending_slot_count: int) -> str:
    return (
        f"Artwork decisions: {locked_slots} accepted/locked, "
        f"{rejected_matches} rejected, {pending_slot_count} pending slot(s)."
    )


def artwork_review_empty_message() -> str:
    return "No pending artwork review candidates for selected rows."


def artwork_review_detail_text(row: ArtworkReviewRow) -> str:
    reasons = "; ".join(row.reasons)
    return (
        f"{row.title}\n"
        f"{row.slot} / {row.provider or 'provider'} / {row.candidate_id}\n"
        f"Identity {row.identity_score}    Set {row.set_coherence_score}\n"
        f"{row.path}\n"
        f"{reasons}"
    ).strip()


def source_review_clear_message(review_count: int) -> str:
    if review_count:
        return f"Cleared {review_count} source review job(s)."
    return "No source review jobs to clear."


def artwork_rejection_clear_message(candidate_count: int) -> str:
    return f"Cleared {candidate_count} rejected artwork candidate(s)."


def pending_review_item_ids(
    item_ids: Sequence[str],
    review_results: Mapping[str, Mapping[str, object]],
) -> tuple[str, ...]:
    return tuple(item_id for item_id in item_ids if item_id in review_results)


def selected_artwork_review_results(
    item_ids: Sequence[str],
    review_results: Mapping[str, Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        result
        for item_id in item_ids
        if (result := review_results.get(item_id)) is not None
    )


def build_artwork_review_summary(
    item_ids: Sequence[str],
    review_results: Mapping[str, Mapping[str, object]],
) -> ArtworkReviewSummary:
    pending_ids = pending_review_item_ids(item_ids, review_results)
    return ArtworkReviewSummary(
        selected_item_count=len(item_ids),
        pending_item_ids=pending_ids,
        pending_slot_count=sum(review_result_slot_count(review_results[item_id]) for item_id in pending_ids),
    )


def build_artwork_review_rows(
    item_ids: Sequence[str],
    row_titles: Mapping[str, str],
    review_results: Mapping[str, Mapping[str, object]],
) -> tuple[ArtworkReviewRow, ...]:
    rows: list[ArtworkReviewRow] = []
    for item_id in item_ids:
        result = review_results.get(item_id)
        if result is None:
            continue
        candidate_ids = _object_mapping(result.get("candidate_ids"))
        details = _object_mapping(result.get("details"))
        validated_files = _object_mapping(details.get("validated_files"))
        reasons = tuple(str(reason) for reason in _object_sequence(result.get("reasons")))
        provider = str(result.get("provider") or "")
        identity_score = _int_value(result.get("identity_score"))
        set_coherence_score = _int_value(result.get("set_coherence_score"))

        for slot in ARTWORK_SLOTS:
            candidate_id = candidate_ids.get(slot)
            if candidate_id is None:
                continue
            file_info = _object_mapping(validated_files.get(slot))
            rows.append(
                ArtworkReviewRow(
                    item_id=item_id,
                    title=row_titles.get(item_id, item_id),
                    slot=slot,
                    candidate_id=str(candidate_id),
                    path=str(file_info.get("path") or ""),
                    provider=provider,
                    width=_int_value(file_info.get("width")),
                    height=_int_value(file_info.get("height")),
                    identity_score=identity_score,
                    set_coherence_score=set_coherence_score,
                    reasons=reasons,
                )
            )
    return tuple(rows)
