#!/usr/bin/env python3
"""Generate a multi-resolution Windows .ico from the app PNG (dev tool; requires Pillow)."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - dev-only script
    raise SystemExit(
        "Pillow is required for icon generation. Install with: uv pip install pillow"
    ) from exc

DEFAULT_SIZES = (16, 24, 32, 48, 64, 128, 256)


def generate_icon(png_path: Path, ico_path: Path, sizes: tuple[int, ...] = DEFAULT_SIZES) -> None:
    with Image.open(png_path) as img:
        rgba = img.convert("RGBA")
        rgba.save(
            ico_path,
            format="ICO",
            sizes=[(size, size) for size in sizes],
        )


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--png",
        type=Path,
        default=root / "immich-go-gui.png",
        help="Source PNG image",
    )
    parser.add_argument(
        "--ico",
        type=Path,
        default=root / "immich-go-gui.ico",
        help="Output ICO path",
    )
    args = parser.parse_args()
    if not args.png.is_file():
        raise SystemExit(f"PNG not found: {args.png}")
    generate_icon(args.png, args.ico)
    print(f"Wrote {args.ico} ({', '.join(str(s) for s in DEFAULT_SIZES)}px)")


if __name__ == "__main__":
    main()
