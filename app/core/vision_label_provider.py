"""Label suggestions for unknown learn-now camera captures."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.vision_label_openai import openai_label_candidates
from app.core.waste_categories import (
    TRAINING_CLASS_ORDER_45,
    canonical_class_name,
    category_for_class,
    default_class_id_for_name,
)

MAX_SUGGESTIONS = 3


@dataclass(frozen=True)
class VisionLabelSuggestion:
    label: str
    canonical_class: str
    class_id: int
    confidence: float
    command: str
    bin_index: int
    route_label: str
    source: str
    reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def suggest_unknown_labels(
    *,
    image_path: Path | None = None,
    manual_hint: str = "",
) -> dict[str, object]:
    """Return canonical 45-class suggestions from configured AI or manual hint."""
    suggestions: list[VisionLabelSuggestion] = []
    provider = "manual_alias"
    available = False
    message = "Enter a Vietnamese alias or configure VISION_LABEL_COMMAND for AI suggestions."

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key and image_path is not None:
        provider = "openai"
        available = True
        suggestions = _openai_suggestions(api_key, image_path)
        message = (
            "OpenAI vision provider returned canonical suggestions."
            if suggestions
            else "OpenAI vision provider returned no 45-class suggestions."
        )

    command = os.getenv("VISION_LABEL_COMMAND", "").strip()
    if not suggestions and command and image_path is not None:
        provider = "command"
        available = True
        suggestions = _command_suggestions(command, image_path)
        message = "Command label provider returned canonical suggestions."

    if not suggestions and manual_hint.strip():
        alias_suggestion = _suggestion(manual_hint, "manual_alias", 0.92, "Approved alias candidate.")
        suggestions = [alias_suggestion] if alias_suggestion is not None else []
        message = "Manual alias was mapped to the 45-class taxonomy." if suggestions else (
            "Alias is not mapped to the 45-class taxonomy yet."
        )

    deduped = _dedupe(suggestions)
    return {
        "provider": provider,
        "available": available,
        "suggestions": [item.as_dict() for item in deduped],
        "message": message,
    }


def _openai_suggestions(api_key: str, image_path: Path) -> list[VisionLabelSuggestion]:
    out: list[VisionLabelSuggestion] = []
    for index, (label, confidence) in enumerate(openai_label_candidates(api_key, image_path)):
        suggestion = _suggestion(str(label), "openai", float(confidence), f"AI rank {index + 1}.")
        if suggestion is not None:
            out.append(suggestion)
    return out


def _command_suggestions(command: str, image_path: Path) -> list[VisionLabelSuggestion]:
    env = os.environ.copy()
    env["VISION_LABEL_IMAGE_PATH"] = str(image_path)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
            shell=True,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = result.stdout.splitlines()
    labels = payload.get("labels") if isinstance(payload, dict) else payload
    if not isinstance(labels, list):
        return []
    out: list[VisionLabelSuggestion] = []
    for index, raw in enumerate(labels[:8]):
        label = raw.get("label") if isinstance(raw, dict) else str(raw)
        confidence = raw.get("confidence", 0.8) if isinstance(raw, dict) else 0.8
        suggestion = _suggestion(str(label), "command", float(confidence), f"AI rank {index + 1}.")
        if suggestion is not None:
            out.append(suggestion)
    return out


def _suggestion(
    label: str,
    source: str,
    confidence: float,
    reason: str,
) -> VisionLabelSuggestion | None:
    canonical = canonical_class_name(label)
    if canonical not in TRAINING_CLASS_ORDER_45:
        return None
    class_id = default_class_id_for_name(canonical)
    if class_id is None:
        return None
    category = category_for_class(canonical)
    return VisionLabelSuggestion(
        label=str(label).strip(),
        canonical_class=canonical,
        class_id=class_id,
        confidence=max(0.0, min(1.0, confidence)),
        command=category.code,
        bin_index=category.bin_index,
        route_label=category.name,
        source=source,
        reason=reason,
    )


def _dedupe(items: list[VisionLabelSuggestion]) -> list[VisionLabelSuggestion]:
    seen: set[str] = set()
    out: list[VisionLabelSuggestion] = []
    for item in sorted(items, key=lambda row: row.confidence, reverse=True):
        if item.canonical_class in seen:
            continue
        seen.add(item.canonical_class)
        out.append(item)
        if len(out) >= MAX_SUGGESTIONS:
            break
    return out


__all__ = ["VisionLabelSuggestion", "suggest_unknown_labels"]
