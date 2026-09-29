"""Crop four 2x2 source sheets into optimized catalog garments.

Usage: python scripts/crop_catalog_sheets.py OUTPUT_DIR SHEET[:name1,name2,name3,name4] ...
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def crop_sheet(source_path: Path, output_dir: Path, names: list[str]) -> None:
    if len(names) != 4:
        raise ValueError("Each sheet requires exactly four output names")
    with Image.open(source_path) as source:
        width, height = source.size
        boxes = [
            (0, 0, width // 2, height // 2),
            (width // 2, 0, width, height // 2),
            (0, height // 2, width // 2, height),
            (width // 2, height // 2, width, height),
        ]
        for name, box in zip(names, boxes, strict=True):
            crop = source.crop(box).convert("RGB")
            crop.thumbnail((720, 720), Image.Resampling.LANCZOS)
            crop.save(output_dir / f"{name}.webp", "WEBP", quality=86, method=6)


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    output_dir = Path(sys.argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    for spec in sys.argv[2:]:
        source, separator, names = spec.rpartition(":")
        if not separator:
            raise ValueError(f"Invalid sheet specification: {spec}")
        crop_sheet(Path(source), output_dir, names.split(","))


if __name__ == "__main__":
    main()
