"""Bundled laptop-speaker voice pack lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.core.hardware_profile import (
    GD5800_MULTI_OBJECT_WARNING_TRACK,
    GD5800_STARTUP_TRACK,
    PROXIMITY_SENSORS,
    ROUTES,
)
from app.utils.paths import resource_path

VoiceGender = Literal["female", "male"]
AudioEventKey = Literal[
    "startup",
    "sort_O",
    "sort_R",
    "sort_I",
    "bin_full_O",
    "bin_full_R",
    "bin_full_I",
    "multi_object_warning",
]

VOICE_PACK_RELS: dict[VoiceGender, Path] = {
    "female": Path("assets") / "audio" / "gd5800" / "Giọng nữ",
    "male": Path("assets") / "audio" / "gd5800" / "Giọng nam",
}

AUDIO_EVENT_LABELS: dict[AudioEventKey, str] = {
    "startup": "Khởi động",
    "sort_O": "Phân loại hữu cơ",
    "sort_R": "Phân loại vô cơ",
    "sort_I": "Phân loại tái chế",
    "bin_full_O": "Hữu cơ đã đầy",
    "bin_full_R": "Vô cơ đã đầy",
    "bin_full_I": "Tái chế đã đầy",
    "multi_object_warning": "Cảnh báo nhiều vật",
}

AUDIO_EVENT_FILES: dict[VoiceGender, dict[AudioEventKey, str]] = {
    "female": {
        "startup": "Xin chao tôi là thùng rác phân loại.mp3",
        "sort_O": "Phân loại hữu cơ.mp3",
        "sort_R": "Phân loại Vô cơ.mp3",
        "sort_I": "Phân loại rác tái chế.mp3",
        "bin_full_O": "Hữu cơ đã đầy.mp3",
        "bin_full_R": "Vô cơ đã đầy.mp3",
        "bin_full_I": "Tái chế đã đầy.mp3",
        "multi_object_warning": "Xin chỉ bỏ 1 loại rác thôi.mp3",
    },
    "male": {
        "startup": "Xin chào tôi là thùng rác phân loại rác tự động.mp3",
        "sort_O": "Phân loại rác hữu cơ.mp3",
        "sort_R": "Phân loại rác vô cơ.mp3",
        "sort_I": "Phân loại rác tái chế.mp3",
        "bin_full_O": "Hữu cơ đã đầy.mp3",
        "bin_full_R": "Vô cơ đã đầy.mp3",
        "bin_full_I": "Tái chế đã đầy.mp3",
        "multi_object_warning": "XIn chỉ để 1 loại rác.mp3",
    },
}

_LEGACY_WARNING_EVENTS = {
    "multi_class_dispatch_blocked": "multi_object_warning",
    "multi_object_warning": "multi_object_warning",
}

AUDIO_EVENT_TRACKS: dict[AudioEventKey, int] = {
    "startup": GD5800_STARTUP_TRACK,
    "multi_object_warning": GD5800_MULTI_OBJECT_WARNING_TRACK,
    **{f"sort_{route.command}": route.gd5800_track for route in ROUTES},
    **{f"bin_full_{sensor.command}": sensor.gd5800_track for sensor in PROXIMITY_SENSORS},
}


def normalize_voice_gender(value: object) -> VoiceGender:
    return "male" if str(value or "").strip().lower() == "male" else "female"


def voice_gender_label(value: object) -> str:
    return "giọng nam" if normalize_voice_gender(value) == "male" else "giọng nữ"


def voice_pack_dir(gender: object = "female") -> Path:
    return resource_path(VOICE_PACK_RELS[normalize_voice_gender(gender)])


def audio_event_path(event_key: str, gender: object = "female") -> Path | None:
    clean_gender = normalize_voice_gender(gender)
    clean_key = _normalize_event_key(event_key)
    if clean_key is None:
        return None
    file_name = AUDIO_EVENT_FILES[clean_gender].get(clean_key)
    if not file_name:
        return None
    path = voice_pack_dir(clean_gender) / file_name
    return path if path.exists() else None


def sort_voice_path(command: str, gender: object = "female") -> Path | None:
    clean_command = str(command or "").strip().upper()
    return audio_event_path(f"sort_{clean_command}", gender)


def warning_voice_path(key: str, gender: object = "female") -> Path | None:
    return audio_event_path(str(_LEGACY_WARNING_EVENTS.get(str(key or "").strip(), "")), gender)


def voice_pack_status(gender: object = "female") -> dict[str, bool]:
    return audio_event_status(gender)


def audio_event_status(gender: object = "female") -> dict[str, bool]:
    clean_gender = normalize_voice_gender(gender)
    pack_dir = voice_pack_dir(clean_gender)
    return {
        event_key: (pack_dir / file_name).exists()
        for event_key, file_name in AUDIO_EVENT_FILES[clean_gender].items()
    }


def _normalize_event_key(event_key: str) -> AudioEventKey | None:
    clean = str(event_key or "").strip()
    if clean in AUDIO_EVENT_LABELS:
        return clean  # type: ignore[return-value]
    if clean in _LEGACY_WARNING_EVENTS:
        return _LEGACY_WARNING_EVENTS[clean]  # type: ignore[return-value]
    return None


__all__ = [
    "AUDIO_EVENT_FILES",
    "AUDIO_EVENT_LABELS",
    "AUDIO_EVENT_TRACKS",
    "AudioEventKey",
    "VoiceGender",
    "audio_event_path",
    "audio_event_status",
    "normalize_voice_gender",
    "sort_voice_path",
    "voice_gender_label",
    "voice_pack_dir",
    "voice_pack_status",
    "warning_voice_path",
]
