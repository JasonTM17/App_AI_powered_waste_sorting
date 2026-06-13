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
