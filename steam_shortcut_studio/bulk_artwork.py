from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Callable, Mapping
from uuid import uuid4

from .artwork_policy import (
    ArtworkDecision,
    ArtworkEvidence,
    ArtworkMatchPolicy,
)
from .job_queue import BackgroundJobQueue, JobExecutionResult, ProgressReporter
from .jobs import CancellationToken, JobKind, JobRecord, JobState
from .selection import SelectionState


ARTWORK_SLOTS = ("grid", "wide", "hero", "logo", "icon")
_ARTWORK_SLOT_SET = frozenset(ARTWORK_SLOTS)


class ArtworkSearchMode(StrEnum):
    MISSING_ONLY = "missing_only"
    ALL_UNLOCKED = "all_unlocked"
    COMPLETE_SET = "complete_set"


@dataclass(frozen=True, slots=True)
class BulkArtworkItem:
    item_id: str
    title: str
    existing_slots: frozenset[str] = field(default_factory=frozenset)
    locked_slots: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("Bulk artwork items require a stable item ID.")
        unknown_existing = self.existing_slots - _ARTWORK_SLOT_SET
        unknown_locked = self.locked_slots - _ARTWORK_SLOT_SET
        if unknown_existing or unknown_locked:
            unknown = sorted(unknown_existing | unknown_locked)
            raise ValueError(f"Unknown artwork slots: {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class ArtworkSearchPlan:
    item_id: str
    title: str
    mode: ArtworkSearchMode
    requested_slots: tuple[str, ...]
    preserved_locked_slots: tuple[str, ...]
    preserved_existing_slots: tuple[str, ...]

    @property
    def has_work(self) -> bool:
        return bool(self.requested_slots)


@dataclass(frozen=True, slots=True)
class ArtworkSearchOutcome:
    evidence: ArtworkEvidence
    found_slots: frozenset[str]
    provider: str = ""
    candidate_ids: Mapping[str, str] = field(default_factory=dict)
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = self.found_slots - _ARTWORK_SLOT_SET
        if unknown:
            raise ValueError(f"Search outcome contains unknown slots: {', '.join(sorted(unknown))}")
        unknown_candidates = set(self.candidate_ids) - _ARTWORK_SLOT_SET
        if unknown_candidates:
            raise ValueError(
                "Candidate IDs contain unknown slots: "
                + ", ".join(sorted(unknown_candidates))
            )


ArtworkSearcher = Callable[
    [BulkArtworkItem, tuple[str, ...], CancellationToken, ProgressReporter],
    ArtworkSearchOutcome,
]


@dataclass(frozen=True, slots=True)
class BulkArtworkSubmission:
    jobs: tuple[JobRecord, ...]
    missing_item_ids: tuple[str, ...] = ()

    @property
    def submitted_count(self) -> int:
        return len(self.jobs)


def build_artwork_search_plan(
    item: BulkArtworkItem,
    mode: ArtworkSearchMode,
) -> ArtworkSearchPlan:
    locked = item.locked_slots
    if mode is ArtworkSearchMode.MISSING_ONLY:
        requested = [
            slot
            for slot in ARTWORK_SLOTS
            if slot not in item.existing_slots and slot not in locked
        ]
    else:
        requested = [slot for slot in ARTWORK_SLOTS if slot not in locked]

    return ArtworkSearchPlan(
        item_id=item.item_id,
        title=item.title,
        mode=mode,
        requested_slots=tuple(requested),
        preserved_locked_slots=tuple(slot for slot in ARTWORK_SLOTS if slot in locked),
        preserved_existing_slots=tuple(
            slot
            for slot in ARTWORK_SLOTS
            if slot in item.existing_slots and slot not in requested
        ),
    )


class BulkArtworkCoordinator:
    """Submit selected library items to the background artwork queue.

    The coordinator is deliberately provider- and UI-independent. A caller supplies
    a searcher that discovers and validates candidates. This class guarantees that
    only selected stable IDs are submitted, locked slots are excluded, and every
    result is routed through the automatic artwork policy.
    """

    def __init__(
        self,
        job_queue: BackgroundJobQueue,
        *,
        policy: ArtworkMatchPolicy | None = None,
    ) -> None:
        self.job_queue = job_queue
        self.policy = policy or ArtworkMatchPolicy()

    def submit_selected(
        self,
        selection: SelectionState,
        ordered_ids: list[str] | tuple[str, ...],
        items: Mapping[str, BulkArtworkItem],
        searcher: ArtworkSearcher,
        *,
        mode: ArtworkSearchMode = ArtworkSearchMode.MISSING_ONLY,
    ) -> BulkArtworkSubmission:
        selected_ids = selection.selected_in_order(ordered_ids)
        missing_ids = tuple(item_id for item_id in selected_ids if item_id not in items)
        jobs: list[JobRecord] = []

        for item_id in selected_ids:
            item = items.get(item_id)
            if item is None:
                continue
            plan = build_artwork_search_plan(item, mode)
            record = JobRecord(
                job_id=f"artwork-{item.item_id}-{uuid4().hex[:12]}",
                item_id=item.item_id,
                kind=JobKind.ARTWORK,
                message=f"Queued artwork search for {item.title}",
            )
            handler = self._handler_for(item, plan, searcher)
            self.job_queue.submit(record, handler)
            jobs.append(record)

        return BulkArtworkSubmission(tuple(jobs), missing_ids)

    def _handler_for(
        self,
        item: BulkArtworkItem,
        plan: ArtworkSearchPlan,
        searcher: ArtworkSearcher,
    ):
        def handler(
            record: JobRecord,
            token: CancellationToken,
            report_progress: ProgressReporter,
        ) -> JobExecutionResult:
            token.raise_if_cancelled()
            if not plan.has_work:
                return JobExecutionResult(
                    state=JobState.SKIPPED,
                    message="All requested artwork slots are already filled or locked.",
                    result=self._base_result(plan, decision="skipped", reasons=()),
                )

            report_progress(0.05, f"Searching artwork for {item.title}")
            outcome = searcher(item, plan.requested_slots, token, report_progress)
            token.raise_if_cancelled()

            found_requested = frozenset(outcome.found_slots).intersection(plan.requested_slots)
            if not found_requested:
                return JobExecutionResult(
                    state=JobState.SKIPPED,
                    message="No usable artwork candidates were found.",
                    result=self._outcome_result(
                        plan,
                        outcome,
                        decision=ArtworkDecision.REJECT.value,
                        reasons=("No requested artwork slots produced a usable candidate.",),
                    ),
                )

            request_complete = set(plan.requested_slots).issubset(found_requested)
            evidence = replace(
                outcome.evidence,
                complete_set=request_complete,
            )
            policy_result = self.policy.evaluate(evidence)
            result = self._outcome_result(
                plan,
                outcome,
                decision=policy_result.decision.value,
                reasons=policy_result.reasons,
                found_slots=found_requested,
            )

            if policy_result.decision is ArtworkDecision.AUTO_ACCEPT:
                state = JobState.SUCCEEDED
                message = "Artwork match passed automatic policy."
            elif policy_result.decision is ArtworkDecision.REVIEW:
                state = JobState.NEEDS_REVIEW
                message = "Artwork candidates need review."
            else:
                state = JobState.SKIPPED
                message = "Artwork candidates were rejected by policy."

            return JobExecutionResult(state=state, message=message, result=result)

        return handler

    @staticmethod
    def _base_result(
        plan: ArtworkSearchPlan,
        *,
        decision: str,
        reasons: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "item_id": plan.item_id,
            "decision": decision,
            "mode": plan.mode.value,
            "requested_slots": list(plan.requested_slots),
            "found_slots": [],
            "preserved_locked_slots": list(plan.preserved_locked_slots),
            "preserved_existing_slots": list(plan.preserved_existing_slots),
            "reasons": list(reasons),
        }

    @classmethod
    def _outcome_result(
        cls,
        plan: ArtworkSearchPlan,
        outcome: ArtworkSearchOutcome,
        *,
        decision: str,
        reasons: tuple[str, ...],
        found_slots: frozenset[str] | None = None,
    ) -> dict[str, object]:
        result = cls._base_result(plan, decision=decision, reasons=reasons)
        result.update(
            {
                "found_slots": [
                    slot
                    for slot in ARTWORK_SLOTS
                    if slot in (found_slots if found_slots is not None else outcome.found_slots)
                ],
                "provider": outcome.provider,
                "candidate_ids": dict(outcome.candidate_ids),
                "details": dict(outcome.details),
                "identity_score": outcome.evidence.identity_score,
                "set_coherence_score": outcome.evidence.set_coherence_score,
            }
        )
        return result
