"""Image embeddings for conservative manual-reference recognition."""

from __future__ import annotations

import os
from typing import Any, Protocol

import numpy as np
from PIL import Image

from app.utils.logging import logger


class ImageEmbedder(Protocol):
    @property
    def name(self) -> str: ...

    def embed(self, rgb: np.ndarray) -> np.ndarray | None: ...


class LegacyImageEmbedder:
    """Small deterministic fallback used when pretrained weights are unavailable."""

    @property
    def name(self) -> str:
        return "legacy"

    def embed(self, rgb: np.ndarray) -> np.ndarray | None:
        if rgb.size == 0:
            return None
        image = Image.fromarray(np.asarray(rgb, dtype=np.uint8)).resize((32, 32))
        arr = np.asarray(image).astype(np.float32) / 255.0
        hist = np.concatenate(
            [
                np.histogram(arr[:, :, channel], bins=16, range=(0.0, 1.0), density=True)[0]
                for channel in range(3)
            ]
        ).astype(np.float32)
        return _normalize(np.concatenate([arr.reshape(-1) * 0.35, hist * 0.65]))


class MobileNetV3SmallEmbedder:
    """Lazy pretrained MobileNet features with a deterministic offline fallback."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._transform: Any | None = None
        self._torch: Any | None = None
        self._attempted = False
        self._fallback = LegacyImageEmbedder()

    @property
    def name(self) -> str:
        return "mobilenet_v3_small" if self._model is not None else self._fallback.name

    def embed(self, rgb: np.ndarray) -> np.ndarray | None:
        self._ensure_loaded()
        if self._model is None or self._transform is None or self._torch is None:
            return self._fallback.embed(rgb)
        if rgb.size == 0:
            return None
        image = Image.fromarray(np.asarray(rgb, dtype=np.uint8))
        tensor = self._transform(image).unsqueeze(0)
        with self._torch.inference_mode():
            features = self._model.features(tensor)
            features = self._model.avgpool(features)
            vector = self._torch.flatten(features, 1)[0].cpu().numpy().astype(np.float32)
        return _normalize(vector)

    def _ensure_loaded(self) -> None:
        if self._attempted:
            return
        self._attempted = True
        try:
            import torch
            from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

            weights = MobileNet_V3_Small_Weights.DEFAULT
            model = mobilenet_v3_small(weights=weights)
            model.eval().cpu()
            self._torch = torch
            self._model = model
            self._transform = weights.transforms()
            logger.info("manual reference embedding backend loaded: MobileNetV3-Small")
        except Exception as exc:
            logger.warning("MobileNet reference embedding unavailable; using legacy: {}", exc)


def create_image_embedder() -> ImageEmbedder:
    requested = os.getenv("TRASH_SORTER_REFERENCE_EMBEDDER", "mobilenet").strip().lower()
    if requested in {"legacy", "off", "disabled"}:
        return LegacyImageEmbedder()
    return MobileNetV3SmallEmbedder()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return -1.0
    return float(np.clip(np.dot(a, b), -1.0, 1.0))


def _normalize(vector: np.ndarray) -> np.ndarray | None:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        return None
    return np.asarray(vector / norm, dtype=np.float32)


__all__ = [
    "ImageEmbedder",
    "LegacyImageEmbedder",
    "MobileNetV3SmallEmbedder",
    "cosine_similarity",
    "create_image_embedder",
]
