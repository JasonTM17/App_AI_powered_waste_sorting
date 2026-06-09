from app.core import voice_pack


def test_voice_pack_resolves_expected_files(tmp_path, monkeypatch):
    pack_dir = tmp_path / "Giọng nữ"
    pack_dir.mkdir()
    files = [
        "Phân loại hữu cơ.mp3",
        "Phân loại Vô cơ.mp3",
        "Phân loại rác tái chế.mp3",
        "Xin chỉ bỏ 1 loại rác thôi.mp3",
    ]
    for name in files:
        (pack_dir / name).write_bytes(b"mp3")
    monkeypatch.setattr(voice_pack, "voice_pack_dir", lambda: pack_dir)

    assert voice_pack.sort_voice_path("O") == pack_dir / files[0]
    assert voice_pack.sort_voice_path("R") == pack_dir / files[1]
    assert voice_pack.sort_voice_path("I") == pack_dir / files[2]
    assert voice_pack.warning_voice_path("multi_class_dispatch_blocked") == pack_dir / files[3]

    status = voice_pack.voice_pack_status()
    assert status == {
        "sort_O": True,
        "sort_R": True,
        "sort_I": True,
        "multi_class_dispatch_blocked": True,
    }


def test_voice_pack_missing_files_return_none(tmp_path, monkeypatch):
    pack_dir = tmp_path / "Giọng nữ"
    pack_dir.mkdir()
    monkeypatch.setattr(voice_pack, "voice_pack_dir", lambda: pack_dir)

    assert voice_pack.sort_voice_path("O") is None
    assert voice_pack.warning_voice_path("missing") is None
