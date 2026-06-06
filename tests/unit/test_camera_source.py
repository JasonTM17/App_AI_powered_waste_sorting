from app.utils.camera_source import normalize_camera_source


def test_normalize_camera_source_keeps_urls():
    assert normalize_camera_source("rtsp://camera.local/live") == "rtsp://camera.local/live"


def test_normalize_camera_source_extracts_index_from_label():
    assert normalize_camera_source("1 (DSHOW) - USB Camera") == "1"
