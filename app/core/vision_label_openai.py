"""Optional OpenAI vision label provider for cropped unknown objects."""

from __future__ import annotations

import json
import os
from base64 import b64encode
from pathlib import Path

import httpx

from app.core.waste_categories import TRAINING_CLASS_ORDER_45


def openai_label_candidates(api_key: str, image_path: Path) -> list[tuple[str, float]]:
    try:
        data_url = _image_data_url(image_path)
    except OSError:
        return []
    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini"
    prompt = (
        "Identify this cropped waste object. Return JSON only as "
        '{"labels":[{"label":"Vietnamese or English name","confidence":0.0}]}. '
        "Use only labels that can map to this taxonomy: "
        + ", ".join(TRAINING_CLASS_ORDER_45)
        + ". Examples: but bi=Pen, vi thuoc=Unknown plastic, khau trang=Textile."
    )
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": "low"},
                ],
            }
        ],
        "max_output_tokens": 300,
    }
    try:
        with httpx.Client(timeout=30) as client:
            res = client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
            )
            res.raise_for_status()
            return _parse_candidates(_response_text(res.json()))
    except (httpx.HTTPError, json.JSONDecodeError):
        return []


def _image_data_url(image_path: Path) -> str:
    raw = image_path.read_bytes()
    suffix = image_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
    return f"data:{mime};base64,{b64encode(raw).decode('ascii')}"


def _response_text(payload: dict[str, object]) -> str:
    if isinstance(payload.get("output_text"), str):
        return str(payload["output_text"])
    chunks: list[str] = []
    output_items = payload.get("output")
    for output in output_items if isinstance(output_items, list) else []:
        content = output.get("content") if isinstance(output, dict) else None
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(str(part["text"]))
    return "\n".join(chunks)


def _parse_candidates(raw: str) -> list[tuple[str, float]]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        return []
    out: list[tuple[str, float]] = []
    for row in labels[:8]:
        label = row.get("label") if isinstance(row, dict) else str(row)
        confidence = row.get("confidence", 0.8) if isinstance(row, dict) else 0.8
        out.append((str(label), float(confidence)))
    return out


__all__ = ["openai_label_candidates"]
