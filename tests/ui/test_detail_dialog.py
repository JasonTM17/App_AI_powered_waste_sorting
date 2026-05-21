import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.widgets.detail_dialog import DetectionDetailDialog


class _Row:
    id = 1
    track_id = 7
    ts = "2026-05-21T18:42:03+00:00"
    cls_id = 0
    cls_name = "paper"
    conf = 0.92
    bbox_x1 = 10
    bbox_y1 = 20
    bbox_x2 = 100
    bbox_y2 = 200
    thumbnail = b""
    uart_command = "P"
    ack_status = "ok"
    rtt_ms = 42


def test_dialog_constructs_with_row(qtbot):
    dlg = DetectionDetailDialog(_Row())
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "Chi tiết detection"
