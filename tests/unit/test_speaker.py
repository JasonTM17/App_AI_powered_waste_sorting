import app.core.speaker as speaker_module
from app.core.speaker import WasteSpeaker
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
    monkeypatch.setattr(speaker_module, "sort_voice_path", lambda _command: None)
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=0.0)
    monkeypatch.setattr(speaker, "_speak_background", lambda text: events.append(text))

    speaker.speak(command="O", bin_index=1, cls_name="Organic", confidence=0.91)

    assert events == [category_for_command("O").voice_text]


def test_waste_speaker_cooldown_blocks_duplicate_announcements(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(speaker_module, "sort_voice_path", lambda _command: None)
    monkeypatch.setattr(speaker_module.threading, "Thread", _ImmediateThread)

    speaker = WasteSpeaker(enabled=True, cooldown_seconds=60.0)
    monkeypatch.setattr(speaker, "_speak_background", lambda text: events.append(text))

    speaker.speak(command="O", bin_index=1, cls_name="Organic", confidence=0.91)
    speaker.speak(command="O", bin_index=1, cls_name="Organic", confidence=0.91)

    assert events == [category_for_command("O").voice_text]
