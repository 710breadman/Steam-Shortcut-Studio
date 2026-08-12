from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as entry_point  # noqa: E402


class _Recorder:
    def __init__(self, fail_with: type[BaseException] | None = None) -> None:
        self.calls: list[tuple] = []
        self.fail_with = fail_with

    def __call__(self, *args) -> int:
        self.calls.append(args)
        if self.fail_with is not None:
            raise self.fail_with("simulated")
        return 0


def _run(argv, *, modern: _Recorder, classic: _Recorder) -> int:
    original_modern = entry_point.run_modern
    original_classic = entry_point.run_classic
    entry_point.run_modern = modern
    entry_point.run_classic = classic
    try:
        return entry_point.main(argv)
    finally:
        entry_point.run_modern = original_modern
        entry_point.run_classic = original_classic


def test_default_launch_opens_the_modern_shell() -> None:
    modern, classic = _Recorder(), _Recorder()

    assert _run([], modern=modern, classic=classic) == 0
    assert modern.calls == [(None, False)]
    assert classic.calls == []


def test_classic_flag_opens_the_classic_window_without_touching_the_shell() -> None:
    modern, classic = _Recorder(), _Recorder()

    assert _run(["--classic"], modern=modern, classic=classic) == 0
    assert classic.calls == [()]
    assert modern.calls == []


def test_database_and_include_missing_reach_the_modern_shell() -> None:
    modern, classic = _Recorder(), _Recorder()

    _run(["--database", r"C:\tmp\library.sqlite3", "--include-missing"], modern=modern, classic=classic)

    (database, include_missing), = modern.calls
    assert Path(database) == Path(r"C:\tmp\library.sqlite3")
    assert include_missing is True


def test_a_missing_gui_dependency_degrades_to_the_classic_window() -> None:
    """A packaging mistake must not leave a user with no app at all."""
    modern, classic = _Recorder(fail_with=ImportError), _Recorder()

    assert _run([], modern=modern, classic=classic) == 0
    assert len(modern.calls) == 1
    assert classic.calls == [()]


def test_unexpected_shell_errors_are_not_silently_swallowed() -> None:
    modern, classic = _Recorder(fail_with=RuntimeError), _Recorder()

    try:
        _run([], modern=modern, classic=classic)
    except RuntimeError:
        pass
    else:  # pragma: no cover - guarded by the assertion below
        raise AssertionError("A real shell failure must surface, not fall back silently.")
    assert classic.calls == []


if __name__ == "__main__":
    test_default_launch_opens_the_modern_shell()
    test_classic_flag_opens_the_classic_window_without_touching_the_shell()
    test_database_and_include_missing_reach_the_modern_shell()
    test_a_missing_gui_dependency_degrades_to_the_classic_window()
    test_unexpected_shell_errors_are_not_silently_swallowed()
    print("Entry point tests passed.")
