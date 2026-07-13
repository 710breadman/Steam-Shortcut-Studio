from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .bulk_artwork import ARTWORK_SLOTS


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
