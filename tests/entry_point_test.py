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


def _run(argv, *, modern: _Recorder) -> int:
    original_modern = entry_point.run_modern
    entry_point.run_modern = modern
    try:
        return entry_point.main(argv)
    finally:
        entry_point.run_modern = original_modern


def test_default_launch_opens_the_modern_shell() -> None:
    modern = _Recorder()

    assert _run([], modern=modern) == 0
    assert modern.calls == [(None, False)]


def test_the_classic_flag_no_longer_exists() -> None:
    """The modern shell is the only interface; --classic must be rejected."""
    modern = _Recorder()

    try:
        _run(["--classic"], modern=modern)
    except SystemExit as exit_error:
        assert exit_error.code != 0
    else:  # pragma: no cover - guarded by the assertion below
        raise AssertionError("--classic must not be accepted any more.")
    assert modern.calls == []


def test_database_and_include_missing_reach_the_modern_shell() -> None:
    modern = _Recorder()

    _run(["--database", r"C:\tmp\library.sqlite3", "--include-missing"], modern=modern)

    (database, include_missing), = modern.calls
    assert Path(database) == Path(r"C:\tmp\library.sqlite3")
    assert include_missing is True


def test_a_missing_gui_dependency_fails_loudly() -> None:
    """A packaging mistake must be obvious, not a silent downgrade."""
    modern = _Recorder(fail_with=ImportError)

    assert _run([], modern=modern) == 1
    assert len(modern.calls) == 1


def test_unexpected_shell_errors_are_not_silently_swallowed() -> None:
    modern = _Recorder(fail_with=RuntimeError)

    try:
        _run([], modern=modern)
    except RuntimeError:
        pass
    else:  # pragma: no cover - guarded by the assertion below
        raise AssertionError("A real shell failure must surface, not be swallowed.")


if __name__ == "__main__":
    test_default_launch_opens_the_modern_shell()
    test_the_classic_flag_no_longer_exists()
    test_database_and_include_missing_reach_the_modern_shell()
    test_a_missing_gui_dependency_fails_loudly()
    test_unexpected_shell_errors_are_not_silently_swallowed()
    print("Entry point tests passed.")
