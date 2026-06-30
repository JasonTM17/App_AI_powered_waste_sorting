"""Create checksums and a manifest for the Windows desktop EXE bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APP_DIR = ROOT / "dist" / "TrashSorterPro"
EXE_NAME = "TrashSorterPro.exe"

BLOCKED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "config.json",
}
BLOCKED_SUFFIXES = {
    ".db",
    ".log",
    ".sqlite",
    ".sqlite3",
}
METADATA_FILE_NAMES = {
    "desktop-exe.sha256",
    "desktop-release-manifest.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _blocked_reason(path: Path) -> str | None:
    name = path.name.casefold()
    if name in BLOCKED_FILE_NAMES:
        return f"blocked file name: {path.name}"
    if path.suffix.casefold() in BLOCKED_SUFFIXES:
        return f"blocked suffix: {path.suffix}"
    if name.startswith(".env"):
        return f"blocked env-like file: {path.name}"
    return None


def _iter_payload_files(app_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in app_dir.rglob("*")
        if path.is_file() and path.name.casefold() not in METADATA_FILE_NAMES
    )


def build_manifest(app_dir: Path) -> dict[str, object]:
    exe = app_dir / EXE_NAME
    if not exe.exists():
        raise FileNotFoundError(f"Desktop executable not found: {exe}")

    files = _iter_payload_files(app_dir)
    blocked = [
        {"path": str(path.relative_to(app_dir)).replace("\\", "/"), "reason": reason}
        for path in files
        if (reason := _blocked_reason(path))
    ]
    if blocked:
        details = ", ".join(f"{item['path']} ({item['reason']})" for item in blocked[:8])
        raise RuntimeError(f"Refusing to package unsafe desktop artifact files: {details}")

    entries: list[dict[str, object]] = []
    total_bytes = 0
    for path in files:
        rel = str(path.relative_to(app_dir)).replace("\\", "/")
        size = path.stat().st_size
        total_bytes += size
        entries.append({"path": rel, "bytes": size, "sha256": _sha256(path)})

    return {
        "artifact": "TrashSorterPro desktop EXE bundle",
        "artifact_dir": str(app_dir.relative_to(ROOT)).replace("\\", "/"),
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "executable": EXE_NAME,
        "metadata_files": sorted(METADATA_FILE_NAMES),
        "payload_file_count": len(entries),
        "payload_total_bytes": total_bytes,
        "blocked_patterns": {
            "file_names": sorted(BLOCKED_FILE_NAMES),
            "suffixes": sorted(BLOCKED_SUFFIXES),
        },
        "files": entries,
    }


def write_checksums(app_dir: Path, manifest: dict[str, object]) -> Path:
    checksum_path = app_dir / "desktop-exe.sha256"
    files = manifest.get("files", [])
    if not isinstance(files, list):
        raise TypeError("manifest files must be a list")
    lines = [
        f"{item['sha256']}  {item['path']}"
        for item in files
        if isinstance(item, dict) and "sha256" in item and "path" in item
    ]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return checksum_path


def write_manifest(app_dir: Path, manifest: dict[str, object]) -> Path:
    manifest_path = app_dir / "desktop-release-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-dir", type=Path, default=DEFAULT_APP_DIR)
    args = parser.parse_args(argv)

    app_dir = args.app_dir.expanduser().resolve()
    manifest = build_manifest(app_dir)
    checksum_path = write_checksums(app_dir, manifest)
    manifest = build_manifest(app_dir)
    manifest_path = write_manifest(app_dir, manifest)
    print(f"[OK] desktop checksum: {checksum_path}")
    print(f"[OK] desktop manifest: {manifest_path}")
    print(
        "[OK] payload_files="
        f"{manifest['payload_file_count']} payload_bytes={manifest['payload_total_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
