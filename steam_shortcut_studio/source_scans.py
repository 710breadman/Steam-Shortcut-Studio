from __future__ import annotations

from dataclasses import dataclass

from .library_store import LibraryStore, SnapshotResult
from .sources.base import SourceAdapter, SourceIssue, SourceScanResult


NON_AUTHORITATIVE_ISSUE_CODES = frozenset(
    {
        "programdata_unavailable",
        "manifest_directory_missing",
    }
)


@dataclass(frozen=True, slots=True)
class PersistedSourceScan:
    scan_id: str
    result: SourceScanResult
    status: str
    authoritative: bool
    snapshot: SnapshotResult | None = None
    error: str = ""

    @property
    def persisted(self) -> bool:
        return self.snapshot is not None

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"


def source_scan_is_authoritative(result: SourceScanResult) -> bool:
    """Return whether absence from this result can safely mean not installed.

    A launcher being unavailable or any malformed source record makes the scan
    partial. Partial scans may be displayed to the user, but they must not mark
    previously stored games missing.
    """

    for issue in result.issues:
        if issue.code in NON_AUTHORITATIVE_ISSUE_CODES:
            return False
        if issue.severity.casefold() == "error":
            return False
    return True


class SourceScanCoordinator:
    """Run one read-only source adapter and persist only authoritative snapshots."""

    def __init__(self, store: LibraryStore) -> None:
        self.store = store

    def run(self, adapter: SourceAdapter) -> PersistedSourceScan:
        source_name = str(adapter.source_name or "").strip()
        if not source_name:
            raise ValueError("Source adapters require a source_name.")

        scan_id = self.store.start_scan(source_name)
        try:
            result = adapter.scan()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.store.finish_scan(
                scan_id,
                status="failed",
                error=error,
            )
            result = SourceScanResult(
                source=source_name,
                issues=(
                    SourceIssue(
                        source=source_name,
                        code="adapter_exception",
                        message=error,
                        severity="error",
                    ),
                ),
            )
            return PersistedSourceScan(
                scan_id=scan_id,
                result=result,
                status="failed",
                authoritative=False,
                error=error,
            )

        if result.source.casefold() != source_name.casefold():
            error = (
                f"Adapter source mismatch: expected {source_name!r}, "
                f"received {result.source!r}."
            )
            self.store.finish_scan(
                scan_id,
                status="failed",
                item_count=result.item_count,
                issue_count=result.issue_count,
                error=error,
            )
            return PersistedSourceScan(
                scan_id=scan_id,
                result=result,
                status="failed",
                authoritative=False,
                error=error,
            )

        authoritative = source_scan_is_authoritative(result)
        if not authoritative:
            error = "Source scan was partial; stored presence was left unchanged."
            self.store.finish_scan(
                scan_id,
                status="failed",
                item_count=result.item_count,
                issue_count=result.issue_count,
                error=error,
            )
            return PersistedSourceScan(
                scan_id=scan_id,
                result=result,
                status="failed",
                authoritative=False,
                error=error,
            )

        try:
            snapshot = self.store.replace_source_snapshot(
                source_name,
                result.items,
                scan_id=scan_id,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.store.finish_scan(
                scan_id,
                status="failed",
                item_count=result.item_count,
                issue_count=result.issue_count,
                error=error,
            )
            return PersistedSourceScan(
                scan_id=scan_id,
                result=result,
                status="failed",
                authoritative=True,
                error=error,
            )

        self.store.finish_scan(
            scan_id,
            status="completed",
            item_count=result.item_count,
            issue_count=result.issue_count,
        )
        return PersistedSourceScan(
            scan_id=scan_id,
            result=result,
            status="completed",
            authoritative=True,
            snapshot=snapshot,
        )
