"""Bundle all project source/config/test files into one text file for LLM analysis.

Captures application code, core modules, theme/assets text, tests, fixtures,
scripts, packaging, and project config — everything needed to understand how
this repo runs.

Usage:
    uv run python scripts/bundle_codebase.py [output_path]

Defaults:
    output_path: immichgo_modules_bundle.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

# Directory names skipped anywhere in a path.
_SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
    "site",
    "dist",
    "build",
    "wheels",
    "node_modules",
    ".kilo",
    ".agents",
    "canvases",
    "AppDir",
    "immich-go",
}

# Top-level paths (relative to repo root) always included when present.
_ROOT_FILES = (
    "app.py",
    "theme.py",
    "pyproject.toml",
    "mkdocs.yml",
    ".pre-commit-config.yaml",
    "README.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE.txt",
    "implementation.md",
)

# Extensions treated as text source/config for the project.
_TEXT_EXTENSIONS = {
    ".py",
    ".toml",
    ".qss",
    ".yml",
    ".yaml",
    ".json",
    ".md",
    ".txt",
    ".svg",
    ".cfg",
    ".ini",
    ".sh",
    ".bat",
    ".ps1",
    ".desktop",
    ".service",
}

# Generated / personal artifacts never bundled.
_SKIP_FILE_NAMES = {
    "immichgo_modules_bundle.txt",
    "immichgo_website_bundle.txt",
    "GitReadme.md",
    "TODO.md",
    "apper.py",
}

_SKIP_NAME_PREFIXES = (
    "Refinement",
    "immichgo_",
)

_SKIP_NAME_SUFFIXES = (
    "_bundle.txt",
    ".egg-info",
)


def _is_under_skipped_dir(path: Path, repo_root: Path) -> bool:
    try:
        parts = path.resolve().relative_to(repo_root.resolve()).parts
    except ValueError:
        return True
    return any(part in _SKIP_DIR_NAMES for part in parts)


def _should_skip_file(path: Path) -> bool:
    name = path.name
    if name in _SKIP_FILE_NAMES:
        return True
    if name.startswith(_SKIP_NAME_PREFIXES):
        return True
    if name.endswith(_SKIP_NAME_SUFFIXES):
        return True
    if name.endswith((".pyc", ".pyo", ".png", ".ico", ".jpg", ".jpeg", ".gif", ".webp", ".bin", ".exe", ".dmg", ".AppImage")):
        return True
    return False


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    # Extensionless project files that are still text.
    return path.name in {".gitignore", "Dockerfile", "Makefile"}


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None


def collect_project_files(repo_root: Path) -> list[Path]:
    """Return sorted unique project files that belong in the codebase bundle."""
    found: set[Path] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        if _is_under_skipped_dir(path, repo_root):
            return
        if _should_skip_file(path):
            return
        if not _is_text_file(path):
            return
        found.add(path.resolve())

    for rel in _ROOT_FILES:
        add(repo_root / rel)

    add(repo_root / ".gitignore")

    # Application / library / UI
    for pattern in (
        "core/**/*",
        "assets/**/*",
        "tests/**/*",
        "scripts/**/*",
        "packaging/**/*",
        "docs/**/*",
        ".github/**/*",
        ".vscode/**/*",
    ):
        for path in repo_root.glob(pattern):
            add(path)

    # Prefer stable, readable order: root → core → app-adjacent → tests → rest.
    def sort_key(p: Path) -> tuple:
        rel = p.relative_to(repo_root).as_posix()
        rank = 50
        if rel in _ROOT_FILES or rel == ".gitignore":
            rank = 0
        elif rel.startswith("core/"):
            rank = 10
        elif rel.startswith("assets/"):
            rank = 20
        elif rel.startswith("tests/"):
            rank = 30
        elif rel.startswith("scripts/"):
            rank = 40
        elif rel.startswith("packaging/"):
            rank = 45
        elif rel.startswith("docs/"):
            rank = 60
        elif rel.startswith(".github/"):
            rank = 70
        elif rel.startswith(".vscode/"):
            rank = 80
        return (rank, rel)

    return sorted(found, key=sort_key)


def bundle_codebase(output_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    files = collect_project_files(repo_root)

    header_lines = [
        "=" * 80,
        "IMMICH-GO GUI — FULL PROJECT CODEBASE BUNDLE",
        "=" * 80,
        "Generated for LLM review & prompting",
        f"Repo root: {repo_root}",
        f"Files included: {len(files)}",
        "",
        "Coverage:",
        "  - Root app entrypoints (app.py, theme.py)",
        "  - core/ (including flags.toml)",
        "  - assets/ text (theme.qss, icons/*.svg)",
        "  - tests/ (suite + fixtures)",
        "  - scripts/",
        "  - packaging/, project config, docs/, CI workflows",
        "",
        "Files:",
    ]

    valid: list[tuple[Path, Path, int, str]] = []
    skipped_binary = 0
    for path in files:
        content = _read_text(path)
        if content is None:
            skipped_binary += 1
            continue
        rel = path.relative_to(repo_root)
        lines = len(content.splitlines())
        valid.append((path, rel, lines, content))

    for idx, (_, rel, lines, _) in enumerate(valid, 1):
        header_lines.append(f"  {idx:3d}. {rel.as_posix()} ({lines} lines)")

    if skipped_binary:
        header_lines.append(f"\nSkipped unreadable/binary files: {skipped_binary}")

    header_lines.extend(["=" * 80, ""])
    sections = ["\n".join(header_lines)]

    for idx, (_, rel, lines, content) in enumerate(valid, 1):
        sections.append(
            f"{'=' * 80}\n"
            f"FILE {idx} / {len(valid)}: {rel.as_posix()} (Lines 1-{lines})\n"
            f"{'=' * 80}\n"
            f"{content}\n"
        )

    output_text = "\n".join(sections)
    output_path.write_text(output_text, encoding="utf-8")
    print(
        f"Successfully generated codebase bundle: {output_path} "
        f"({len(valid)} files, {len(output_text.splitlines())} lines)"
    )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    out_file = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "immichgo_modules_bundle.txt"
    bundle_codebase(out_file)
