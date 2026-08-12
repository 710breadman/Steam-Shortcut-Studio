from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from .bulk_artwork import ARTWORK_SLOTS
from .job_queue import JobEvent
from .jobs import JobState, TERMINAL_JOB_STATES

ArtworkReviewAction = Literal["accept", "reject", "skip"]
ArtworkReviewSelectionAction = Literal["review", "clear_rejections"]


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


def artwork_review_selection_required_message(action: ArtworkReviewSelectionAction) -> str:
    if action == "clear_rejections":
        return "Select stored library rows before clearing artwork rejections."
    return "Select stored library rows before reviewing artwork decisions."


def artwork_review_no_pending_message(*, retry: bool = False) -> str:
    if retry:
        return "No selected rows have pending artwork review results to retry."
    return "No selected rows have pending artwork review results."


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


@dataclass(frozen=True, slots=True)
class ArtworkQueueUpdate:
    """What a UI should do after one bulk artwork job event."""

    job_id: str
    item_id: str
    status: str
    terminal: bool
    needs_review: bool


def artwork_job_status_text(
    decision: str,
    requested_slots: Sequence[str] = (),
    *,
    accepted: int = 0,
    rejected: int = 0,
) -> str:
    status = f"Artwork {decision}"
    slots = ", ".join(str(slot) for slot in requested_slots)
    if slots:
        status += f" ({slots})"
    if accepted or rejected:
        status += f"; saved {accepted} accepted/{rejected} rejected"
    return status


def artwork_queue_progress_text(active_jobs: int, pending_items: int) -> str:
    if active_jobs:
        return (
            f"Artwork search: {active_jobs} job(s) running, "
            f"{pending_items} awaiting review."
        )
    if pending_items:
        return f"Artwork search finished. {pending_items} game(s) awaiting review."
    return "Artwork search finished. Nothing is awaiting review."


class ArtworkReviewQueue:
    """Tk-free record of in-flight bulk artwork jobs and their review results.

    `BulkArtworkCoordinator` routes anything the policy will not auto-accept to
    `JobState.NEEDS_REVIEW`, which leaves the caller holding a result that has
    validated candidate files but no decision. This owns that holding area so
    both the polling loop and the review screen read the same state, and so the
    behaviour is testable without a Tk window.

    Nothing here writes to disk. Persisting an accepted or rejected decision
    stays with `LibraryController`, and getting an accepted file into Steam
    stays a separate, explicit Apply Changes step.
    """

    def __init__(self) -> None:
        self._job_items: dict[str, str] = {}
        self._results: dict[str, dict[str, object]] = {}

    def track(self, job_id: str, item_id: str) -> None:
        self._job_items[job_id] = item_id

    def tracks(self, job_id: str) -> bool:
        return job_id in self._job_items

    @property
    def job_ids(self) -> tuple[str, ...]:
        """Jobs submitted but not yet finished, for cancellation and busy state."""
        return tuple(self._job_items)

    @property
    def active_job_count(self) -> int:
        return len(self._job_items)

    @property
    def results(self) -> Mapping[str, Mapping[str, object]]:
        return dict(self._results)

    @property
    def pending_item_ids(self) -> tuple[str, ...]:
        return tuple(self._results)

    @property
    def pending_slot_count(self) -> int:
        return sum(review_result_slot_count(result) for result in self._results.values())

    def result_for(self, item_id: str) -> Mapping[str, object] | None:
        return self._results.get(item_id)

    def results_for(self, item_ids: Sequence[str]) -> tuple[Mapping[str, object], ...]:
        return selected_artwork_review_results(item_ids, self._results)

    def discard(self, item_id: str) -> bool:
        return self._results.pop(item_id, None) is not None

    def clear(self) -> int:
        cleared = len(self._results)
        self._results.clear()
        return cleared

    def handle_event(
        self,
        event: JobEvent,
        *,
        accepted: int = 0,
        rejected: int = 0,
    ) -> ArtworkQueueUpdate | None:
        """Fold one job event into the queue, or return None if untracked."""
        item_id = self._job_items.get(event.job_id)
        if item_id is None:
            return None

        if event.state not in TERMINAL_JOB_STATES:
            return ArtworkQueueUpdate(
                job_id=event.job_id,
                item_id=item_id,
                status=event.message or event.state.value,
                terminal=False,
                needs_review=False,
            )

        self._job_items.pop(event.job_id, None)
        result = dict(event.result or {})
        decision = str(result.get("decision") or event.state.value)
        needs_review = bool(result) and (
            decision == "review" or event.state is JobState.NEEDS_REVIEW
        )
        if needs_review:
            self._results[item_id] = result
        if event.state is JobState.FAILED:
            status = f"Artwork search failed: {event.error or event.message}"
        else:
            requested = result.get("requested_slots") or ()
            status = artwork_job_status_text(
                decision,
                requested if isinstance(requested, Sequence) and not isinstance(requested, str) else (),
                accepted=accepted,
                rejected=rejected,
            )
        return ArtworkQueueUpdate(
            job_id=event.job_id,
            item_id=item_id,
            status=status,
            terminal=True,
            needs_review=needs_review,
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
