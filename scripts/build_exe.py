"""PyInstaller one-folder build for Trash Sorter Pro."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
PYINSTALLER_BUILD = BUILD / "pyinstaller"
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
    if any(models.glob("*.pt")):
        out.append(f"{models}{sep}models")
    return out


def _icon_arg() -> list[str]:
    icon = ROOT / "app" / "ui" / "resources" / "icons" / "app.ico"
    if icon.exists():
        return ["--icon", str(icon)]
    return []


def _python_ssl_dlls() -> list[Path]:
    dll_dir = Path(sys.base_prefix) / "DLLs"
    return [p for p in (dll_dir / "libssl-3-x64.dll", dll_dir / "libcrypto-3-x64.dll") if p.exists()]


def _repair_bundled_ssl_dlls() -> None:
    """Keep Python's `_ssl.pyd` paired with the OpenSSL DLLs it was built for."""
    target_dir = DIST / APP_NAME / "_internal"
    if not target_dir.exists():
        return
    for src in _python_ssl_dlls():
        dst = target_dir / src.name
        shutil.copy2(src, dst)
        print(f"[OK] bundled Python SSL DLL: {dst}")


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

    PYINSTALLER_BUILD.mkdir(parents=True, exist_ok=True)
    args = [
        "--name", APP_NAME,
        "--noconsole",
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(PYINSTALLER_BUILD),
        "--specpath", str(PYINSTALLER_BUILD),
    ]
    for d in _datas():
        args.extend(["--add-data", d])
    args.extend(_icon_arg())
    args.append(str(ROOT / "app" / "__main__.py"))

    print("PyInstaller args:", args)
    PyInstaller.__main__.run(args)
    _repair_bundled_ssl_dlls()
    print(f"\n[OK] Build complete: {DIST / APP_NAME}")

    # Keep generated shortcuts out of the source root.
    try:
        from scripts.make_shortcuts import main as _make_shortcuts
        _make_shortcuts()
    except Exception as e:
        print(f"warn: shortcut creation failed: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
