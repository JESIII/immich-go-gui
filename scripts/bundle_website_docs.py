"""Bundle documentation and website rendering files into a single text file for LLM analysis.

Docs review profile: MkDocs site source, overrides, root README/CHANGELOG/CONTRIBUTING,
and docs CI workflow. Use bundle_codebase.py for application code review.

Usage:
    uv run scripts/bundle_website_docs.py [output_path]

Defaults:
    output_path: immichgo_website_bundle.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

_TEXT_EXTENSIONS = {".md", ".css", ".js", ".html", ".svg", ".yml", ".yaml", ".json", ".txt"}


def _collect_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []

    for config_name in [
        "mkdocs.yml",
        ".github/workflows/docs.yml",
        "pyproject.toml",
        "README.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
    ]:
        cfg_path = repo_root / config_name
        if cfg_path.exists():
            files.append(cfg_path)

    overrides_dir = repo_root / "overrides"
    if overrides_dir.exists():
        for p in sorted(overrides_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS:
                files.append(p)

    docs_dir = repo_root / "docs"
    if docs_dir.exists():
        for p in sorted(docs_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS:
                files.append(p)

    # Stable order: root configs → overrides → docs tree
    def sort_key(p: Path) -> tuple:
        rel = p.relative_to(repo_root).as_posix()
        if rel in {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "mkdocs.yml", "pyproject.toml"}:
            return (0, rel)
        if rel.startswith(".github/"):
            return (1, rel)
        if rel.startswith("overrides/"):
            return (2, rel)
        return (3, rel)

    return sorted(files, key=sort_key)


def _build_header(repo_root: Path, valid_files: list[tuple[Path, Path, int]]) -> str:
    lines = [
        "=" * 80,
        "IMMICH-GO GUI — WEBSITE & DOCUMENTATION BUNDLE",
        "=" * 80,
        "Generated for LLM documentation review & analysis",
        f"Repo root: {repo_root}",
        f"Files included: {len(valid_files)}",
        "",
        "Purpose:",
        "  MkDocs Material site source (docs/), theme overrides, mkdocs.yml,",
        "  root README/CHANGELOG/CONTRIBUTING, and docs CI workflow.",
        "  For application code review use: immichgo_modules_bundle.txt",
        "",
        "Files:",
    ]
    for idx, (_, rel_path, lines_count) in enumerate(valid_files, 1):
        lines.append(f"  {idx:3d}. {rel_path} ({lines_count} lines)")

    lines.extend(["=" * 80, "", ""])
    return "\n".join(lines)


def bundle_website(output_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    files_to_bundle = _collect_files(repo_root)

    valid_files: list[tuple[Path, Path, int]] = []
    for f in files_to_bundle:
        rel_path = f.relative_to(repo_root)
        lines_count = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
        valid_files.append((f, rel_path, lines_count))

    sections = [_build_header(repo_root, valid_files)]

    for idx, (f_path, rel_path, lines_count) in enumerate(valid_files, 1):
        content = f_path.read_text(encoding="utf-8", errors="replace")
        sections.append(
            f"{'=' * 80}\n"
            f"FILE {idx} / {len(valid_files)}: {rel_path} (Lines 1-{lines_count})\n"
            f"{'=' * 80}\n"
            f"{content}\n"
        )

    output_text = "\n".join(sections)
    output_path.write_text(output_text, encoding="utf-8")
    print(
        f"Successfully generated website docs bundle: {output_path} "
        f"({len(valid_files)} files, {len(output_text.splitlines())} lines)"
    )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    out_file = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "immichgo_website_bundle.txt"
    bundle_website(out_file)
