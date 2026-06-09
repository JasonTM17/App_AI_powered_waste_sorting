"""Bundled laptop-speaker voice pack lookup."""

from __future__ import annotations

from pathlib import Path

from app.utils.paths import resource_path

VOICE_PACK_REL = Path("assets") / "audio" / "gd5800" / "Giọng nữ"

SORT_VOICE_FILES = {
    "O": "Phân loại hữu cơ.mp3",
    "R": "Phân loại Vô cơ.mp3",
    "I": "Phân loại rác tái chế.mp3",
}

WARNING_VOICE_FILES = {
    "multi_class_dispatch_blocked": "Xin chỉ bỏ 1 loại rác thôi.mp3",
}


def voice_pack_dir() -> Path:
    return resource_path(VOICE_PACK_REL)


def sort_voice_path(command: str) -> Path | None:
    file_name = SORT_VOICE_FILES.get(str(command or "").strip().upper())
    if not file_name:
        return None
    path = voice_pack_dir() / file_name
    return path if path.exists() else None


def warning_voice_path(key: str) -> Path | None:
    file_name = WARNING_VOICE_FILES.get(str(key or "").strip())
    if not file_name:
        return None
    path = voice_pack_dir() / file_name
    return path if path.exists() else None


def voice_pack_status() -> dict[str, bool]:
    return {
        **{
            f"sort_{command}": (voice_pack_dir() / file_name).exists()
            for command, file_name in SORT_VOICE_FILES.items()
        },
        **{
            key: (voice_pack_dir() / file_name).exists()
            for key, file_name in WARNING_VOICE_FILES.items()
        },
    }
