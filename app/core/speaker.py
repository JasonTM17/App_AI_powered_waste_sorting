"""Small non-blocking speaker helper for sorter announcements."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Protocol

from app.core.waste_categories import category_for_command
from app.utils.logging import logger


class Speaker(Protocol):
    def speak(
        self,
        *,
        command: str,
        bin_index: int,
        cls_name: str,
        confidence: float,
    ) -> None:
        """Announce a dispatched item without blocking inference."""


class NoopSpeaker:
    def speak(
        self,
        *,
        command: str,
        bin_index: int,
        cls_name: str,
        confidence: float,
    ) -> None:
        return


class WasteSpeaker:
    def __init__(self, *, enabled: bool = True, cooldown_seconds: float = 2.5):
        self.enabled = enabled
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._last_spoken_at: dict[str, float] = {}

    def configure(self, *, enabled: bool, cooldown_seconds: float) -> None:
        with self._lock:
            self.enabled = enabled
            self.cooldown_seconds = cooldown_seconds

    def speak(
        self,
        *,
        command: str,
        bin_index: int,
        cls_name: str,
        confidence: float,
    ) -> None:
        if not self.enabled:
            return
        category = category_for_command(command)
        if category is None:
            logger.debug("speaker skipped unknown command={} cls={}", command, cls_name)
            return
        now = time.monotonic()
        with self._lock:
            previous = self._last_spoken_at.get(category.code, 0.0)
            if now - previous < self.cooldown_seconds:
                return
            self._last_spoken_at[category.code] = now
        text = category.voice_text
        thread = threading.Thread(
            target=self._speak_background,
            args=(text,),
            name="trash-sorter-speaker",
            daemon=True,
        )
        thread.start()
        logger.info(
            "speaker queued cls={} cmd={} bin={} conf={:.2f}",
            cls_name,
            category.code,
            bin_index,
            confidence,
        )

    def _speak_background(self, text: str) -> None:
        if sys.platform != "win32":
            logger.info("speaker text: {}", text)
            return
        env = os.environ.copy()
        env["TRASH_SORTER_SPEECH_TEXT"] = text
        script = (
            "$text = $env:TRASH_SORTER_SPEECH_TEXT; "
            "Add-Type -AssemblyName System.Speech; "
            "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$speaker.Volume = 100; "
            "$speaker.Rate = 0; "
            "$speaker.Speak($text)"
        )
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-Command",
                    script,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
                creationflags=creationflags,
            )
        except Exception as e:
            logger.warning("speaker failed: {}", e)
