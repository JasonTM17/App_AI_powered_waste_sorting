import importlib.util
from pathlib import Path


def _load_run_agent_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "run_agent.py"
    spec = importlib.util.spec_from_file_location("run_agent", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_agent_uses_default_local_host_port(monkeypatch):
    module = _load_run_agent_module()
    monkeypatch.delenv("TRASH_SORTER_AGENT_HOST", raising=False)
    monkeypatch.delenv("TRASH_SORTER_AGENT_PORT", raising=False)

    assert module._agent_host_port() == ("127.0.0.1", 8765)


def test_run_agent_reads_valid_agent_port_env(monkeypatch):
    module = _load_run_agent_module()
    monkeypatch.setenv("TRASH_SORTER_AGENT_HOST", "0.0.0.0")
    monkeypatch.setenv("TRASH_SORTER_AGENT_PORT", "8875")

    assert module._agent_host_port() == ("0.0.0.0", 8875)


def test_run_agent_ignores_invalid_agent_port_env(monkeypatch):
    module = _load_run_agent_module()
    monkeypatch.setenv("TRASH_SORTER_AGENT_PORT", "999999")

    assert module._agent_host_port() == ("127.0.0.1", 8765)
