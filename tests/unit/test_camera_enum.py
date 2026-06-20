from app.utils.camera_enum import (
    _is_builtin,
    _is_external_directshow_name,
    camera_unavailable_message,
    has_external_camera,
    probe_usb_cameras,
)


def test_is_builtin():
    assert _is_builtin("Integrated Webcam")
    assert _is_builtin("HP TrueVision HD")
    assert _is_builtin("Built-in Camera")
    assert not _is_builtin("Logitech C920")
    assert not _is_builtin("USB Video Device")


def test_has_external_camera(monkeypatch):
    monkeypatch.setattr("os.name", "posix")
    assert has_external_camera() is True


def test_directshow_filters_virtual_camera_names():
    assert not _is_external_directshow_name("OBS Virtual Camera")
    assert not _is_external_directshow_name("Integrated Webcam")
    assert _is_external_directshow_name("USB Video Device")


def test_probe_usb_cameras_uses_directshow_when_pnp_unavailable(monkeypatch):
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setattr("app.utils.camera_enum.list_pnp_cameras", lambda: [])
    monkeypatch.setattr(
        "app.utils.camera_enum.list_directshow_cameras",
        lambda: ["OBS Virtual Camera", "USB Video Device"],
    )

    class _Quality:
        usable = False
        reason = "mock"

        def to_dict(self):
            return {"usable": self.usable, "reason": self.reason}

    class _Capture:
        opened_sources = []

        def __init__(self, idx, _backend):
            self.idx = idx
            _Capture.opened_sources.append(idx)

        def isOpened(self):  # noqa: N802
            return False

        def release(self):
            pass

    class _Cv2:
        CAP_DSHOW = 1
        CAP_MSMF = 2
        CAP_ANY = 3
        VideoCapture = _Capture

    monkeypatch.setitem(__import__("sys").modules, "cv2", _Cv2)
    monkeypatch.setattr("app.utils.camera_enum._sample_capture_quality", lambda _cap: _Quality())

    probes = probe_usb_cameras()

    assert probes
    assert {item["index"] for item in probes} == {1}
    assert _Capture.opened_sources == [1, 1, 1]


def test_camera_unavailable_message_names_virtual_only(monkeypatch):
    monkeypatch.setattr(
        "app.utils.camera_enum.list_directshow_cameras",
        lambda: ["OBS Virtual Camera"],
    )

    message = camera_unavailable_message()

    assert "OBS Virtual Camera" in message
    assert "camera USB thật" in message
