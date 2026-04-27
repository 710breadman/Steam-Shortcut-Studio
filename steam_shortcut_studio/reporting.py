from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import DetectedGame


def game_to_dict(game: DetectedGame) -> dict[str, object]:
    candidate = game.selected_candidate
    return {
        "selected": game.selected,
        "title": game.title,
        "display_title": game.display_title,
        "root_path": str(game.root_path),
        "selected_exe": str(game.selected_exe or ""),
        "confidence": game.confidence,
        "candidate_reasons": candidate.reasons if candidate else [],
        "candidate_count": len(game.candidates),
        "artwork_status": game.artwork_status,
        "metadata_status": game.metadata_status,
        "existing_appid": game.existing_appid,
        "existing_match": game.existing_match,
        "launch_options": game.launch_options,
        "metadata": {
            "clean_title": game.metadata.clean_title,
            "release_year": game.metadata.release_year,
            "developer": game.metadata.developer,
            "publisher": game.metadata.publisher,
            "genres": game.metadata.genres,
            "description": game.metadata.description,
            "source": game.metadata.source,
            "sgdb_id": game.metadata.sgdb_id,
            "steam_appid": game.metadata.steam_appid,
            "notes": game.metadata.notes,
        },
    }


def export_json(games: list[DetectedGame], destination: Path) -> None:
    destination.write_text(
        json.dumps([game_to_dict(game) for game in games], indent=2),
        encoding="utf-8",
    )


def export_csv(games: list[DetectedGame], destination: Path) -> None:
    rows = [game_to_dict(game) for game in games]
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "selected",
                "title",
                "display_title",
                "root_path",
                "selected_exe",
                "confidence",
                "artwork_status",
                "metadata_status",
                "existing_appid",
                "existing_match",
                "launch_options",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})
