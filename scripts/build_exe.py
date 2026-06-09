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
        (ROOT / "assets" / "audio", "assets/audio"),
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
    # Don't pre-delete dist/build — if a previous build's exe is still
    # running it locks the folder. PyInstaller's --noconfirm overwrites
    # files in place; --clean wipes the PyInstaller work cache only.
    for d in (DIST, BUILD):
        if not d.exists():
            continue
        try:
            shutil.rmtree(d)
        except (OSError, PermissionError) as e:
            print(f"warn: could not remove {d} (probably locked): {e}")
            print("      proceeding — PyInstaller will overwrite reachable files")

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

    # Drop shortcuts at project root + Desktop so user doesn't have to
    # dig into dist/TrashSorterPro/ to launch the app.
    try:
        from scripts.make_shortcuts import main as _make_shortcuts
        _make_shortcuts()
    except Exception as e:
        print(f"warn: shortcut creation failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
