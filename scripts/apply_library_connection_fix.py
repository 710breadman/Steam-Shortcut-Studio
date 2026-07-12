from __future__ import annotations

from pathlib import Path


path = Path("steam_shortcut_studio/library_store.py")
text = path.read_text(encoding="utf-8")

if "from contextlib import contextmanager" not in text:
    text = text.replace(
        "import json\n",
        "import json\nfrom contextlib import contextmanager\n",
        1,
    )

needle = """        return connection

    def initialize(self) -> None:
"""
replacement = """        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
"""
if needle not in text and "def _connection(self)" not in text:
    raise RuntimeError("Could not locate LibraryStore connection insertion point.")
if "def _connection(self)" not in text:
    text = text.replace(needle, replacement, 1)

text = text.replace(
    "self._connect() as connection",
    "self._connection() as connection",
)
path.write_text(text, encoding="utf-8")

for temporary in (
    Path(".github/workflows/library-store-diagnostic.yml"),
    Path(".github/workflows/apply-library-connection-fix.yml"),
    Path("scripts/apply_library_connection_fix.py"),
):
    if temporary.exists():
        temporary.unlink()
