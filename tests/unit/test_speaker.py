import app.core.speaker as speaker_module
from app.core.speaker import WasteSpeaker
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
