from app.core import voice_pack
from app.core.hardware_profile import (
    GD5800_MULTI_OBJECT_WARNING_TRACK,
    GD5800_STARTUP_TRACK,
    PROXIMITY_SENSORS,
    ROUTES,
)


def test_voice_pack_resolves_expected_files(tmp_path, monkeypatch):
    female_dir = tmp_path / "Giọng nữ"
    male_dir = tmp_path / "Giọng nam"
    female_dir.mkdir()
    male_dir.mkdir()
    female_files = [
        "Xin chao tôi là thùng rác phân loại.mp3",
        "Phân loại hữu cơ.mp3",
        "Phân loại Vô cơ.mp3",
        "Phân loại rác tái chế.mp3",
        "Hữu cơ đã đầy.mp3",
        "Vô cơ đã đầy.mp3",
        "Tái chế đã đầy.mp3",
        "Xin chỉ bỏ 1 loại rác thôi.mp3",
    ]
    male_files = [
        "Xin chào tôi là thùng rác phân loại rác tự động.mp3",
        "Phân loại rác hữu cơ.mp3",
        "Phân loại rác vô cơ.mp3",
        "Phân loại rác tái chế.mp3",
        "Hữu cơ đã đầy.mp3",
        "Vô cơ đã đầy.mp3",
        "Tái chế đã đầy.mp3",
        "XIn chỉ để 1 loại rác.mp3",
    ]
    for name in female_files:
        (female_dir / name).write_bytes(b"mp3")
    for name in male_files:
        (male_dir / name).write_bytes(b"mp3")
    monkeypatch.setattr(
        voice_pack,
        "voice_pack_dir",
        lambda gender="female": male_dir
        if voice_pack.normalize_voice_gender(gender) == "male"
        else female_dir,
    )

    assert voice_pack.audio_event_path("startup") == female_dir / female_files[0]
    assert voice_pack.sort_voice_path("O") == female_dir / female_files[1]
    assert voice_pack.sort_voice_path("R") == female_dir / female_files[2]
    assert voice_pack.sort_voice_path("I") == female_dir / female_files[3]
    assert voice_pack.audio_event_path("bin_full_O") == female_dir / female_files[4]
    assert voice_pack.audio_event_path("bin_full_R") == female_dir / female_files[5]
    assert voice_pack.audio_event_path("bin_full_I") == female_dir / female_files[6]
    assert voice_pack.warning_voice_path("multi_class_dispatch_blocked") == female_dir / female_files[7]
    assert voice_pack.audio_event_path("startup", "male") == male_dir / male_files[0]
    assert voice_pack.sort_voice_path("O", "male") == male_dir / male_files[1]
    assert voice_pack.sort_voice_path("R", "male") == male_dir / male_files[2]
    assert voice_pack.sort_voice_path("I", "male") == male_dir / male_files[3]
    assert voice_pack.audio_event_path("bin_full_O", "male") == male_dir / male_files[4]
    assert voice_pack.audio_event_path("bin_full_R", "male") == male_dir / male_files[5]
    assert voice_pack.audio_event_path("bin_full_I", "male") == male_dir / male_files[6]
    assert voice_pack.warning_voice_path("multi_class_dispatch_blocked", "male") == male_dir / male_files[7]

    status = voice_pack.voice_pack_status()
    assert status == {
        "startup": True,
        "sort_O": True,
        "sort_R": True,
        "sort_I": True,
        "bin_full_O": True,
        "bin_full_R": True,
        "bin_full_I": True,
        "multi_object_warning": True,
    }
    assert voice_pack.voice_pack_status("male") == status


def test_voice_pack_missing_files_return_none(tmp_path, monkeypatch):
    pack_dir = tmp_path / "Giọng nữ"
    pack_dir.mkdir()
    monkeypatch.setattr(voice_pack, "voice_pack_dir", lambda gender="female": pack_dir)

    assert voice_pack.sort_voice_path("O") is None
    assert voice_pack.warning_voice_path("missing") is None


def test_bundled_voice_packs_cover_all_events():
    assert all(voice_pack.voice_pack_status("female").values())
    assert all(voice_pack.voice_pack_status("male").values())


def test_voice_gender_helpers_normalize_labels():
    assert voice_pack.normalize_voice_gender("male") == "male"
    assert voice_pack.normalize_voice_gender("bad") == "female"
    assert voice_pack.voice_gender_label("male") == "giọng nam"
    assert voice_pack.voice_gender_label("female") == "giọng nữ"


def test_audio_event_tracks_match_hardware_profile():
    expected = {
        "startup": GD5800_STARTUP_TRACK,
        "multi_object_warning": GD5800_MULTI_OBJECT_WARNING_TRACK,
        **{f"sort_{route.command}": route.gd5800_track for route in ROUTES},
        **{f"bin_full_{sensor.command}": sensor.gd5800_track for sensor in PROXIMITY_SENSORS},
    }

    assert expected == voice_pack.AUDIO_EVENT_TRACKS
    assert set(voice_pack.AUDIO_EVENT_LABELS) == set(expected)
