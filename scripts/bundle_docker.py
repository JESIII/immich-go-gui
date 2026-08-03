"""Bundle Docker & Web Console files into one text file for LLM review.

Bundles web.py, webapp/, templates/, static/ (CSS/JS), Dockerfile, docker-compose.yml,
WEB_UI.md, fetch_vendor.sh, and web tests into a single text file.

Usage:
    uv run python scripts/bundle_docker.py [output_path]

Defaults:
    output_path: immichgo_docker_bundle.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path

_SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
    "dist",
    "build",
    "vendor",
}

_TEXT_EXTENSIONS = {
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".md",
    ".txt",
    ".sh",
    ".html",
    ".css",
    ".js",
}

_DOCKER_WEB_FILES = (
    "Dockerfile",
    "docker-compose.yml",
    "WEB_UI.md",
    "web.py",
    "scripts/fetch_vendor.sh",
)

_DOCKER_WEB_GLOBS = (
    "webapp/**/*",
    "templates/**/*",
    "static/app.css",
    "static/app.js",
    "tests/test_web.py",
)


def _is_under_skipped_dir(path: Path, repo_root: Path) -> bool:
    try:
        parts = path.resolve().relative_to(repo_root.resolve()).parts
    except ValueError:
        return True
    return any(part in _SKIP_DIR_NAMES for part in parts)


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    return path.name in {"Dockerfile", ".gitignore"}


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None


def collect_docker_web_files(repo_root: Path) -> list[Path]:
    found: set[Path] = set()

    def add(path: Path) -> None:
        if not path.is_file():
            return
        if _is_under_skipped_dir(path, repo_root):
            return
        if not _is_text_file(path):
            return
        found.add(path.resolve())

    for rel in _DOCKER_WEB_FILES:
        add(repo_root / rel)

    for pattern in _DOCKER_WEB_GLOBS:
        for path in repo_root.glob(pattern):
            add(path)

    def sort_key(p: Path) -> tuple[int, str]:
        rel = p.relative_to(repo_root).as_posix()
        rank = 50
        if rel in ("Dockerfile", "docker-compose.yml", "WEB_UI.md"):
            rank = 0
        elif rel == "web.py":
            rank = 5
        elif rel.startswith("webapp/"):
            rank = 10
        elif rel.startswith("templates/"):
            rank = 20
        elif rel.startswith("static/"):
            rank = 30
        elif rel.startswith("scripts/"):
            rank = 40
        elif rel.startswith("tests/"):
            rank = 50
        return (rank, rel)

    return sorted(found, key=sort_key)


def _build_header(repo_root: Path, valid: list[tuple[Path, Path, int, str]]) -> str:
    lines = [
        "=" * 80,
        "IMMICH-GO GUI — DOCKER & WEB CONSOLE BUNDLE",
        "=" * 80,
        "Generated for LLM code review & prompting",
        f"Repo root: {repo_root}",
        f"Files included: {len(valid)}",
        "",
        "Bundle contents:",
        "  - Dockerfile & docker-compose.yml",
        "  - WEB_UI.md documentation",
        "  - web.py Uvicorn entrypoint",
        "  - webapp/ package (app, forms, runner, auth, diagnostics)",
        "  - templates/ (base, login, partials)",
        "  - static/ (app.css, app.js)",
        "  - scripts/fetch_vendor.sh",
        "  - tests/test_web.py",
        "",
        "Files:",
    ]
    for idx, (_, rel, line_count, _) in enumerate(valid, 1):
        lines.append(f"  {idx:3d}. {rel.as_posix()} ({line_count} lines)")

    lines.extend(["=" * 80, ""])
    return "\n".join(lines)


def bundle_docker_web(output_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    files = collect_docker_web_files(repo_root)

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

    sections = [_build_header(repo_root, valid)]

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
        f"Successfully generated Docker/Web bundle: {output_path} "
        f"({len(valid)} files, {len(output_text.splitlines())} lines)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bundle Docker & Web files for LLM review"
    )
    parser.add_argument("output_path", nargs="?", help="Output file path")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out_file = (
        Path(args.output_path)
        if args.output_path
        else repo_root / "immichgo_docker_bundle.txt"
    )
    bundle_docker_web(out_file)


if __name__ == "__main__":
    main()
