import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.ui.pages.recognition_test import RecognitionTestPage


def test_recognition_test_page_emits_canonical_sample_plan(qtbot):
    page = RecognitionTestPage()
    qtbot.addWidget(page)
    panel = page.recognition_test_panel
    panel.sample_name.setText("lon bia thật")
    panel.expected_class.setCurrentText("lon bia")
    panel.btn_add.click()

    with qtbot.waitSignal(
        page.recognition_test_start_requested,
        timeout=500,
    ) as blocker:
        panel.btn_start.click()

    payload = blocker.args[0]
    assert payload["samples"] == [
        {"label": "lon bia thật", "expected_class": "Aluminum can"}
    ]
    assert payload["repetitions"] == 5
    assert payload["countdown_seconds"] == 3
    assert payload["scan_timeout_seconds"] == 8


def test_recognition_test_page_delegates_state_and_trial(qtbot):
    page = RecognitionTestPage()
    qtbot.addWidget(page)

    page.set_recognition_test_state(
        {
            "active": True,
            "state": "SCANNING",
            "sample_label": "chai nhựa",
            "trial_number": 2,
            "repetitions": 5,
        }
    )
    page.set_recognition_test_trial(
        {
            "expected_class": "Plastic bottle",
            "predicted_class": "Plastic bottle",
            "verdict": "correct",
            "confidence": 0.88,
        }
    )

    assert page.recognition_test_panel.state_label.text() == "Đang quét"
    assert "chai nhựa" in page.recognition_test_panel.progress_label.text()
    assert "Plastic bottle" in page.recognition_test_panel.result_label.text()
