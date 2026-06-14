import runpy

import pytest

import app.__main__ as desktop_main


def test_demo_entrypoint_skips_admin_login(monkeypatch):
    calls = []
    monkeypatch.setattr(
        desktop_main,
        "main",
        lambda **kwargs: calls.append(kwargs) or 0,
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("app.demo_main", run_name="__main__")

    assert exc_info.value.code == 0
    assert calls == [{"require_admin_login": False}]
