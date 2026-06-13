from app.utils.camera_enum import _is_builtin, has_external_camera


def test_is_builtin():
    assert _is_builtin("Integrated Webcam")
    assert _is_builtin("HP TrueVision HD")
    assert _is_builtin("Built-in Camera")
    assert not _is_builtin("Logitech C920")
    assert not _is_builtin("USB Video Device")


def test_has_external_camera(monkeypatch):
    monkeypatch.setattr("os.name", "posix")
    assert has_external_camera() is True
