"""Small non-blocking speaker helper for sorter announcements."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Protocol

from app.core.voice_pack import sort_voice_path, warning_voice_path
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

    def speak_text(self, *, text: str, key: str, cooldown_seconds: float | None = None) -> None:
        """Announce a warning/status text without implying a sort completed."""


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

    def speak_text(self, *, text: str, key: str, cooldown_seconds: float | None = None) -> None:
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
        self._queue(
            text=category.voice_text,
            key=category.code,
            audio_path=sort_voice_path(category.code),
            cooldown_seconds=None,
            require_enabled=True,
        )
        logger.info(
            "speaker queued cls={} cmd={} bin={} conf={:.2f}",
            cls_name,
            category.code,
            bin_index,
            confidence,
        )

    def speak_text(self, *, text: str, key: str, cooldown_seconds: float | None = None) -> None:
        self._queue(
            text=text,
            key=key,
            audio_path=warning_voice_path(key),
            cooldown_seconds=cooldown_seconds,
            require_enabled=True,
        )

    def preview_command(self, command: str) -> bool:
        category = category_for_command(command)
        if category is None:
            return False
        self._queue(
            text=category.voice_text,
            key=f"preview:{category.code}",
            audio_path=sort_voice_path(category.code),
            cooldown_seconds=0.0,
            require_enabled=False,
        )
        return True

    def preview_warning(self) -> bool:
        self._queue(
            text="Chỉ đặt một loại rác trong khay.",
            key="preview:multi_class_dispatch_blocked",
            audio_path=warning_voice_path("multi_class_dispatch_blocked"),
            cooldown_seconds=0.0,
            require_enabled=False,
        )
        return True

    def _queue(
        self,
        *,
        text: str,
        key: str,
        audio_path: Path | None,
        cooldown_seconds: float | None,
        require_enabled: bool,
    ) -> None:
        if require_enabled and not self.enabled:
            return
        clean_text = str(text or "").strip()
        if not clean_text:
            return
        clean_key = str(key or "").strip() or clean_text
        cooldown = self.cooldown_seconds if cooldown_seconds is None else max(0.0, float(cooldown_seconds))
        now = time.monotonic()
        with self._lock:
            previous = self._last_spoken_at.get(clean_key, 0.0)
            if now - previous < cooldown:
                return
            self._last_spoken_at[clean_key] = now
        thread = threading.Thread(
            target=self._play_background,
            args=(clean_text, audio_path),
            name="trash-sorter-speaker",
            daemon=True,
        )
        thread.start()
        logger.info("speaker queued key={} text={} audio={}", clean_key, clean_text, audio_path or "")

    def _play_background(self, text: str, audio_path: Path | None) -> None:
        if audio_path is not None and audio_path.exists():
            try:
                self._play_audio_file(audio_path)
                return
            except Exception as e:
                logger.warning("speaker mp3 failed, falling back to TTS: {}", e)
        self._speak_background(text)

    def _play_audio_file(self, audio_path: Path) -> None:
        if sys.platform != "win32":
            logger.info("speaker audio file: {}", audio_path)
            return
        env = os.environ.copy()
        env["TRASH_SORTER_AUDIO_PATH"] = str(audio_path)
        script = (
            "$path = $env:TRASH_SORTER_AUDIO_PATH; "
            "Add-Type -AssemblyName PresentationCore; "
            "$player = New-Object System.Windows.Media.MediaPlayer; "
            "$player.Open([Uri]::new($path)); "
            "$player.Volume = 1.0; "
            "$player.Play(); "
            "$deadline = (Get-Date).AddSeconds(8); "
            "while (-not $player.NaturalDuration.HasTimeSpan -and (Get-Date) -lt $deadline) "
            "{ Start-Sleep -Milliseconds 50 }; "
            "if ($player.NaturalDuration.HasTimeSpan) { "
            "$ms = [Math]::Min($player.NaturalDuration.TimeSpan.TotalMilliseconds + 200, 8000); "
            "Start-Sleep -Milliseconds ([int]$ms) "
            "} else { Start-Sleep -Milliseconds 2500 }; "
            "$player.Stop(); $player.Close()"
        )
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-Sta",
                "-Command",
                script,
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            raise RuntimeError(f"PowerShell MediaPlayer exited {result.returncode}")

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
