
import app.core.learn_now_training as learn_now_training


def test_start_learn_now_training_invokes_micro_candidate_script(tmp_path):
    script = tmp_path / "scripts" / "start_learn_now_micro_train.ps1"
    script.parent.mkdir(parents=True)
    script.write_text("param()", encoding="utf-8")
    calls: list[dict[str, object]] = []

    class FakeProcess:
        pid = 1234

    def fake_popen(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return FakeProcess()

    pid = learn_now_training.start_learn_now_training(
        tmp_path,
        "Textile",
        "micro",
        popen=fake_popen,
    )

    assert pid == 1234
    command = calls[0]["command"]
    assert isinstance(command, list)
    assert "start_learn_now_micro_train.ps1" in " ".join(command)
    assert "-ClassName" in command
    assert "Textile" in command
    assert "-Profile" in command
    assert "micro" in command
    assert calls[0]["cwd"] == tmp_path


def test_build_training_status_reports_latest_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(learn_now_training, "training_processes", lambda: [])
    run = tmp_path / "runs" / "train" / "learn-now-micro-textile-stage2"
    weights = run / "weights"
    weights.mkdir(parents=True)
    (weights / "best.pt").write_bytes(b"model")
    (run / "args.yaml").write_text("epochs: 6\nmodel: models/best.pt\n", encoding="utf-8")
    (run / "results.csv").write_text(
        "epoch,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "5,0.8,0.7,0.75,0.4\n",
        encoding="utf-8",
    )

    status = learn_now_training.build_training_status(tmp_path)

    assert status["running"] is False
    assert status["run_name"] == "learn-now-micro-textile-stage2"
    assert status["best_model_path"] == str(weights / "best.pt")
    assert status["completed_epoch"] == 6
    assert status["target_epoch"] == 6
    assert status["map50"] == 0.75


def test_build_training_status_handles_no_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(learn_now_training, "training_processes", lambda: [])

    status = learn_now_training.build_training_status(tmp_path)

    assert status["running"] is False
    assert status["best_model_path"] == ""
    assert "run" in str(status["message"]).lower()
