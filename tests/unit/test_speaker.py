import base64
import subprocess
import threading
import time
from pathlib import Path

import pytest

import app.core.speaker as speaker_module
from app.core.speaker import AudioPlaybackResult, WasteSpeaker
from app.core.voice_pack import AUDIO_EVENT_LABELS
from app.core.waste_categories import category_for_command


class _ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, **_):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target is not None:
            self._target(*self._args, **self._kwargs)


def test_waste_speaker_falls_back_to_tts_when_voice_file_missing(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(speaker_module, "sort_voice_path", lambda _command, _gender="female": None)
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=0.0)
    monkeypatch.setattr(speaker, "_speak_background", lambda text: events.append(text))

    speaker.speak(command="O", bin_index=1, cls_name="Organic", confidence=0.91)

    assert events == [category_for_command("O").voice_text]


def test_waste_speaker_cooldown_blocks_duplicate_announcements(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(speaker_module, "sort_voice_path", lambda _command, _gender="female": None)
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=60.0)
    monkeypatch.setattr(speaker, "_speak_background", lambda text: events.append(text))

    speaker.speak(command="O", bin_index=1, cls_name="Organic", confidence=0.91)
    speaker.speak(command="O", bin_index=1, cls_name="Organic", confidence=0.91)

    assert events == [category_for_command("O").voice_text]


def test_waste_speaker_passes_selected_voice_gender(monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        speaker_module,
        "sort_voice_path",
        lambda command, gender="female": calls.append((command, gender)) or None,
    )
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)
    speaker = WasteSpeaker(enabled=True, cooldown_seconds=0.0, voice_gender="male")
    monkeypatch.setattr(speaker, "_speak_background", lambda _text: None)

    speaker.speak(command="I", bin_index=3, cls_name="Paper", confidence=0.9)

    assert calls == [("I", "male")]


def test_waste_speaker_previews_all_audio_events(tmp_path, monkeypatch):
    played: list[tuple[str, str]] = []
    fake_audio = tmp_path / "voice.mp3"
    fake_audio.write_bytes(b"mp3")
    monkeypatch.setattr(speaker_module, "audio_event_path", lambda _event, _gender="female": fake_audio)
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)
    speaker = WasteSpeaker(enabled=False, cooldown_seconds=60.0, voice_gender="male")
    monkeypatch.setattr(
        speaker,
        "_play_background",
        lambda text, audio_path: played.append((text, str(audio_path))),
    )

    for event_key in AUDIO_EVENT_LABELS:
        assert speaker.preview_event(event_key) is True

    assert [item[0] for item in played] == [AUDIO_EVENT_LABELS[key] for key in AUDIO_EVENT_LABELS]
    assert {item[1] for item in played} == {str(fake_audio)}


def test_waste_speaker_audio_test_reports_real_playback_success(tmp_path, monkeypatch):
    fake_audio = tmp_path / "voice.mp3"
    fake_audio.write_bytes(b"mp3")
    played = []
    monkeypatch.setattr(speaker_module, "audio_event_path", lambda _event, _gender="female": fake_audio)
    speaker = WasteSpeaker(enabled=False, voice_gender="female")
    monkeypatch.setattr(speaker, "_play_audio_file", played.append)

    result = speaker.play_event_for_test("startup", voice_gender="male")

    assert result.ok is True
    assert result.audio_path == fake_audio
    assert played == [fake_audio]


def test_waste_speaker_audio_test_reports_playback_failure(tmp_path, monkeypatch):
    fake_audio = tmp_path / "voice.mp3"
    fake_audio.write_bytes(b"mp3")
    monkeypatch.setattr(speaker_module, "audio_event_path", lambda _event, _gender="female": fake_audio)
    speaker = WasteSpeaker(enabled=False)

    def fail_playback(_audio_path):
        raise RuntimeError("decoder unavailable")

    monkeypatch.setattr(speaker, "_play_audio_file", fail_playback)

    result = speaker.play_event_for_test("startup")

    assert result.ok is False
    assert result.audio_path == fake_audio
    assert "decoder unavailable" in result.message


def test_completion_beep_plays_exactly_once_per_trial(monkeypatch):
    events = []
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)
    speaker = WasteSpeaker(enabled=False)
    monkeypatch.setattr(speaker, "_play_completion_tone", lambda: events.append("beep"))

    assert speaker.play_completion_beep("trial-1") is True
    assert speaker.play_completion_beep("trial-1") is False
    assert speaker.play_completion_beep("trial-2") is True
    assert events == ["beep", "beep"]


def test_waste_speaker_serializes_different_announcements(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    order: list[str] = []
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=0.0)

    def play(text, _audio_path):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
            order.append(text)
        if len(order) == 1:
            started.set()
            assert release.wait(2)
        with state_lock:
            active -= 1
            if len(order) == 2:
                finished.set()

    monkeypatch.setattr(speaker, "_play_background", play)
    speaker.speak_text(text="first", key="first", cooldown_seconds=0)
    assert started.wait(2)
    speaker.speak_text(text="second", key="second", cooldown_seconds=0)
    time.sleep(0.05)

    assert max_active == 1
    assert order == ["first"]

    release.set()
    assert finished.wait(2)
    assert order == ["first", "second"]
    assert max_active == 1


def test_waste_speaker_clears_pending_audio_when_switched_to_hardware(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    order: list[str] = []

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=0.0)

    def play(text, _audio_path):
        order.append(text)
        if len(order) == 1:
            started.set()
            assert release.wait(2)
        finished.set()

    monkeypatch.setattr(speaker, "_play_background", play)
    speaker.speak_text(text="first", key="first", cooldown_seconds=0)
    assert started.wait(2)
    speaker.speak_text(text="second", key="second", cooldown_seconds=0)

    speaker.configure(enabled=False, cooldown_seconds=0.0, voice_gender="female")
    release.set()

    assert finished.wait(2)
    assert order == ["first"]


def test_waste_speaker_stops_active_laptop_process_when_switched_to_hardware():
    class _FakeProcess:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=0.0)
    process = _FakeProcess()
    speaker._active_process = process

    speaker.configure(enabled=False, cooldown_seconds=0.0, voice_gender="female")

    assert process.terminated is True


def test_play_event_for_test_reports_missing_audio(monkeypatch):
    monkeypatch.setattr(speaker_module, "audio_event_path", lambda _event, _gender: None)
    speaker = WasteSpeaker(enabled=False)

    result = speaker.play_event_for_test("startup", voice_gender="female")

    assert result == AudioPlaybackResult(False, "Missing laptop audio file for startup.")


def test_windows_media_player_uses_encoded_command_and_waits_for_events(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"mp3")

    class _Process:
        returncode = 0

        def communicate(self, timeout=None):
            return ("", "")

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Process()

    monkeypatch.setattr(speaker_module.sys, "platform", "win32")
    monkeypatch.setattr(speaker_module.subprocess, "Popen", fake_popen)
    speaker = WasteSpeaker(enabled=False)

    speaker._play_audio_file(audio_path)

    command = captured["command"]
    assert isinstance(command, list)
    encoded = command[command.index("-EncodedCommand") + 1]
    script = base64.b64decode(encoded).decode("utf-16le")
    assert "add_MediaOpened" in script
    assert "add_MediaFailed" in script
    assert "add_MediaEnded" in script
    assert command[-2] == "-EncodedCommand"
    assert captured["kwargs"]["stderr"] == subprocess.PIPE


def test_powershell_failure_redacts_audio_path(monkeypatch):
    secret_path = Path(r"C:\private\voice.mp3")

    class _Process:
        returncode = 7

        def communicate(self, timeout=None):
            return ("", f"cannot open {secret_path}")

    monkeypatch.setattr(speaker_module.subprocess, "Popen", lambda *_args, **_kwargs: _Process())
    speaker = WasteSpeaker(enabled=False)

    with pytest.raises(RuntimeError) as exc_info:
        speaker._run_powershell_script(
            "throw 'failed'",
            env={"TRASH_SORTER_AUDIO_PATH": str(secret_path)},
            timeout_seconds=1,
            label="PowerShell MediaPlayer",
        )

    assert str(secret_path) not in str(exc_info.value)
    assert "<redacted-path>" in str(exc_info.value)


def test_powershell_timeout_kills_process(monkeypatch):
    class _Process:
        returncode = None

        def __init__(self):
            self.killed = False
            self.calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.killed:
                self.returncode = -9
                return ("", "stopped")
            raise subprocess.TimeoutExpired("powershell.exe", timeout)

        def kill(self):
            self.killed = True

    process = _Process()
    monotonic = iter((0.0, 2.0))
    monkeypatch.setattr(speaker_module.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(speaker_module.time, "monotonic", lambda: next(monotonic))
    speaker = WasteSpeaker(enabled=False)

    with pytest.raises(RuntimeError, match="timed out"):
        speaker._run_powershell_script(
            "Start-Sleep -Seconds 5",
            env={},
            timeout_seconds=1,
            label="PowerShell MediaPlayer",
        )

    assert process.killed is True
