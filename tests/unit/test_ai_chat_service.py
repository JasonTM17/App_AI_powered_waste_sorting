from app.agent.ai_chat_service import build_chat_response


def test_map_question_uses_fast_local_answer_without_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-used")

    class FailClient:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Local map questions must not call DeepSeek")

    monkeypatch.setattr("app.agent.ai_chat_service.httpx.Client", FailClient)
    response = build_chat_response(
        role="user",
        message="Thùng nào của mình đang gần đầy?",
        context={
            "operations_map": {
                "available": True,
                "scope": "user_assigned_stations",
                "station_total": 2,
                "open_alert_total": 1,
                "full_or_warning_bins": [
                    {
                        "station_id": "owned-01",
                        "station_name": "Trạm của tôi",
                        "label": "Tái chế",
                        "fill_percent": 96,
                        "status": "full",
                    }
                ],
            }
        },
    )

    assert response.available is True
    assert response.provider == "local"
    assert response.answer_source == "local"
    assert response.latency_ms < 100
    assert "Trạm của tôi" in response.message
    assert "96%" in response.message


def test_admin_device_question_uses_local_runtime_snapshot(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "must-not-be-used")

    class FailClient:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Local runtime questions must not call DeepSeek")

    monkeypatch.setattr("app.agent.ai_chat_service.httpx.Client", FailClient)
    response = build_chat_response(
        role="admin",
        message="Thiết bị nào đang bất thường?",
        context={
            "runtime": {
                "camera": {"connected": True, "running": True, "message": "Camera đang chạy"},
                "uart": {"connected": False, "running": False, "message": "Chưa kết nối"},
                "model": {"connected": True, "running": True, "message": "Model sẵn sàng"},
                "three_bin_classifier": {
                    "connected": False,
                    "running": False,
                    "message": "Chưa nạp",
                },
            }
        },
    )

    assert response.answer_source == "local"
    assert "Có 2 thành phần chưa sẵn sàng" in response.message
    assert "UART: chưa sẵn sàng" in response.message
