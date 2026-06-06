"""Create Windows .lnk shortcuts to TrashSorterPro.exe.

Drops two shortcuts so the user doesn't have to dig into dist/:
  - <project_root>/Trash Sorter Pro.lnk
  - <Desktop>/Trash Sorter Pro.lnk

Pure-PowerShell underneath so we don't need pywin32 in the build env.
Idempotent: re-running just refreshes the targets.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = ROOT / "dist" / "TrashSorterPro" / "TrashSorterPro.exe"
ICON = ROOT / "app" / "ui" / "resources" / "icons" / "app.ico"
NAME = "Trash Sorter Pro.lnk"


def _desktop_dir() -> Path:
    home = Path.home()
    for cand in (home / "Desktop", home / "OneDrive" / "Desktop"):
        if cand.exists():
            return cand
    return home / "Desktop"


def _make_lnk(target: Path, link: Path, icon: Path | None) -> None:
    icon_arg = f'; $s.IconLocation = "{icon}"' if icon and icon.exists() else ""
    ps = (
        f'$w = New-Object -ComObject WScript.Shell; '
        f'$s = $w.CreateShortcut("{link}"); '
        f'$s.TargetPath = "{target}"; '
        f'$s.WorkingDirectory = "{target.parent}"; '
        f'$s.WindowStyle = 1; '
        f'$s.Description = "Trash Sorter Pro - YOLO trash classifier"'
        f'{icon_arg}; '
        f'$s.Save()'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=True,
        capture_output=True,
    )


def main() -> int:
    if os.name != "nt":
        print("not Windows; skipping shortcut creation")
        return 0
    if not EXE.exists():
        print(f"exe not found at {EXE} — build first")
        return 1
    targets = [ROOT / NAME, _desktop_dir() / NAME]
    for link in targets:
        try:
            link.parent.mkdir(parents=True, exist_ok=True)
            _make_lnk(EXE, link, ICON if ICON.exists() else None)
            print(f"[OK] {link}")
        except subprocess.CalledProcessError as e:
            print(f"[FAIL] {link}: {e.stderr.decode(errors='replace').strip()}")
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
