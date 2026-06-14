import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_datas_returns_list(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_exe
    out = build_exe._datas()
    assert isinstance(out, list)
    sep = ";" if sys.platform == "win32" else ":"
    for entry in out:
        assert sep in entry
    assert any(str(ROOT / "assets" / "audio") in entry for entry in out)
    icon_args = build_exe._icon_arg()
    assert icon_args[:1] == ["--icon"]
    assert icon_args[1].endswith("app.ico")
    if sys.platform == "win32":
        ssl_dlls = {path.name for path in build_exe._python_ssl_dlls()}
        assert "libssl-3-x64.dll" in ssl_dlls
        assert "libcrypto-3-x64.dll" in ssl_dlls


def test_pyinstaller_outputs_stay_out_of_source_root(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_exe

    assert build_exe.PYINSTALLER_BUILD.parent == build_exe.BUILD
    assert build_exe.PYINSTALLER_BUILD != build_exe.ROOT


def test_shortcuts_include_obvious_launch_locations(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import make_shortcuts

    targets = make_shortcuts._shortcut_targets()
    assert make_shortcuts.ROOT / make_shortcuts.NAME in targets
    assert make_shortcuts.ROOT / "dist" / make_shortcuts.NAME in targets


def test_demo_builder_uses_separate_output_and_writes_handoff_guide(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import build_demo_exe

    calls = []
    monkeypatch.setattr(build_demo_exe, "ROOT", tmp_path)
    monkeypatch.setattr(build_demo_exe, "BUILD", tmp_path / "build")
    monkeypatch.setattr(
        build_demo_exe,
        "build",
        lambda **kwargs: calls.append(kwargs) or 0,
    )

    assert build_demo_exe.main() == 0
    assert calls[0]["app_name"] == "TrashSorterProDemo"
    assert calls[0]["create_shortcuts"] is False
    guide = tmp_path / "dist" / "TrashSorterProDemo" / "HUONG-DAN-MO-DEMO.txt"
    assert "khong can dang nhap" in guide.read_text(encoding="utf-8")
