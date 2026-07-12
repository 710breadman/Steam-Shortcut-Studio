from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from . import __app_name__
from .sources.base import SourceLibraryItem


SCHEMA_VERSION = 1
ARTWORK_SLOTS = frozenset({"grid", "wide", "hero", "logo", "icon"})


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat()


def _app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / __app_name__.replace(" ", "")


def default_library_database() -> Path:
    return _app_data_dir() / "library.sqlite3"


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_object(value: str) -> dict[str, object]:
    try:
        decoded = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return dict(decoded) if isinstance(decoded, dict) else {}


def _json_strings(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(str(item) for item in decoded if str(item).strip())


def _nullable_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(int(value))


@dataclass(frozen=True, slots=True)
class LibraryItemRecord:
    stable_id: str
    source: str
    external_id: str
    title: str
    install_path: str
    launch_target: str = ""
    launch_arguments: str = ""
    working_directory: str = ""
    platform: str = ""
    version: str = ""
    size_bytes: int = 0
    source_record_path: str = ""
    launch_target_exists: bool | None = None
    evidence: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    is_present: bool = True
    first_seen_at: str = ""
    last_seen_at: str = ""
    last_scan_id: str = ""


@dataclass(frozen=True, slots=True)
class ManualOverrides:
    item_id: str
    display_title: str | None = None
    launch_target: str | None = None
    launch_arguments: str | None = None
    working_directory: str | None = None
    notes: str | None = None
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class ResolvedLibraryItem:
    record: LibraryItemRecord
    display_title: str
    launch_target: str
    launch_arguments: str
    working_directory: str
    notes: str = ""
    overridden_fields: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ArtworkLock:
    item_id: str
    slot: str
    candidate_id: str = ""
    source: str = ""
    local_path: str = ""
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class RejectedMatch:
    item_id: str
    provider: str
    slot: str
    candidate_id: str
    reason: str = ""
    rejected_at: str = ""


@dataclass(frozen=True, slots=True)
class ScanRun:
    scan_id: str
    source: str
    started_at: str
    finished_at: str = ""
    status: str = "running"
    item_count: int = 0
    issue_count: int = 0
    error: str = ""


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    inserted: int = 0
    updated: int = 0
    marked_missing: int = 0


class LibraryStore:
    """Thread-safe SQLite persistence for normalized library source records.

    Connections are short lived so worker threads never share a sqlite connection.
    Stable source IDs allow rescans to refresh launcher data without discarding
    manual overrides, artwork locks, or rejected candidate decisions.
    """

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = Path(database_path or default_library_database()).expanduser()
        self._write_lock = threading.RLock()
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._write_lock, self._connect() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Library database schema {version} is newer than supported schema "
                    f"{SCHEMA_VERSION}."
                )
            if version == 0:
                self._create_schema(connection)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif version < SCHEMA_VERSION:
                self._migrate(connection, version)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE library_items (
                stable_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                install_path TEXT NOT NULL DEFAULT '',
                launch_target TEXT NOT NULL DEFAULT '',
                launch_arguments TEXT NOT NULL DEFAULT '',
                working_directory TEXT NOT NULL DEFAULT '',
                platform TEXT NOT NULL DEFAULT '',
                version TEXT NOT NULL DEFAULT '',
                size_bytes INTEGER NOT NULL DEFAULT 0 CHECK(size_bytes >= 0),
                source_record_path TEXT NOT NULL DEFAULT '',
                launch_target_exists INTEGER NULL,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                is_present INTEGER NOT NULL DEFAULT 1 CHECK(is_present IN (0, 1)),
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_scan_id TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX idx_library_items_source_present
                ON library_items(source, is_present);
            CREATE INDEX idx_library_items_external
                ON library_items(source, external_id);

            CREATE TABLE manual_overrides (
                item_id TEXT PRIMARY KEY REFERENCES library_items(stable_id) ON DELETE CASCADE,
                display_title TEXT NULL,
                launch_target TEXT NULL,
                launch_arguments TEXT NULL,
                working_directory TEXT NULL,
                notes TEXT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE artwork_locks (
                item_id TEXT NOT NULL REFERENCES library_items(stable_id) ON DELETE CASCADE,
                slot TEXT NOT NULL,
                candidate_id TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                local_path TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(item_id, slot)
            );

            CREATE TABLE rejected_matches (
                item_id TEXT NOT NULL REFERENCES library_items(stable_id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                slot TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                rejected_at TEXT NOT NULL,
                PRIMARY KEY(item_id, provider, slot, candidate_id)
            );

            CREATE TABLE scan_runs (
                scan_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'running',
                item_count INTEGER NOT NULL DEFAULT 0,
                issue_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX idx_scan_runs_source_started
                ON scan_runs(source, started_at DESC);
            """
        )

    @staticmethod
    def _migrate(connection: sqlite3.Connection, current_version: int) -> None:
        raise RuntimeError(
            f"No migration is defined from library schema {current_version} to "
            f"{SCHEMA_VERSION}."
        )

    def start_scan(self, source: str) -> str:
        source_name = str(source or "").strip()
        if not source_name:
            raise ValueError("Scan source is required.")
        scan_id = uuid4().hex
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scan_runs(scan_id, source, started_at, status)
                VALUES (?, ?, ?, 'running')
                """,
                (scan_id, source_name, _utc_now_text()),
            )
        return scan_id

    def finish_scan(
        self,
        scan_id: str,
        *,
        status: str = "completed",
        item_count: int = 0,
        issue_count: int = 0,
        error: str = "",
    ) -> None:
        final_status = str(status or "").strip()
        if final_status not in {"completed", "failed", "cancelled"}:
            raise ValueError(f"Unsupported scan status: {final_status}")
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE scan_runs
                SET finished_at = ?, status = ?, item_count = ?, issue_count = ?, error = ?
                WHERE scan_id = ?
                """,
                (
                    _utc_now_text(),
                    final_status,
                    max(0, int(item_count)),
                    max(0, int(issue_count)),
                    str(error or ""),
                    scan_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown scan ID: {scan_id}")

    def replace_source_snapshot(
        self,
        source: str,
        items: Iterable[SourceLibraryItem],
        *,
        scan_id: str = "",
    ) -> SnapshotResult:
        source_name = str(source or "").strip()
        if not source_name:
            raise ValueError("Snapshot source is required.")
        incoming = list(items)
        for item in incoming:
            if item.source.casefold() != source_name.casefold():
                raise ValueError(
                    f"Source item {item.stable_id} belongs to {item.source}, not {source_name}."
                )

        now = _utc_now_text()
        inserted = 0
        updated = 0
        seen_ids: list[str] = []

        with self._write_lock, self._connect() as connection:
            for item in incoming:
                exists = connection.execute(
                    "SELECT 1 FROM library_items WHERE stable_id = ?",
                    (item.stable_id,),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO library_items(
                        stable_id, source, external_id, title, install_path,
                        launch_target, launch_arguments, working_directory, platform,
                        version, size_bytes, source_record_path, launch_target_exists,
                        evidence_json, metadata_json, is_present, first_seen_at,
                        last_seen_at, last_scan_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    ON CONFLICT(stable_id) DO UPDATE SET
                        source = excluded.source,
                        external_id = excluded.external_id,
                        title = excluded.title,
                        install_path = excluded.install_path,
                        launch_target = excluded.launch_target,
                        launch_arguments = excluded.launch_arguments,
                        working_directory = excluded.working_directory,
                        platform = excluded.platform,
                        version = excluded.version,
                        size_bytes = excluded.size_bytes,
                        source_record_path = excluded.source_record_path,
                        launch_target_exists = excluded.launch_target_exists,
                        evidence_json = excluded.evidence_json,
                        metadata_json = excluded.metadata_json,
                        is_present = 1,
                        last_seen_at = excluded.last_seen_at,
                        last_scan_id = excluded.last_scan_id
                    """,
                    (
                        item.stable_id,
                        source_name,
                        item.external_id,
                        item.title,
                        item.install_path,
                        item.launch_target,
                        item.launch_arguments,
                        item.working_directory,
                        item.platform,
                        item.version,
                        max(0, int(item.size_bytes)),
                        item.source_record_path,
                        None if item.launch_target_exists is None else int(item.launch_target_exists),
                        _json_dump(list(item.evidence)),
                        _json_dump(dict(item.metadata)),
                        now,
                        now,
                        scan_id,
                    ),
                )
                seen_ids.append(item.stable_id)
                if exists:
                    updated += 1
                else:
                    inserted += 1

            if seen_ids:
                placeholders = ",".join("?" for _ in seen_ids)
                cursor = connection.execute(
                    f"""
                    UPDATE library_items
                    SET is_present = 0, last_scan_id = ?
                    WHERE source = ? AND is_present = 1
                      AND stable_id NOT IN ({placeholders})
                    """,
                    (scan_id, source_name, *seen_ids),
                )
            else:
                cursor = connection.execute(
                    """
                    UPDATE library_items
                    SET is_present = 0, last_scan_id = ?
                    WHERE source = ? AND is_present = 1
                    """,
                    (scan_id, source_name),
                )
            marked_missing = max(0, int(cursor.rowcount))

        return SnapshotResult(inserted, updated, marked_missing)

    def get_record(self, item_id: str) -> LibraryItemRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM library_items WHERE stable_id = ?",
                (item_id,),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def list_records(
        self,
        *,
        source: str | None = None,
        include_missing: bool = False,
    ) -> list[LibraryItemRecord]:
        clauses: list[str] = []
        parameters: list[object] = []
        if source is not None:
            clauses.append("source = ?")
            parameters.append(source)
        if not include_missing:
            clauses.append("is_present = 1")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM library_items"
                + where
                + " ORDER BY title COLLATE NOCASE, stable_id",
                parameters,
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> LibraryItemRecord:
        return LibraryItemRecord(
            stable_id=str(row["stable_id"]),
            source=str(row["source"]),
            external_id=str(row["external_id"]),
            title=str(row["title"]),
            install_path=str(row["install_path"]),
            launch_target=str(row["launch_target"]),
            launch_arguments=str(row["launch_arguments"]),
            working_directory=str(row["working_directory"]),
            platform=str(row["platform"]),
            version=str(row["version"]),
            size_bytes=int(row["size_bytes"]),
            source_record_path=str(row["source_record_path"]),
            launch_target_exists=_nullable_bool(row["launch_target_exists"]),
            evidence=_json_strings(str(row["evidence_json"])),
            metadata=_json_object(str(row["metadata_json"])),
            is_present=bool(row["is_present"]),
            first_seen_at=str(row["first_seen_at"]),
            last_seen_at=str(row["last_seen_at"]),
            last_scan_id=str(row["last_scan_id"]),
        )

    def save_overrides(self, overrides: ManualOverrides) -> ManualOverrides:
        self._require_item(overrides.item_id)
        updated_at = overrides.updated_at or _utc_now_text()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO manual_overrides(
                    item_id, display_title, launch_target, launch_arguments,
                    working_directory, notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    display_title = excluded.display_title,
                    launch_target = excluded.launch_target,
                    launch_arguments = excluded.launch_arguments,
                    working_directory = excluded.working_directory,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    overrides.item_id,
                    overrides.display_title,
                    overrides.launch_target,
                    overrides.launch_arguments,
                    overrides.working_directory,
                    overrides.notes,
                    updated_at,
                ),
            )
        return ManualOverrides(
            item_id=overrides.item_id,
            display_title=overrides.display_title,
            launch_target=overrides.launch_target,
            launch_arguments=overrides.launch_arguments,
            working_directory=overrides.working_directory,
            notes=overrides.notes,
            updated_at=updated_at,
        )

    def get_overrides(self, item_id: str) -> ManualOverrides | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM manual_overrides WHERE item_id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return ManualOverrides(
            item_id=str(row["item_id"]),
            display_title=row["display_title"],
            launch_target=row["launch_target"],
            launch_arguments=row["launch_arguments"],
            working_directory=row["working_directory"],
            notes=row["notes"],
            updated_at=str(row["updated_at"]),
        )

    def clear_overrides(self, item_id: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM manual_overrides WHERE item_id = ?",
                (item_id,),
            )
        return cursor.rowcount > 0

    def resolve_item(self, item_id: str) -> ResolvedLibraryItem | None:
        record = self.get_record(item_id)
        if record is None:
            return None
        overrides = self.get_overrides(item_id)
        if overrides is None:
            return ResolvedLibraryItem(
                record=record,
                display_title=record.title,
                launch_target=record.launch_target,
                launch_arguments=record.launch_arguments,
                working_directory=record.working_directory,
            )

        overridden: set[str] = set()

        def choose(field_name: str, override: str | None, original: str) -> str:
            if override is None:
                return original
            overridden.add(field_name)
            return override

        return ResolvedLibraryItem(
            record=record,
            display_title=choose("display_title", overrides.display_title, record.title),
            launch_target=choose("launch_target", overrides.launch_target, record.launch_target),
            launch_arguments=choose(
                "launch_arguments", overrides.launch_arguments, record.launch_arguments
            ),
            working_directory=choose(
                "working_directory", overrides.working_directory, record.working_directory
            ),
            notes=choose("notes", overrides.notes, ""),
            overridden_fields=frozenset(overridden),
        )

    def set_artwork_lock(self, lock: ArtworkLock) -> ArtworkLock:
        if lock.slot not in ARTWORK_SLOTS:
            raise ValueError(f"Unknown artwork slot: {lock.slot}")
        self._require_item(lock.item_id)
        updated_at = lock.updated_at or _utc_now_text()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artwork_locks(
                    item_id, slot, candidate_id, source, local_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id, slot) DO UPDATE SET
                    candidate_id = excluded.candidate_id,
                    source = excluded.source,
                    local_path = excluded.local_path,
                    updated_at = excluded.updated_at
                """,
                (
                    lock.item_id,
                    lock.slot,
                    lock.candidate_id,
                    lock.source,
                    lock.local_path,
                    updated_at,
                ),
            )
        return ArtworkLock(
            item_id=lock.item_id,
            slot=lock.slot,
            candidate_id=lock.candidate_id,
            source=lock.source,
            local_path=lock.local_path,
            updated_at=updated_at,
        )

    def clear_artwork_lock(self, item_id: str, slot: str) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM artwork_locks WHERE item_id = ? AND slot = ?",
                (item_id, slot),
            )
        return cursor.rowcount > 0

    def list_artwork_locks(self, item_id: str) -> list[ArtworkLock]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artwork_locks
                WHERE item_id = ?
                ORDER BY slot
                """,
                (item_id,),
            ).fetchall()
        return [
            ArtworkLock(
                item_id=str(row["item_id"]),
                slot=str(row["slot"]),
                candidate_id=str(row["candidate_id"]),
                source=str(row["source"]),
                local_path=str(row["local_path"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]

    def reject_match(self, rejection: RejectedMatch) -> RejectedMatch:
        if rejection.slot not in ARTWORK_SLOTS:
            raise ValueError(f"Unknown artwork slot: {rejection.slot}")
        self._require_item(rejection.item_id)
        rejected_at = rejection.rejected_at or _utc_now_text()
        with self._write_lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rejected_matches(
                    item_id, provider, slot, candidate_id, reason, rejected_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id, provider, slot, candidate_id) DO UPDATE SET
                    reason = excluded.reason,
                    rejected_at = excluded.rejected_at
                """,
                (
                    rejection.item_id,
                    rejection.provider,
                    rejection.slot,
                    rejection.candidate_id,
                    rejection.reason,
                    rejected_at,
                ),
            )
        return RejectedMatch(
            item_id=rejection.item_id,
            provider=rejection.provider,
            slot=rejection.slot,
            candidate_id=rejection.candidate_id,
            reason=rejection.reason,
            rejected_at=rejected_at,
        )

    def is_match_rejected(
        self,
        item_id: str,
        provider: str,
        slot: str,
        candidate_id: str,
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM rejected_matches
                WHERE item_id = ? AND provider = ? AND slot = ? AND candidate_id = ?
                """,
                (item_id, provider, slot, candidate_id),
            ).fetchone()
        return row is not None

    def list_rejected_matches(self, item_id: str) -> list[RejectedMatch]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM rejected_matches
                WHERE item_id = ?
                ORDER BY rejected_at DESC, provider, slot, candidate_id
                """,
                (item_id,),
            ).fetchall()
        return [
            RejectedMatch(
                item_id=str(row["item_id"]),
                provider=str(row["provider"]),
                slot=str(row["slot"]),
                candidate_id=str(row["candidate_id"]),
                reason=str(row["reason"]),
                rejected_at=str(row["rejected_at"]),
            )
            for row in rows
        ]

    def clear_rejected_match(
        self,
        item_id: str,
        provider: str,
        slot: str,
        candidate_id: str,
    ) -> bool:
        with self._write_lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM rejected_matches
                WHERE item_id = ? AND provider = ? AND slot = ? AND candidate_id = ?
                """,
                (item_id, provider, slot, candidate_id),
            )
        return cursor.rowcount > 0

    def list_scan_runs(self, *, source: str | None = None, limit: int = 50) -> list[ScanRun]:
        parameters: list[object] = []
        where = ""
        if source is not None:
            where = " WHERE source = ?"
            parameters.append(source)
        parameters.append(max(1, int(limit)))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM scan_runs
                """
                + where
                + " ORDER BY started_at DESC, scan_id DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [
            ScanRun(
                scan_id=str(row["scan_id"]),
                source=str(row["source"]),
                started_at=str(row["started_at"]),
                finished_at=str(row["finished_at"]),
                status=str(row["status"]),
                item_count=int(row["item_count"]),
                issue_count=int(row["issue_count"]),
                error=str(row["error"]),
            )
            for row in rows
        ]

    def _require_item(self, item_id: str) -> None:
        if self.get_record(item_id) is None:
            raise KeyError(f"Unknown library item: {item_id}")
