"""PyInstaller one-folder build for Trash Sorter Pro."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_NAME = "TrashSorterPro"


def _datas() -> list[str]:
    items: list[tuple[Path, str]] = [
        (ROOT / "app" / "ui" / "resources", "app/ui/resources"),
        (ROOT / "config.example.json", "."),
    ]
    out: list[str] = []
    sep = ";" if sys.platform == "win32" else ":"
    for src, dst in items:
        if not src.exists():
            print(f"warn: data path missing, skip: {src}")
            continue
        out.append(f"{src}{sep}{dst}")
    models = ROOT / "models"
    if (models / "best.pt").exists():
        out.append(f"{models}{sep}models")
    return out


def _icon_arg() -> list[str]:
    icon = ROOT / "app" / "ui" / "resources" / "icons" / "app.ico"
    if icon.exists():
        return ["--icon", str(icon)]
    return []


def main() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)

    args = [
        "--name", APP_NAME,
        "--noconsole",
        "--noconfirm",
        "--clean",
    ]
    for d in _datas():
        args.extend(["--add-data", d])
    args.extend(_icon_arg())
    args.append(str(ROOT / "app" / "__main__.py"))

    print("PyInstaller args:", args)
    PyInstaller.__main__.run(args)
    print(f"\n[OK] Build complete: {DIST / APP_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
