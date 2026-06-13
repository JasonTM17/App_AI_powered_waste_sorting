import os

import pytest

# Setup headless Qt for all UI tests globally
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def mock_appdata(monkeypatch, tmp_path):
    """Ensure tests don't write to the real user's APPDATA directory."""
    appdata = tmp_path / "mock_appdata"
    appdata.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata))
    return appdata
