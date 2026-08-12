from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_policy import (  # noqa: E402
    ArtworkDecision,
    ArtworkEvidence,
    ArtworkMatchPolicy,
)
from steam_shortcut_studio.artwork_scoring import (  # noqa: E402
    MATCH_PROVENANCE_KEY,
    MatchMethod,
    UNVERIFIABLE_IDENTITY,
    edition_tokens,
    editions_conflict,
    identity_score_for_asset,
    match_method,
    matched_title,
    provider_name,
    score_artwork_set,
    years_conflict,
)
from steam_shortcut_studio.models import ArtworkAsset  # noqa: E402


def _asset(
    slot: str,
    *,
    provider: str = "SteamGridDB",
    method: MatchMethod = MatchMethod.TITLE_SEARCH,
    name: str = "",
    appid: int | None = None,
    year: str = "",
    width: int = 0,
    height: int = 0,
    url: str = "https://example.invalid/a.png",
) -> ArtworkAsset:
    provenance: dict[str, object] = {"provider": provider, "method": str(method)}
    if name:
        provenance["name"] = name
    if appid:
        provenance["appid"] = str(appid)
    if year:
        provenance["year"] = year
    return ArtworkAsset(
        kind=slot,
        asset_id=f"{slot}-1",
        url=url,
        width=width,
        height=height,
        raw={"source": provider, MATCH_PROVENANCE_KEY: provenance},
    )


def _sized(slot: str, **kwargs) -> ArtworkAsset:
    """An asset with the correct shape for its slot, so shape never confounds."""
    shapes = {
        "grid": (600, 900), "wide": (616, 353), "hero": (1920, 620),
        "logo": (512, 256), "icon": (256, 256),
    }
    width, height = shapes[slot]
    kwargs.setdefault("width", width)
    kwargs.setdefault("height", height)
    return _asset(slot, **kwargs)


# ---------- provenance reading ----------

def test_provenance_helpers_read_what_the_search_service_stamps() -> None:
    asset = _asset("grid", provider="Steam", method=MatchMethod.STEAM_APPID, name="Portal 2", appid=620)

    assert match_method(asset) is MatchMethod.STEAM_APPID
    assert provider_name(asset) == "Steam"
    assert matched_title(asset) == "Portal 2"


def test_unstamped_assets_are_never_treated_as_verified() -> None:
    bare = ArtworkAsset(kind="grid", asset_id="g", url="https://cdn2.steamgriddb.com/x.png")

    assert match_method(bare) is MatchMethod.UNKNOWN
    assert provider_name(bare) == "SteamGridDB"
    assert matched_title(bare) == ""


# ---------- identity ----------

def test_an_appid_the_library_row_owns_is_certain() -> None:
    asset = _asset("grid", provider="Steam", method=MatchMethod.STEAM_APPID, appid=620)

    score, reason = identity_score_for_asset(asset, library_title="Portal 2", steam_appid=620)

    assert score == 100
    assert "620" in reason


def test_an_appid_that_does_not_match_the_row_falls_back_to_the_title() -> None:
    """A stamped AppID only certifies the match if it is *this* game's AppID."""
    asset = _asset("grid", provider="Steam", method=MatchMethod.STEAM_APPID, appid=999, name="Portal 2")

    score, _ = identity_score_for_asset(asset, library_title="Portal 2", steam_appid=620)

    assert score < 100


def test_title_matches_are_capped_by_how_much_the_provider_can_be_trusted() -> None:
    exact_sgdb = _asset("grid", provider="SteamGridDB", name="Hollow Knight")
    exact_wiki = _asset("grid", provider="Wikipedia/Wikimedia", name="Hollow Knight")

    sgdb_score, _ = identity_score_for_asset(exact_sgdb, library_title="Hollow Knight")
    wiki_score, _ = identity_score_for_asset(exact_wiki, library_title="Hollow Knight")

    assert sgdb_score > wiki_score
    assert sgdb_score == 95
    assert wiki_score == 70


def test_a_weak_title_match_scores_far_below_an_exact_one() -> None:
    exact = _asset("grid", name="Hollow Knight")
    wrong = _asset("grid", name="Hollow Knight Silksong")

    exact_score, _ = identity_score_for_asset(exact, library_title="Hollow Knight")
    wrong_score, _ = identity_score_for_asset(wrong, library_title="Hollow Knight")

    assert exact_score > wrong_score


def test_an_unverifiable_match_is_capped_below_the_automatic_threshold() -> None:
    """No title to compare means a human decides -- not a confident guess."""
    asset = _asset("grid", provider="SteamGridDB")

    score, reason = identity_score_for_asset(asset, library_title="Hollow Knight")

    assert score == UNVERIFIABLE_IDENTITY
    assert score < ArtworkMatchPolicy().auto_identity_threshold
    assert "no title" in reason.casefold()


# ---------- conflicts ----------

def test_edition_words_are_detected_on_either_side() -> None:
    assert edition_tokens("Alan Wake Remastered") == frozenset({"remastered"})
    assert editions_conflict("Alan Wake Remastered", "Alan Wake") is True
    assert editions_conflict("Control", "Control Ultimate Edition") is True
    assert editions_conflict("Hollow Knight", "Hollow Knight") is False
    assert editions_conflict("Alan Wake Remastered", "Alan Wake Remastered") is False
    assert editions_conflict("Hollow Knight", "") is False


def test_identifier_matches_never_raise_conflict_flags() -> None:
    """ArtworkMatchPolicy checks conflicts before scores, so a certain match
    must not be sent to review over edition wording."""
    selected = {
        "grid": _sized("grid", provider="Steam", method=MatchMethod.STEAM_APPID, appid=620,
                       name="Portal 2 Game of the Year")
    }

    score = score_artwork_set(selected, library_title="Portal 2", steam_appid=620)

    assert score.conflicting_edition is False
    assert score.identity_score == 100


def test_edition_conflict_is_raised_for_a_name_resolved_match() -> None:
    selected = {"grid": _sized("grid", name="Alan Wake")}

    score = score_artwork_set(selected, library_title="Alan Wake Remastered")

    assert score.conflicting_edition is True
    assert ArtworkMatchPolicy().evaluate(
        ArtworkEvidence(
            identity_score=score.identity_score,
            set_coherence_score=score.set_coherence_score,
            complete_set=True,
            conflicting_edition=score.conflicting_edition,
        )
    ).decision is ArtworkDecision.REVIEW


def test_release_year_conflicts_are_detected_only_when_both_years_are_known() -> None:
    assert years_conflict("2016", "2019") is True
    assert years_conflict("2016", "2016") is False
    assert years_conflict("", "2019") is False
    assert years_conflict("2016", "") is False


def test_year_conflict_is_raised_from_stamped_provider_metadata() -> None:
    selected = {"grid": _sized("grid", name="Doom", year="1993")}

    score = score_artwork_set(selected, library_title="Doom", release_year="2016")

    assert score.conflicting_year is True


# ---------- set coherence ----------

def test_a_single_source_correctly_shaped_complete_set_scores_full_coherence() -> None:
    selected = {slot: _sized(slot, name="Hollow Knight") for slot in ("grid", "wide", "hero", "logo", "icon")}

    score = score_artwork_set(
        selected, library_title="Hollow Knight",
        requested_slots=("grid", "wide", "hero", "logo", "icon"),
    )

    assert score.set_coherence_score == 100


def test_mixing_name_resolved_providers_reduces_coherence() -> None:
    selected = {
        "grid": _sized("grid", provider="SteamGridDB", name="Hollow Knight"),
        "hero": _sized("hero", provider="RAWG", name="Hollow Knight"),
    }

    score = score_artwork_set(selected, library_title="Hollow Knight")

    assert score.set_coherence_score < 100
    assert any("different sources" in reason for reason in score.reasons)


def test_mixing_identifier_resolved_providers_costs_nothing() -> None:
    """Steam's own capsules plus a SteamGridDB icon, both answering one AppID,
    is the most common good result -- it must not be penalised as incoherent."""
    selected = {
        slot: _sized(slot, provider="Steam", method=MatchMethod.STEAM_APPID, appid=620)
        for slot in ("grid", "wide", "hero", "logo")
    }
    selected["icon"] = _sized("icon", provider="SteamGridDB", method=MatchMethod.STEAM_APPID, appid=620)

    score = score_artwork_set(
        selected, library_title="Portal 2", steam_appid=620,
        requested_slots=("grid", "wide", "hero", "logo", "icon"),
    )

    assert score.identity_score == 100
    assert score.set_coherence_score == 100
    assert ArtworkMatchPolicy().evaluate(
        ArtworkEvidence(
            identity_score=score.identity_score,
            set_coherence_score=score.set_coherence_score,
            complete_set=True,
        )
    ).decision is ArtworkDecision.AUTO_ACCEPT


def test_a_wrongly_shaped_image_reduces_coherence() -> None:
    """A square image in the hero slot is the classic visibly-broken result."""
    good = {"hero": _sized("hero", name="Hollow Knight")}
    bad = {"hero": _asset("hero", name="Hollow Knight", width=512, height=512)}

    assert score_artwork_set(bad, library_title="Hollow Knight").set_coherence_score < (
        score_artwork_set(good, library_title="Hollow Knight").set_coherence_score
    )
    assert any("shape" in reason for reason in score_artwork_set(bad, library_title="Hollow Knight").reasons)


def test_missing_requested_slots_reduce_coherence() -> None:
    selected = {"grid": _sized("grid", name="Hollow Knight")}

    partial = score_artwork_set(
        selected, library_title="Hollow Knight",
        requested_slots=("grid", "wide", "hero", "logo", "icon"),
    )
    whole = score_artwork_set(selected, library_title="Hollow Knight", requested_slots=("grid",))

    assert partial.set_coherence_score < whole.set_coherence_score


def test_missing_dimensions_are_not_treated_as_a_wrong_shape() -> None:
    unknown = {"hero": _asset("hero", name="Hollow Knight", width=0, height=0)}

    score = score_artwork_set(unknown, library_title="Hollow Knight")

    assert score.set_coherence_score == 100


# ---------- identity is the weakest link ----------

def test_identity_is_the_weakest_slot_not_the_average() -> None:
    """Four certain slots must not carry one wrong image into an auto-apply."""
    selected = {
        "grid": _sized("grid", provider="Steam", method=MatchMethod.STEAM_APPID, appid=620),
        "wide": _sized("wide", provider="Steam", method=MatchMethod.STEAM_APPID, appid=620),
        "hero": _sized("hero", provider="Steam", method=MatchMethod.STEAM_APPID, appid=620),
        "logo": _sized("logo", provider="Steam", method=MatchMethod.STEAM_APPID, appid=620),
        "icon": _sized("icon", provider="Wikipedia/Wikimedia", name="Something Else Entirely"),
    }

    score = score_artwork_set(selected, library_title="Portal 2", steam_appid=620)

    assert score.identity_score < 60


def test_an_empty_selection_scores_zero() -> None:
    score = score_artwork_set({}, library_title="Anything")

    assert (score.identity_score, score.set_coherence_score) == (0, 0)


# ---------- the outcome that matters ----------

def test_a_certain_complete_set_can_finally_auto_accept() -> None:
    """The whole point of scoring: strong complete matches stop needing review."""
    selected = {
        slot: _sized(slot, provider="Steam", method=MatchMethod.STEAM_APPID, appid=620)
        for slot in ("grid", "wide", "hero", "logo", "icon")
    }

    score = score_artwork_set(
        selected, library_title="Portal 2", steam_appid=620,
        requested_slots=("grid", "wide", "hero", "logo", "icon"),
    )
    decision = ArtworkMatchPolicy().evaluate(
        ArtworkEvidence(
            identity_score=score.identity_score,
            set_coherence_score=score.set_coherence_score,
            complete_set=True,
            conflicting_edition=score.conflicting_edition,
            conflicting_year=score.conflicting_year,
        )
    ).decision

    assert decision is ArtworkDecision.AUTO_ACCEPT


def test_an_unverifiable_set_still_goes_to_review() -> None:
    selected = {slot: _sized(slot) for slot in ("grid", "wide", "hero", "logo", "icon")}

    score = score_artwork_set(
        selected, library_title="Some Obscure Game",
        requested_slots=("grid", "wide", "hero", "logo", "icon"),
    )
    decision = ArtworkMatchPolicy().evaluate(
        ArtworkEvidence(
            identity_score=score.identity_score,
            set_coherence_score=score.set_coherence_score,
            complete_set=True,
        )
    ).decision

    assert decision is ArtworkDecision.REVIEW


def test_scores_always_stay_inside_the_range_artwork_evidence_accepts() -> None:
    """ArtworkEvidence raises outside 0-100, which would fail a job mid-queue."""
    hostile = {
        "grid": _asset("grid", provider="Nonexistent Provider", name="", width=1, height=9999),
        "wide": _asset("wide", provider="RAWG", name="x" * 400, width=9999, height=1),
        "hero": _asset("hero", provider="Wikipedia/Wikimedia", name="", width=0, height=0),
        "logo": _asset("logo", provider="Steam", name="", width=1, height=1),
        "icon": _asset("icon", provider="SteamGridDB", name="", width=1, height=1),
    }

    score = score_artwork_set(
        hostile, library_title="", requested_slots=("grid", "wide", "hero", "logo", "icon"),
    )

    ArtworkEvidence(
        identity_score=score.identity_score,
        set_coherence_score=score.set_coherence_score,
    )
    assert 0 <= score.identity_score <= 100
    assert 0 <= score.set_coherence_score <= 100


if __name__ == "__main__":
    for name, value in sorted(dict(globals()).items()):
        if name.startswith("test_") and callable(value):
            value()
    print("Artwork scoring tests passed.")
