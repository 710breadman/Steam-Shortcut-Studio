from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from steam_shortcut_studio.artwork_transactions import (  # noqa: E402
    ArtworkTransactionVerificationError,
    ArtworkWriteRequest,
    apply_artwork_set_transaction,
)
from steam_shortcut_studio.file_transactions import sha256_path  # noqa: E402
from steam_shortcut_studio.image_validation import ArtworkValidationError  # noqa: E402


def _image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (96, 64)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def test_complete_artwork_set_commits_writes_and_stale_removals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transaction_root = root / "transactions"
        grid_dir = root / "grid"
        source_grid = _image(root / "sources" / "grid.png", (10, 20, 30), (600, 900))
        source_hero = _image(root / "sources" / "hero.png", (40, 50, 60), (1920, 620))
        target_grid = _image(grid_dir / "424242p.png", (100, 0, 0), (600, 900))
        target_hero = _image(grid_dir / "424242_hero.png", (0, 100, 0), (1920, 620))
        stale_grid = _image(grid_dir / "424242p.jpg", (0, 0, 100), (600, 900))

        outcome = apply_artwork_set_transaction(
            [
                ArtworkWriteRequest(source_grid, target_grid, slot="grid"),
                ArtworkWriteRequest(source_hero, target_hero, slot="hero"),
            ],
            remove_paths=[stale_grid],
            transaction_root=transaction_root,
            transaction_id="success",
        )

        assert outcome.status == "committed"
        assert sha256_path(target_grid) == sha256_path(source_grid)
        assert sha256_path(target_hero) == sha256_path(source_hero)
        assert not stale_grid.exists()
        assert len(outcome.operations) == 3
        assert all(operation.status == "committed" for operation in outcome.operations)
        manifest = json.loads(Path(outcome.manifest_path).read_text(encoding="utf-8"))
        assert manifest["status"] == "committed"
        assert [operation["action"] for operation in manifest["operations"]] == [
            "write",
            "write",
            "remove",
        ]
        assert all(
            operation["backup_path"]
            for operation in manifest["operations"]
        )


def test_invalid_source_aborts_before_any_target_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transaction_root = root / "transactions"
        target = _image(root / "grid" / "424242p.png", (10, 10, 10), (600, 900))
        original_hash = sha256_path(target)
        invalid = root / "sources" / "bad.png"
        invalid.parent.mkdir(parents=True)
        invalid.write_text("<html>not an image</html>", encoding="utf-8")

        try:
            apply_artwork_set_transaction(
                [ArtworkWriteRequest(invalid, target, slot="grid")],
                transaction_root=transaction_root,
            )
        except ArtworkValidationError:
            pass
        else:
            raise AssertionError("Invalid artwork was accepted")

        assert sha256_path(target) == original_hash
        assert not transaction_root.exists()


def test_failure_after_first_write_restores_entire_previous_set() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        transaction_root = root / "transactions"
        grid_dir = root / "grid"
        source_grid = _image(root / "sources" / "grid.png", (10, 20, 30), (600, 900))
        source_hero = _image(root / "sources" / "hero.png", (40, 50, 60), (1920, 620))
        target_grid = _image(grid_dir / "424242p.png", (100, 0, 0), (600, 900))
        target_hero = _image(grid_dir / "424242_hero.png", (0, 100, 0), (1920, 620))
        stale = _image(grid_dir / "424242p.jpg", (0, 0, 100), (600, 900))
        original_hashes = {
            target_grid: sha256_path(target_grid),
            target_hero: sha256_path(target_hero),
            stale: sha256_path(stale),
        }

        def fail_after_first(index, operation):
            if index == 0:
                raise RuntimeError("injected artwork failure")

        try:
            apply_artwork_set_transaction(
                [
                    ArtworkWriteRequest(source_grid, target_grid, slot="grid"),
                    ArtworkWriteRequest(source_hero, target_hero, slot="hero"),
                ],
                remove_paths=[stale],
                transaction_root=transaction_root,
                transaction_id="rollback-existing",
                written_hook=fail_after_first,
            )
        except ArtworkTransactionVerificationError as exc:
            outcome = exc.outcome
        else:
            raise AssertionError("Injected artwork failure did not fail")

        assert outcome.status == "rolled_back"
        assert outcome.restored is True
        assert outcome.restore_verified is True
        assert all(path.exists() for path in original_hashes)
        assert {path: sha256_path(path) for path in original_hashes} == original_hashes
        manifest = json.loads(Path(outcome.manifest_path).read_text(encoding="utf-8"))
        assert manifest["status"] == "rolled_back"
        assert all(operation["restore_verified"] for operation in manifest["operations"])


def test_failure_removes_every_newly_created_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source_grid = _image(root / "sources" / "grid.png", (10, 20, 30), (600, 900))
        source_logo = _image(root / "sources" / "logo.png", (40, 50, 60), (512, 256))
        target_grid = root / "grid" / "424242p.png"
        target_logo = root / "grid" / "424242_logo.png"

        def fail_after_second(index, operation):
            if index == 1:
                raise RuntimeError("injected second write failure")

        try:
            apply_artwork_set_transaction(
                [
                    ArtworkWriteRequest(source_grid, target_grid, slot="grid"),
                    ArtworkWriteRequest(source_logo, target_logo, slot="logo"),
                ],
                transaction_root=root / "transactions",
                transaction_id="rollback-new",
                written_hook=fail_after_second,
            )
        except ArtworkTransactionVerificationError as exc:
            outcome = exc.outcome
        else:
            raise AssertionError("Injected artwork failure did not fail")

        assert outcome.status == "rolled_back"
        assert outcome.restore_verified is True
        assert not target_grid.exists()
        assert not target_logo.exists()
        assert all(not operation.original_exists for operation in outcome.operations)


def test_remove_only_transaction_is_reversible_on_later_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _image(root / "grid" / "424242p.jpg", (1, 2, 3), (600, 900))
        second = _image(root / "grid" / "424242_hero.jpg", (4, 5, 6), (1920, 620))
        original = {first: sha256_path(first), second: sha256_path(second)}

        def fail_after_first(index, operation):
            if index == 0:
                raise RuntimeError("injected removal failure")

        try:
            apply_artwork_set_transaction(
                [],
                remove_paths=(path for path in (first, second)),
                transaction_root=root / "transactions",
                transaction_id="remove-only",
                written_hook=fail_after_first,
            )
        except ArtworkTransactionVerificationError as exc:
            outcome = exc.outcome
        else:
            raise AssertionError("Injected removal failure did not fail")

        assert outcome.status == "rolled_back"
        assert {path: sha256_path(path) for path in original} == original


def test_duplicate_or_conflicting_targets_are_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = _image(root / "source.png", (1, 2, 3))
        target = root / "grid" / "same.png"

        for writes, removals in (
            (
                [
                    ArtworkWriteRequest(source, target),
                    ArtworkWriteRequest(source, target),
                ],
                [],
            ),
            ([ArtworkWriteRequest(source, target)], [target]),
        ):
            try:
                apply_artwork_set_transaction(
                    writes,
                    remove_paths=removals,
                    transaction_root=root / "transactions",
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Conflicting artwork targets were accepted")


if __name__ == "__main__":
    test_complete_artwork_set_commits_writes_and_stale_removals()
    test_invalid_source_aborts_before_any_target_changes()
    test_failure_after_first_write_restores_entire_previous_set()
    test_failure_removes_every_newly_created_target()
    test_remove_only_transaction_is_reversible_on_later_failure()
    test_duplicate_or_conflicting_targets_are_rejected()
    print("Artwork transaction tests passed.")
