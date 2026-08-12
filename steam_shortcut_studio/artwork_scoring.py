"""Confidence scoring for artwork candidates.

`ArtworkMatchPolicy` decides whether a match may be applied automatically, but
it can only be as good as the evidence handed to it. This module produces that
evidence from data the providers already return -- no network, no Tk, no I/O --
so the decision is testable and explainable rather than a magic number.

The organising idea is **how the match was established**, not which provider
produced it:

* Resolved by a stable identifier (a Steam AppID the library row already owns)
  is certain. Nothing about a title can contradict it.
* Resolved by name is only as good as the name comparison, capped by how much
  the provider's own matching can be trusted.
* Not verifiable at all is capped below the automatic threshold on purpose. A
  human decides those, which is the honest outcome rather than a confident
  guess.

Set coherence asks a different question: do these files look like one artwork
set for one game? Slots pulled from different providers, or images whose shape
is wrong for the slot they landed in, are the two failure modes that produce a
visibly broken Steam library, so both are penalised.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from .models import ArtworkAsset
from .scanner import normalize_title, similarity


MATCH_PROVENANCE_KEY = "sss_match"


class MatchMethod(StrEnum):
    """How a provider arrived at the game it returned artwork for."""

    STEAM_APPID = "steam_appid"
    """Fetched by a Steam AppID the library row already owns."""

    PROVIDER_ID = "provider_id"
    """Fetched by a provider-side ID a previous identifier match established."""

    TITLE_SEARCH = "title_search"
    """Found by searching a name. Only as good as the name comparison."""

    UNKNOWN = "unknown"
    """No provenance recorded. Never treated as verified."""


# How far a match established by *name* can be trusted, per provider. These are
# ceilings, not scores: the title comparison scales each one down. A provider
# whose own matching is strict (SteamGridDB refuses weak title matches before
# returning anything) earns a higher ceiling than one that returns whatever its
# search endpoint ranked first.
PROVIDER_TITLE_CEILING: dict[str, int] = {
    "steam": 96,
    "steam store": 96,
    "steamgriddb": 95,
    "rawg": 78,
    "wikipedia/wikimedia": 70,
}
DEFAULT_TITLE_CEILING = 70

# Identity for a match nothing can verify: below ArtworkMatchPolicy's automatic
# threshold, above its rejection threshold. It goes to a human, not to disk.
UNVERIFIABLE_IDENTITY = 80

# Expected width/height ratio per slot, with the tolerance band that still
# counts as correct. Measured against what SteamGridDB actually returns rather
# than against Steam's nominal store sizes:
#
#   grid  600x900 and 660x930 are both common  -> 0.67 to 0.71
#   wide  Steam's wide capsule is 920x430      -> 2.14, and 616x353 (1.75) also occurs
#   hero  3840x1240 and 1920x620               -> 3.10 exactly
#   icon  512x512 / 1024x1024                  -> 1.00 exactly
#
# `logo` is deliberately absent. Logos are transparent wordmarks whose real
# ratios span 1.02 to 6.00 in this library alone, so there is no shape to check
# and any check produces false penalties.
SLOT_ASPECTS: dict[str, tuple[float, float]] = {
    "grid": (600 / 900, 0.18),
    "wide": (920 / 430, 0.55),
    "hero": (1920 / 620, 0.55),
    "icon": (1.0, 0.25),
}

_EDITION_WORDS = (
    "goty", "game of the year", "definitive", "ultimate", "deluxe", "complete",
    "remastered", "remaster", "enhanced", "anniversary", "director's cut",
    "directors cut", "gold", "legendary", "redux",
)
_YEAR_PATTERN = re.compile(r"\b(19[7-9]\d|20[0-4]\d)\b")


@dataclass(frozen=True, slots=True)
class ArtworkScore:
    """Evidence for one candidate artwork set, ready for `ArtworkMatchPolicy`."""

    identity_score: int
    set_coherence_score: int
    conflicting_edition: bool = False
    conflicting_year: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)


def match_provenance(asset: ArtworkAsset) -> Mapping[str, object]:
    raw = asset.raw if isinstance(asset.raw, Mapping) else {}
    provenance = raw.get(MATCH_PROVENANCE_KEY)
    return provenance if isinstance(provenance, Mapping) else {}


def match_method(asset: ArtworkAsset) -> MatchMethod:
    value = str(match_provenance(asset).get("method") or "")
    try:
        return MatchMethod(value)
    except ValueError:
        return MatchMethod.UNKNOWN


def provider_name(asset: ArtworkAsset) -> str:
    """Best available provider label for an asset."""
    raw = asset.raw if isinstance(asset.raw, Mapping) else {}
    source = str(raw.get("source") or "").strip()
    if source:
        return source
    recorded = str(match_provenance(asset).get("provider") or "").strip()
    if recorded:
        return recorded
    return "SteamGridDB" if "steamgriddb" in asset.url.casefold() else ""


def matched_title(asset: ArtworkAsset) -> str:
    """The provider's own name for the game it returned artwork for."""
    provenance = match_provenance(asset)
    for key in ("name", "title"):
        value = str(provenance.get(key) or "").strip()
        if value:
            return value
    raw = asset.raw if isinstance(asset.raw, Mapping) else {}
    for key in ("name", "title"):
        value = str(raw.get(key) or "").strip()
        if value:
            return value
    return ""


def edition_tokens(title: str) -> frozenset[str]:
    lowered = f" {str(title or '').casefold()} "
    return frozenset(word for word in _EDITION_WORDS if f" {word} " in lowered)


def release_years(text: str) -> frozenset[str]:
    return frozenset(_YEAR_PATTERN.findall(str(text or "")))


def editions_conflict(library_title: str, candidate_title: str) -> bool:
    """True when the two titles name *different* editions of the same game.

    `normalize_title` strips edition words before comparing, which is what lets
    "Alan Wake" match "Alan Wake Remastered" -- useful for *finding* the game,
    wrong for deciding whether this is the right art for the copy the user owns.
    Any difference in edition wording is left for a human, because that is
    precisely the case that yields plausible-looking but wrong box art.
    """
    if not candidate_title.strip():
        return False
    return edition_tokens(library_title) != edition_tokens(candidate_title)


def candidate_year(asset: ArtworkAsset) -> str:
    provenance = match_provenance(asset)
    for key in ("year", "released", "release_year"):
        found = release_years(str(provenance.get(key) or ""))
        if found:
            return sorted(found)[0]
    return ""


def years_conflict(library_year: str, candidate_year_text: str) -> bool:
    expected = release_years(library_year)
    found = release_years(candidate_year_text)
    if not expected or not found:
        return False
    return expected.isdisjoint(found)


def is_identifier_match(asset: ArtworkAsset) -> bool:
    """True when the game was resolved by ID rather than by name.

    Edition and year ambiguity simply does not arise for these: the AppID names
    exactly one store entry. `ArtworkMatchPolicy` checks the conflict flags
    before it looks at any score, so raising them here would send a certain
    match to review.
    """
    return match_method(asset) in (MatchMethod.STEAM_APPID, MatchMethod.PROVIDER_ID)


def identity_score_for_asset(
    asset: ArtworkAsset,
    *,
    library_title: str,
    steam_appid: int | None = None,
) -> tuple[int, str]:
    """Score one asset's identity confidence, with the reason for that score."""
    method = match_method(asset)
    provenance = match_provenance(asset)

    if method is MatchMethod.STEAM_APPID and steam_appid:
        recorded = str(provenance.get("appid") or "")
        if recorded.isdigit() and int(recorded) == int(steam_appid):
            return 100, f"Matched by Steam AppID {steam_appid}."
    if method is MatchMethod.PROVIDER_ID and steam_appid:
        return 97, "Matched through a provider ID resolved from this game's Steam AppID."

    candidate = matched_title(asset)
    provider = provider_name(asset)
    ceiling = PROVIDER_TITLE_CEILING.get(provider.casefold(), DEFAULT_TITLE_CEILING)
    if not candidate:
        return (
            min(UNVERIFIABLE_IDENTITY, ceiling),
            f"{provider or 'Provider'} returned no title to verify the match against.",
        )

    ratio = similarity(library_title, candidate)
    score = int(round(ceiling * ratio))
    return score, f'{provider or "Provider"} matched "{candidate}" (title similarity {ratio:.2f}).'


def _aspect_ratio_ok(slot: str, asset: ArtworkAsset) -> bool | None:
    """True/False when the shape can be judged, None when dimensions are absent."""
    expected = SLOT_ASPECTS.get(slot)
    if expected is None or not asset.width or not asset.height:
        return None
    target, tolerance = expected
    return abs((asset.width / asset.height) - target) <= tolerance


def score_artwork_set(
    selected: Mapping[str, ArtworkAsset],
    *,
    library_title: str,
    requested_slots: Sequence[str] = (),
    release_year: str = "",
    steam_appid: int | None = None,
) -> ArtworkScore:
    """Build `ArtworkScore` for the assets chosen for one game.

    Identity is the *weakest* slot's confidence, not the average: a set is only
    as trustworthy as its worst member, and averaging would let four certain
    slots carry one wrong image into an automatic apply.
    """
    if not selected:
        return ArtworkScore(
            identity_score=0,
            set_coherence_score=0,
            reasons=("No artwork candidate passed validation.",),
        )

    reasons: list[str] = []
    identities: list[int] = []
    for slot in sorted(selected):
        score, reason = identity_score_for_asset(
            selected[slot], library_title=library_title, steam_appid=steam_appid
        )
        identities.append(score)
        reasons.append(f"{slot}: {reason}")
    identity = min(identities)

    conflicting_edition = False
    conflicting_year = False
    for asset in selected.values():
        if is_identifier_match(asset):
            continue
        candidate = matched_title(asset)
        if editions_conflict(library_title, candidate):
            conflicting_edition = True
            reasons.append(f'Edition mismatch between "{library_title}" and "{candidate}".')
        year_text = candidate_year(asset)
        if years_conflict(release_year, year_text):
            conflicting_year = True
            reasons.append(f'Release year mismatch: library says {release_year}, provider says {year_text}.')

    coherence = 100
    # Only name-resolved assets can disagree about *which game* this is; two
    # sources that both answered a Steam AppID are describing the same store
    # entry, so mixing them costs nothing. Penalising that would put the most
    # common good case (Steam's own capsules plus a SteamGridDB icon) one point
    # from failing for no real reason.
    ambiguous_providers = {
        provider_name(asset).casefold() or "unknown"
        for asset in selected.values()
        if not is_identifier_match(asset)
    }
    if len(ambiguous_providers) > 1:
        penalty = min(40, 15 * (len(ambiguous_providers) - 1))
        coherence -= penalty
        reasons.append(
            f"Artwork was matched by name across {len(ambiguous_providers)} different sources "
            f"({', '.join(sorted(ambiguous_providers))}), which may not be the same game."
        )

    wrong_shape = [
        slot for slot, asset in selected.items() if _aspect_ratio_ok(slot, asset) is False
    ]
    if wrong_shape:
        coherence -= min(45, 15 * len(wrong_shape))
        reasons.append(
            "Wrong image shape for " + ", ".join(sorted(wrong_shape)) + "; Steam will crop or letterbox it."
        )

    requested = [slot for slot in requested_slots if slot]
    if requested:
        missing = [slot for slot in requested if slot not in selected]
        if missing:
            coverage = len(selected) / len(requested)
            coherence -= int(round(25 * (1 - coverage)))
            reasons.append(f"No candidate for {', '.join(sorted(missing))}.")

    return ArtworkScore(
        identity_score=max(0, min(100, identity)),
        set_coherence_score=max(0, min(100, coherence)),
        conflicting_edition=conflicting_edition,
        conflicting_year=conflicting_year,
        reasons=tuple(reasons),
    )
