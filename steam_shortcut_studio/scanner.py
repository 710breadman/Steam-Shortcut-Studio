from __future__ import annotations

import logging
import math
import os
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from .exe_metadata import read_pe_summary, read_version_info
from .models import DetectedGame, ExecutableCandidate

LOGGER = logging.getLogger(__name__)


BAD_NAME_PARTS = {
    "uninstall",
    "unins",
    "setup",
    "install",
    "launcher_helper",
    "crash",
    "crashreport",
    "redist",
    "vc_redist",
    "vcredist",
    "directx",
    "dxsetup",
    "dotnet",
    "unitycrashhandler",
    "unrealcefsubprocess",
    "helper",
    "updater",
    "update",
    "repair",
    "benchmark",
    "config",
    "settings",
    "editor",
    "server",
    "steamerrorreporter",
}

BAD_PATH_PARTS = {
    "_commonredist",
    "redist",
    "redistributable",
    "directx",
    "dotnet",
    "support",
    "tools",
    "tool",
    "installer",
    "__installer",
    "prereq",
    "prereqs",
    "crashreporter",
    "binaries/thirdparty",
    "crashpad",
}

GOOD_PATH_PARTS = {
    "bin",
    "binaries",
    "win64",
    "win32",
    "x64",
    "x86",
    "release",
    "shipping",
    "game",
    "client",
    "linux",
    "linux64",
    "x86_64",
}

LAUNCH_CANDIDATE_PATTERNS = ("*.exe",)
NATIVE_LINUX_PATTERNS = (
    "*.sh",
    "*.AppImage",
    "*.appimage",
    "*.x86_64",
    "*.x86",
    "*.bin",
    "*.run",
)
NATIVE_LINUX_SUFFIXES = {".sh", ".appimage", ".x86_64", ".x86", ".bin", ".run"}


def native_launch_candidates_enabled() -> bool:
    return os.name != "nt"


def is_native_linux_launch_candidate(path: Path) -> bool:
    suffix = path.suffix.casefold()
    if suffix in NATIVE_LINUX_SUFFIXES:
        return True
    return not suffix and os.access(path, os.X_OK)


def is_launch_candidate(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.casefold() == ".exe":
        return True
    return native_launch_candidates_enabled() and is_native_linux_launch_candidate(path)


def canonical_gta_title(text: str) -> str:
    raw = text.strip()
    lowered = raw.casefold()
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    has_gta = bool(re.search(r"\bgta\b", lowered)) or compact.startswith("gta") or "grandtheftauto" in compact
    if not has_gta:
        return ""
    if "trilogy" in lowered or "trilogy" in compact:
        if "definitive" in lowered or re.search(r"\bde\b", lowered) or "delauncher" in compact:
            return "Grand Theft Auto: The Trilogy - The Definitive Edition"
        return "Grand Theft Auto: The Trilogy"
    variants = [
        ({"v", "5"}, "Grand Theft Auto V"),
        ({"iv", "4"}, "Grand Theft Auto IV"),
        ({"iii", "3"}, "Grand Theft Auto III"),
        ({"sa", "sanandreas"}, "Grand Theft Auto: San Andreas"),
        ({"vc", "vicecity"}, "Grand Theft Auto: Vice City"),
    ]
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    for aliases, title in variants:
        if aliases.intersection(tokens) or any(f"gta{alias}" in compact for alias in aliases):
            return title
    return re.sub(r"\bgta\b", "Grand Theft Auto", raw, flags=re.I)


def strip_launcher_suffixes(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r"(?i)\b(del|de|definitive edition)?\s*launcher$", "", cleaned).strip()
    cleaned = re.sub(r"(?i)\b(win64|win32|x64|x86|shipping|client|game|launcher)$", "", cleaned).strip()
    return cleaned or text


def normalize_title(text: str) -> str:
    text = canonical_gta_title(text) or text
    text = re.sub(r"\[[^\]]+\]|\([^\)]+\)", " ", text)
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"\bgta\b", "grand theft auto", text, flags=re.I)
    text = re.sub(r"\b(the|a|an|game|edition|definitive|ultimate|deluxe|goty)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def clean_display_title(text: str) -> str:
    gta_title = canonical_gta_title(text)
    if gta_title:
        return gta_title
    text = strip_launcher_suffixes(text)
    text = re.sub(r"\s*[-–—:]+\s*", " ", text)
    text = re.sub(r"\s+", " ", text.replace("_", " ").replace(".", " ")).strip()
    return text


def similarity(a: str, b: str) -> float:
    na = normalize_title(a)
    nb = normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    tokens_a = set(na.split())
    tokens_b = set(nb.split())
    seq = SequenceMatcher(None, na, nb).ratio()
    if not tokens_a or not tokens_b:
        return seq
    common = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    jaccard = common / union if union else 0.0
    coverage = common / max(len(tokens_a), len(tokens_b))
    token_score = (jaccard * 0.55) + (coverage * 0.45)
    if na in nb or nb in na:
        return min(0.78, max(seq, token_score))
    return max(seq, token_score)


def important_title_tokens(text: str) -> set[str]:
    return {
        token
        for token in normalize_title(text).split()
        if token not in {"the", "and", "of", "for", "with", "edition", "definitive", "remastered", "remaster"}
    }


def is_specific_title_match(query: str, candidate: str, minimum_similarity: float = 0.52) -> bool:
    if similarity(query, candidate) < minimum_similarity:
        return False
    query_tokens = important_title_tokens(query)
    candidate_tokens = important_title_tokens(candidate)
    if len(query_tokens) >= 3:
        missing = query_tokens - candidate_tokens
        if missing:
            return False
    return True


def should_accept_matched_title(original_title: str, current_title: str, candidate_title: str) -> bool:
    candidate_title = clean_display_title(candidate_title)
    if not candidate_title:
        return False
    if current_title and current_title != original_title:
        return False
    if candidate_title.casefold() == original_title.casefold():
        return True
    if len(candidate_title) < 5 and len(original_title) > len(candidate_title) + 2:
        return False
    return is_specific_title_match(original_title, candidate_title, minimum_similarity=0.62)


def executable_title_tokens(stem: str) -> set[str]:
    cleaned = strip_launcher_suffixes(stem)
    cleaned = re.sub(
        r"(?i)\b(win64|win32|linux64|linux|x64|x86|x86_64|shipping|client|launcher|bootstrap|binary|binaries|appimage)\b",
        " ",
        cleaned,
    )
    return important_title_tokens(cleaned)


class GameScanner:
    def __init__(
        self,
        logger: logging.Logger | None = None,
        max_version_checks_per_game: int = 8,
        cancel_check: Callable[[], None] | None = None,
        progress_callback: Callable[[str], None] | None = None,
        game_callback: Callable[[DetectedGame], None] | None = None,
    ) -> None:
        self.logger = logger or LOGGER
        self.max_version_checks_per_game = max_version_checks_per_game
        self.cancel_check = cancel_check
        self.progress_callback = progress_callback
        self.game_callback = game_callback

    def _cancel_if_requested(self) -> None:
        if self.cancel_check:
            self.cancel_check()

    def _progress(self, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(message)

    def _game_found(self, game: DetectedGame) -> None:
        if self.game_callback:
            self.game_callback(game)

    def iter_launch_candidates(self, collection_root: Path) -> list[Path]:
        patterns = list(LAUNCH_CANDIDATE_PATTERNS)
        if native_launch_candidates_enabled():
            patterns.extend(NATIVE_LINUX_PATTERNS)

        seen: set[Path] = set()
        candidates: list[Path] = []
        for pattern in patterns:
            for path in collection_root.rglob(pattern):
                if path in seen or not is_launch_candidate(path):
                    continue
                seen.add(path)
                candidates.append(path)

        if native_launch_candidates_enabled():
            for path in collection_root.rglob("*"):
                if path in seen or path.suffix or not is_launch_candidate(path):
                    continue
                seen.add(path)
                candidates.append(path)
        candidates.sort(key=lambda item: str(item).casefold())
        return candidates

    def scan(self, collection_root: Path) -> list[DetectedGame]:
        collection_root = collection_root.expanduser().resolve()
        if not collection_root.exists() or not collection_root.is_dir():
            raise ValueError(f"Game collection folder does not exist: {collection_root}")

        self.logger.info("Scanning %s for launch candidates...", collection_root)
        grouped: dict[Path, list[Path]] = defaultdict(list)
        root_candidates: list[Path] = []
        scanned_count = 0
        for exe_path in self.iter_launch_candidates(collection_root):
            scanned_count += 1
            if scanned_count % 25 == 0:
                self._cancel_if_requested()
                self._progress(f"Found {scanned_count} launch candidate(s) so far...")
            if not exe_path.is_file():
                continue
            try:
                rel = exe_path.relative_to(collection_root)
            except ValueError:
                continue
            parts = rel.parts
            if len(parts) == 1:
                root_candidates.append(exe_path)
                continue
            grouped[collection_root / parts[0]].append(exe_path)

        games: list[DetectedGame] = []
        for game_root in sorted(grouped, key=lambda item: item.name.lower()):
            self._cancel_if_requested()
            source_title = game_root.name
            title = clean_display_title(source_title)
            self._progress(f"Ranking candidates for {title}...")
            candidates = self.rank_candidates(title, game_root, grouped[game_root])
            selected = candidates[0].path if candidates else None
            game = DetectedGame(
                title=title,
                root_path=game_root,
                source_title=source_title,
                candidates=candidates,
                selected_exe=selected,
                selected=False,
            )
            games.append(game)
            self._game_found(game)
        for exe_path in sorted(root_candidates, key=lambda item: item.name.lower()):
            self._cancel_if_requested()
            source_title = exe_path.stem
            title = clean_display_title(source_title)
            self._progress(f"Ranking candidates for {title}...")
            candidates = self.rank_candidates(title, exe_path.parent, [exe_path])
            selected = candidates[0].path if candidates else exe_path
            game = DetectedGame(
                title=title,
                root_path=exe_path.parent,
                source_title=source_title,
                candidates=candidates,
                selected_exe=selected,
                selected=False,
            )
            games.append(game)
            self._game_found(game)
        self.logger.info("Scan complete: %s game folders with launch candidates.", len(games))
        return games

    def rank_candidates(self, title: str, game_root: Path, exe_paths: list[Path]) -> list[ExecutableCandidate]:
        self._cancel_if_requested()
        candidates = [self.score_candidate(title, game_root, exe_path, include_version_info=False) for exe_path in exe_paths]
        self.rebalance_candidate_scores(title, game_root, candidates)
        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        if self.max_version_checks_per_game > 0:
            rescored: dict[Path, ExecutableCandidate] = {}
            for candidate in candidates[: self.max_version_checks_per_game]:
                self._cancel_if_requested()
                rescored[candidate.path] = self.score_candidate(
                    title,
                    game_root,
                    candidate.path,
                    include_version_info=True,
                )
            candidates = [rescored.get(candidate.path, candidate) for candidate in candidates]
        self.rebalance_candidate_scores(title, game_root, candidates)
        candidates.sort(key=lambda candidate: candidate.score, reverse=True)
        return candidates

    def rebalance_candidate_scores(self, title: str, game_root: Path, candidates: list[ExecutableCandidate]) -> None:
        title_tokens = important_title_tokens(title)
        if not title_tokens or len(candidates) < 2:
            return
        candidate_tokens = {candidate.path: executable_title_tokens(candidate.path.stem) for candidate in candidates}
        has_near_root_title_match = any(
            candidate.depth <= 1
            and candidate_tokens[candidate.path] & title_tokens
            and not any(part in candidate.path.stem.casefold() for part in BAD_NAME_PARTS)
            for candidate in candidates
        )
        for candidate in candidates:
            tokens = candidate_tokens[candidate.path]
            overlap = tokens & title_tokens
            stem_lower = candidate.path.stem.casefold()
            try:
                rel_lower = "/".join(part.casefold() for part in candidate.path.relative_to(game_root).parts)
            except ValueError:
                rel_lower = candidate.path.name.casefold()
            if overlap and candidate.depth <= 1:
                bonus = 18 + min(12, len(overlap) * 6)
                candidate.score += bonus
                candidate.reasons.append(f"Bonus for near-root executable name matching title token(s): {', '.join(sorted(overlap))}.")
            if has_near_root_title_match and not overlap and candidate.depth >= 3 and ("shipping" in stem_lower or "binaries/win64" in rel_lower):
                candidate.score -= 45
                candidate.reasons.append("Penalized because this deep shipping binary uses a project codename while a near-root title-matching executable exists.")
            candidate.confidence = max(0, min(100, round(candidate.score)))

    def score_candidate(
        self,
        title: str,
        game_root: Path,
        exe_path: Path,
        include_version_info: bool = True,
    ) -> ExecutableCandidate:
        reasons: list[str] = []
        score = 20.0
        try:
            rel = exe_path.relative_to(game_root)
            depth = max(0, len(rel.parts) - 1)
            rel_lower = "/".join(part.lower() for part in rel.parts)
        except ValueError:
            depth = 99
            rel_lower = exe_path.name.lower()

        stem = exe_path.stem
        stem_lower = stem.lower()
        suffix = exe_path.suffix.casefold()
        native_linux_candidate = native_launch_candidates_enabled() and is_native_linux_launch_candidate(exe_path)
        version_info: dict[str, str] = {}
        size = 0
        try:
            size = exe_path.stat().st_size
        except OSError:
            reasons.append("Could not read file size.")

        if native_linux_candidate:
            score += 20
            if suffix == ".sh":
                reasons.append("Native Linux launch script candidate.")
            elif suffix == ".appimage":
                reasons.append("Native Linux AppImage candidate.")
            elif not suffix:
                reasons.append("Executable Linux launch file candidate.")
            else:
                reasons.append("Native Linux launch binary candidate.")

        bad_hits = sorted(part for part in BAD_NAME_PARTS if part in stem_lower)
        if bad_hits:
            penalty = 80 + 30 * len(bad_hits)
            score -= penalty
            reasons.append(f"Penalized for installer/helper keywords: {', '.join(bad_hits)}.")

        path_hits = sorted(part for part in BAD_PATH_PARTS if part in rel_lower)
        if path_hits:
            score -= 65
            reasons.append(f"Penalized for support/redist path: {', '.join(path_hits)}.")

        name_ratio = similarity(title, stem)
        if name_ratio >= 0.92:
            score += 55
            reasons.append("Executable name closely matches the game folder name.")
        elif name_ratio >= 0.70:
            score += 36
            reasons.append("Executable name partially matches the game folder name.")
        elif normalize_title(title) in normalize_title(stem):
            score += 28
            reasons.append("Executable name contains the game title.")
        else:
            score += name_ratio * 20
            if name_ratio < 0.35:
                reasons.append("Executable name does not strongly match the folder title.")

        if depth <= 1:
            score += 30
            reasons.append("Executable is near the top of the game folder.")
        elif depth <= 3:
            score += 18
            reasons.append("Executable is in a common shallow launch location.")
        else:
            score -= min(28, depth * 3)
            reasons.append(f"Executable is nested {depth} folders deep.")

        good_hits = sorted(part for part in GOOD_PATH_PARTS if f"/{part}/" in f"/{rel_lower}/" or stem_lower.endswith(part))
        if good_hits:
            score += 14
            reasons.append(f"Found common game launch path markers: {', '.join(good_hits[:4])}.")

        if size:
            size_mb = size / (1024 * 1024)
            if size_mb >= 100:
                score += 28
                reasons.append(f"Large executable ({size_mb:.1f} MB), often a primary binary.")
            elif size_mb >= 20:
                score += 20
                reasons.append(f"Substantial executable size ({size_mb:.1f} MB).")
            elif size_mb >= 5:
                score += 12
                reasons.append(f"Moderate executable size ({size_mb:.1f} MB).")
            elif size_mb < 1:
                if native_linux_candidate and (suffix == ".sh" or not suffix):
                    score += 4
                    reasons.append("Small Linux launcher file; size is normal for scripts and wrapper launchers.")
                else:
                    score -= 16
                    reasons.append("Very small executable; may be a helper or bootstrapper.")
            else:
                score += max(0, math.log2(size_mb + 1) * 2)

        if suffix == ".exe":
            try:
                version_info = read_version_info(exe_path) if include_version_info else read_pe_summary(exe_path)
            except Exception:
                version_info = read_pe_summary(exe_path)
            if version_info:
                product = version_info.get("ProductName") or version_info.get("FileDescription") or ""
                if product:
                    score += 10
                    reasons.append("Readable Windows version metadata was found.")
                else:
                    score += 5
                    reasons.append("Valid Windows PE header was found.")
                if product:
                    ratio = similarity(title, product)
                    if ratio >= 0.72:
                        score += 16
                        reasons.append(f"Version metadata title looks relevant: {product}.")
            else:
                reasons.append("No readable Windows version metadata.")
        else:
            reasons.append("No Windows version metadata expected for native Linux launch files.")

        if "shipping" in stem_lower or "win64" in rel_lower or "linux64" in rel_lower or "binaries" in rel_lower:
            score += 10
            reasons.append("Looks like an Unreal/Unity shipping binary.")

        confidence = max(0, min(100, round(score)))
        if not reasons:
            reasons.append("Selected by balanced score across name, location, size, and metadata.")
        return ExecutableCandidate(
            path=exe_path,
            score=score,
            confidence=confidence,
            size_bytes=size,
            depth=depth,
            reasons=reasons,
            version_info=version_info,
        )
