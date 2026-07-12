from __future__ import annotations

from pathlib import Path

from . import steam_shortcuts as _steam_shortcuts
from .models import DetectedGame, SteamProfile
from .shortcut_transactions import upsert_games_transactional


# Keep the existing UI import surface stable while routing the desktop app through
# the verified transaction service. The legacy implementation remains available
# inside steam_shortcuts.py only for compatibility tests until that module is
# refactored in a later sprint.
def _transactional_upsert_games(
    profile: SteamProfile,
    games: list[DetectedGame],
    update_existing: bool = True,
    default_tags: list[str] | None = None,
) -> tuple[int, int, Path | None]:
    result = upsert_games_transactional(
        profile,
        games,
        update_existing=update_existing,
        default_tags=default_tags,
    )
    return result.as_legacy_tuple()


_legacy_preview_changes = _steam_shortcuts.preview_changes


def _safe_preview_changes(*args, **kwargs) -> str:
    text = _legacy_preview_changes(*args, **kwargs)
    return text.replace(
        "Warning: existing shortcuts.vdf could not be parsed and will be backed up/replaced during write:",
        "BLOCKED: existing shortcuts.vdf could not be parsed. No changes can be written until it is restored or repaired:",
    )


# ui.py imports these names from steam_shortcuts during module initialization.
# Install the safe production adapters before importing the UI.
_steam_shortcuts.upsert_games = _transactional_upsert_games
_steam_shortcuts.preview_changes = _safe_preview_changes

from .ui import main  # noqa: E402  (must import after production wiring)


if __name__ == "__main__":
    main()
