from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ArtworkDecision(StrEnum):
    AUTO_ACCEPT = "auto_accept"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class ArtworkEvidence:
    """Evidence used to decide whether artwork may be accepted automatically."""

    identity_score: int
    set_coherence_score: int
    valid_image: bool = True
    complete_set: bool = False
    manually_locked: bool = False
    conflicting_edition: bool = False
    conflicting_year: bool = False
    source: str = ""
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("identity_score", self.identity_score),
            ("set_coherence_score", self.set_coherence_score),
        ):
            if not 0 <= value <= 100:
                raise ValueError(f"{field_name} must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class ArtworkPolicyResult:
    decision: ArtworkDecision
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArtworkMatchPolicy:
    auto_identity_threshold: int = 92
    auto_set_threshold: int = 85
    reject_identity_below: int = 45
    require_complete_set_for_auto: bool = True

    def evaluate(self, evidence: ArtworkEvidence) -> ArtworkPolicyResult:
        reasons = list(evidence.reasons)

        if evidence.manually_locked:
            reasons.append("Artwork is manually locked.")
            return ArtworkPolicyResult(ArtworkDecision.REVIEW, tuple(reasons))

        if not evidence.valid_image:
            reasons.append("Candidate did not pass image validation.")
            return ArtworkPolicyResult(ArtworkDecision.REJECT, tuple(reasons))

        if evidence.identity_score < self.reject_identity_below:
            reasons.append(
                f"Identity score {evidence.identity_score} is below the rejection threshold "
                f"of {self.reject_identity_below}."
            )
            return ArtworkPolicyResult(ArtworkDecision.REJECT, tuple(reasons))

        if evidence.conflicting_edition:
            reasons.append("Candidate appears to target a conflicting game edition.")
            return ArtworkPolicyResult(ArtworkDecision.REVIEW, tuple(reasons))

        if evidence.conflicting_year:
            reasons.append("Candidate release year conflicts with the library item.")
            return ArtworkPolicyResult(ArtworkDecision.REVIEW, tuple(reasons))

        if evidence.identity_score < self.auto_identity_threshold:
            reasons.append(
                f"Identity score {evidence.identity_score} is below the automatic threshold "
                f"of {self.auto_identity_threshold}."
            )
            return ArtworkPolicyResult(ArtworkDecision.REVIEW, tuple(reasons))

        if evidence.set_coherence_score < self.auto_set_threshold:
            reasons.append(
                f"Set coherence score {evidence.set_coherence_score} is below the automatic "
                f"threshold of {self.auto_set_threshold}."
            )
            return ArtworkPolicyResult(ArtworkDecision.REVIEW, tuple(reasons))

        if self.require_complete_set_for_auto and not evidence.complete_set:
            reasons.append("Artwork set is incomplete.")
            return ArtworkPolicyResult(ArtworkDecision.REVIEW, tuple(reasons))

        reasons.append("Identity, image validation, and set coherence passed automatic policy.")
        return ArtworkPolicyResult(ArtworkDecision.AUTO_ACCEPT, tuple(reasons))
