from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol
from uuid import NAMESPACE_URL, uuid5


@dataclass(frozen=True, slots=True)
class SourceIssue:
    source: str
    code: str
    message: str
    record_path: str = ""
    item_external_id: str = ""
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class SourceLibraryItem:
    stable_id: str
    source: str
    external_id: str
    title: str
    install_path: str
    launch_target: str = ""
    launch_arguments: str = ""
    working_directory: str = ""
    platform: str = "windows"
    version: str = ""
    size_bytes: int = 0
    source_record_path: str = ""
    launch_target_exists: bool | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.stable_id.strip():
            raise ValueError("Source library items require a stable ID.")
        if not self.source.strip():
            raise ValueError("Source library items require a source.")
        if not self.title.strip():
            raise ValueError("Source library items require a title.")


@dataclass(frozen=True, slots=True)
class SourceScanResult:
    source: str
    items: tuple[SourceLibraryItem, ...] = ()
    issues: tuple[SourceIssue, ...] = ()

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def issue_count(self) -> int:
        return len(self.issues)


class SourceAdapter(Protocol):
    source_name: str

    def scan(self) -> SourceScanResult: ...


def _identity_text(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    return text.replace("\\", "/").casefold()


def stable_source_item_id(
    source: str,
    *,
    external_id: str = "",
    install_path: str = "",
    title: str = "",
) -> str:
    """Return a deterministic ID without depending on mutable display order."""

    source_key = _identity_text(source)
    external_key = _identity_text(external_id)
    if external_key:
        identity = f"source:{source_key}:external:{external_key}"
    else:
        install_key = _identity_text(install_path)
        title_key = _identity_text(title)
        if not install_key and not title_key:
            raise ValueError("Stable source IDs require an external ID, path, or title.")
        identity = f"source:{source_key}:path:{install_key}:title:{title_key}"
    return str(uuid5(NAMESPACE_URL, identity))
