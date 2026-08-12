from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.steam_playtime import (  # noqa: E402
    format_last_played,
    last_played_from_localconfig,
    load_last_played,
    localconfig_paths,
)


def _localconfig(apps: dict[str, dict[str, str]]) -> str:
    lines = ['"UserLocalConfigStore"', "{", '\t"Software"', "\t{", '\t\t"Valve"', "\t\t{",
             '\t\t\t"Steam"', "\t\t\t{", '\t\t\t\t"apps"', "\t\t\t\t{"]
    for appid, values in apps.items():
        lines.append(f'\t\t\t\t\t"{appid}"')
        lines.append("\t\t\t\t\t{")
        for key, value in values.items():
            lines.append(f'\t\t\t\t\t\t"{key}"\t\t"{value}"')
        lines.append("\t\t\t\t\t}")
    lines += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}", "}"]
    return "\n".join(lines) + "\n"


def _write_user(root: Path, user: str, apps: dict[str, dict[str, str]]) -> Path:
    config = root / "userdata" / user / "config"
    config.mkdir(parents=True, exist_ok=True)
    path = config / "localconfig.vdf"
    path.write_text(_localconfig(apps), encoding="utf-8")
    return path


def test_last_played_is_read_from_the_documented_vdf_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_user(Path(tmp), "1", {
            "220": {"LastPlayed": "1700000000", "Playtime": "500"},
            "620": {"LastPlayed": "1600000000"},
        })

        assert last_played_from_localconfig(path) == {220: 1700000000, 620: 1600000000}


def test_never_played_and_malformed_entries_are_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_user(Path(tmp), "1", {
            "220": {"LastPlayed": "0"},
            "620": {"LastPlayed": "not-a-number"},
            "630": {"LastPlayed": "-5"},
            "640": {"Playtime": "100"},
            "notanappid": {"LastPlayed": "1700000000"},
            "650": {"LastPlayed": "1700000000"},
        })

        assert last_played_from_localconfig(path) == {650: 1700000000}


def test_steam_casing_changes_do_not_break_the_lookup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "localconfig.vdf"
        path.write_text(
            _localconfig({"220": {"lastplayed": "1700000000"}}).replace('"Steam"', '"steam"'),
            encoding="utf-8",
        )

        assert last_played_from_localconfig(path) == {220: 1700000000}


def test_an_unreadable_or_foreign_file_yields_no_data_rather_than_an_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nope.vdf"
        garbage = Path(tmp) / "garbage.vdf"
        garbage.write_text("this is not vdf at all {{{", encoding="utf-8")
        other = Path(tmp) / "other.vdf"
        other.write_text('"SomethingElse"\n{\n\t"a"\t\t"b"\n}\n', encoding="utf-8")

        assert last_played_from_localconfig(missing) == {}
        assert last_played_from_localconfig(garbage) == {}
        assert last_played_from_localconfig(other) == {}


def test_multiple_users_merge_to_the_most_recent_play() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_user(root, "1", {"220": {"LastPlayed": "1600000000"}, "620": {"LastPlayed": "1500000000"}})
        _write_user(root, "2", {"220": {"LastPlayed": "1700000000"}})

        assert len(localconfig_paths(root)) == 2
        assert load_last_played(root) == {220: 1700000000, 620: 1500000000}


def test_a_missing_steam_path_yields_no_data() -> None:
    assert load_last_played(None) == {}
    assert load_last_played("") == {}
    with tempfile.TemporaryDirectory() as tmp:
        assert load_last_played(Path(tmp)) == {}
        assert localconfig_paths(Path(tmp)) == ()


def test_recency_is_described_in_the_units_a_person_would_use() -> None:
    now = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)

    def when(days: int) -> str:
        return format_last_played(int((now - timedelta(days=days)).timestamp()), now=now)

    assert when(0) == "Today"
    assert when(1) == "Yesterday"
    assert when(3) == "3 days ago"
    assert when(10) == "1 week ago"
    assert when(20) == "2 weeks ago"
    assert when(200) == format_last_played(int((now - timedelta(days=200)).timestamp()), now=now)
    assert "ago" in when(400)


def test_no_record_shows_an_em_dash_rather_than_a_fabricated_date() -> None:
    assert format_last_played(0) == "—"
    assert format_last_played(-1) == "—"


def test_a_future_timestamp_shows_a_date_instead_of_negative_days() -> None:
    now = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
    future = int((now + timedelta(days=30)).timestamp())

    assert "ago" not in format_last_played(future, now=now)


if __name__ == "__main__":
    for name, value in sorted(dict(globals()).items()):
        if name.startswith("test_") and callable(value):
            value()
    print("Steam playtime tests passed.")
