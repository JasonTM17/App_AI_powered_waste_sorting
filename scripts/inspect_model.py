"""Print metadata for a YOLO .pt model.

Usage:
    python scripts/inspect_model.py [path]

Defaults to models/best.pt.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path("models/best.pt")
    if not target.exists():
        print(f"error: model not found: {target}", file=sys.stderr)
        return 1

    from ultralytics import YOLO

    model = YOLO(str(target))
    print(f"path: {target}")
    print(f"task: {getattr(model, 'task', '?')}")
    ckpt = getattr(model, "ckpt_path", None)
    if ckpt:
        print(f"ckpt: {Path(ckpt).name}")
    names = dict(getattr(model, "names", {}))
    print(f"classes ({len(names)}):")
    for k, v in sorted(names.items()):
        print(f"  {k:>3}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
