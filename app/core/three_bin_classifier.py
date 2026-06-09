"""Gated three-bin classifier fallback for stable unknown-object crops."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.core.image_embedding import LegacyImageEmbedder, cosine_similarity
from app.core.waste_categories import category_for_command
from app.utils.logging import logger
from app.utils.paths import resource_path

THREE_BIN_COMMANDS = ("O", "R", "I")
THREE_BIN_CLASS_NAMES = {
    "O": "Kaggle 3-bin O",
    "R": "Kaggle 3-bin R",
    "I": "Kaggle 3-bin I",
}
THREE_BIN_CLASS_IDS = {"O": -301, "R": -302, "I": -303}
THREE_BIN_SOURCE = "kaggle_three_bin_classifier"


@dataclass(frozen=True)
class ThreeBinPrediction:
    command: str
    cls_id: int
    cls_name: str
    confidence: float
    margin: float
    passed: bool
    probabilities: dict[str, float]
    backend: str
    detail_label: str = ""


class ThreeBinClassifier:
    def __init__(
        self,
        model_path: Path | str,
        *,
        enabled: bool = True,
        min_confidence: float = 0.72,
        min_margin: float = 0.12,
        min_crop_area_ratio: float = 0.003,
        input_size: int = 224,
    ) -> None:
        self.model_path = Path(model_path)
        self.enabled = bool(enabled)
        self.min_confidence = float(min_confidence)
        self.min_margin = float(min_margin)
        self.min_crop_area_ratio = float(min_crop_area_ratio)
        self.input_size = int(input_size)
        self.backend = ""
        self.message = "disabled" if not self.enabled else "not loaded"
        self._artifact: dict[str, Any] = {}
        self._model: Any | None = None
        self._torch: Any | None = None
        self._transform: Any | None = None
        self._embedder = LegacyImageEmbedder()
        self._loaded = False

    @property
    def ready(self) -> bool:
        return self.enabled and self._loaded

    def status(self) -> dict[str, object]:
        resolved = _resolve_model_path(self.model_path)
        return {
            "enabled": self.enabled,
            "ready": self.ready,
            "model_path": str(resolved),
            "exists": resolved.exists(),
            "backend": self.backend,
            "message": self.message,
        }

    def classify_bgr(
        self,
        frame_bgr: np.ndarray,
        xyxy: tuple[int, int, int, int],
    ) -> ThreeBinPrediction | None:
        if not self.enabled:
            return None
        if not self._ensure_loaded():
            return None
        crop = _rgb_crop_from_bgr(frame_bgr, xyxy)
        if crop is None:
            return None
        frame_area = max(1, int(frame_bgr.shape[0]) * int(frame_bgr.shape[1]))
        crop_area = int(crop.shape[0]) * int(crop.shape[1])
        if crop_area / float(frame_area) < self.min_crop_area_ratio:
            return None
        return self.classify_rgb(crop)

    def classify_rgb(self, rgb: np.ndarray) -> ThreeBinPrediction | None:
        if not self.enabled or not self._ensure_loaded() or rgb.size == 0:
            return None
        if self.backend == "torchvision_mobilenet_v3_small":
            probabilities = self._predict_torch(rgb)
        else:
            probabilities = self._predict_centroid(rgb)
        if not probabilities:
            return None
        ranked = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
        command, confidence = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = float(confidence - runner_up)
        passed = confidence >= self.min_confidence and margin >= self.min_margin
        return ThreeBinPrediction(
            command=command,
            cls_id=THREE_BIN_CLASS_IDS[command],
            cls_name=THREE_BIN_CLASS_NAMES[command],
            confidence=float(confidence),
            margin=margin,
            passed=passed,
            probabilities={key: float(value) for key, value in probabilities.items()},
            backend=self.backend,
            detail_label=str(self._artifact.get("detail_label") or ""),
        )

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return True
        path = _resolve_model_path(self.model_path)
        if not path.exists():
            self.message = f"missing artifact: {path}"
            return False
        try:
            if path.suffix.lower() == ".json":
                self._load_json(path)
            else:
                self._load_torch(path)
            self._loaded = True
            self.message = f"loaded {self.backend}"
            return True
        except Exception as exc:
            self.message = f"load failed: {exc}"
            logger.warning("three-bin classifier load failed {}: {}", path, exc)
            return False

    def _load_json(self, path: Path) -> None:
        artifact = json.loads(path.read_text(encoding="utf-8"))
        centroids = artifact.get("centroids")
        if not isinstance(centroids, dict):
            raise ValueError("JSON artifact missing centroids")
        self._artifact = artifact
        self.backend = str(artifact.get("backend") or artifact.get("embedder") or "legacy_centroid")

    def _load_torch(self, path: Path) -> None:
        import torch
        from torchvision import transforms
        from torchvision.models import mobilenet_v3_small

        try:
            artifact = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            artifact = torch.load(path, map_location="cpu")
        if not isinstance(artifact, dict):
            raise ValueError("torch artifact must be a dictionary")
        model_type = str(artifact.get("model_type") or "")
        if model_type != "torchvision_mobilenet_v3_small":
            raise ValueError(f"unsupported classifier model_type: {model_type}")
        classes = tuple(str(item) for item in artifact.get("classes") or THREE_BIN_COMMANDS)
        if classes != THREE_BIN_COMMANDS:
            raise ValueError(f"unsupported classifier classes: {classes}")
        input_size = int(artifact.get("input_size") or self.input_size)
        model = mobilenet_v3_small(weights=None)
        in_features = model.classifier[-1].in_features
        model.classifier[-1] = torch.nn.Linear(in_features, len(THREE_BIN_COMMANDS))
        model.load_state_dict(artifact["model_state"])
        model.eval().cpu()
        self._torch = torch
        self._model = model
        self._transform = transforms.Compose(
            [
                transforms.Resize((input_size, input_size)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                ),
            ]
        )
        self._artifact = artifact
        self.input_size = input_size
        self.backend = model_type

    def _predict_torch(self, rgb: np.ndarray) -> dict[str, float]:
        if self._torch is None or self._model is None or self._transform is None:
            return {}
        image = Image.fromarray(np.asarray(rgb, dtype=np.uint8))
        tensor = self._transform(image).unsqueeze(0)
        with self._torch.inference_mode():
            logits = self._model(tensor)
            probs = self._torch.softmax(logits, dim=1)[0].cpu().numpy()
        return {command: float(probs[index]) for index, command in enumerate(THREE_BIN_COMMANDS)}

    def _predict_centroid(self, rgb: np.ndarray) -> dict[str, float]:
        query = self._embedder.embed(rgb)
        if query is None:
            return {}
        centroids = self._artifact.get("centroids") or {}
        scores = {}
        for command in THREE_BIN_COMMANDS:
            raw = centroids.get(command)
            if not isinstance(raw, list):
                continue
            centroid = np.asarray(raw, dtype=np.float32)
            scores[command] = max(0.0, cosine_similarity(query, centroid))
        total = sum(scores.values())
        if total <= 1e-9:
            return {}
        return {command: score / total for command, score in scores.items()}


def parse_three_bin_class_name(cls_name: str) -> str | None:
    clean = str(cls_name or "").strip().upper()
    for command, class_name in THREE_BIN_CLASS_NAMES.items():
        if clean == class_name.upper():
            return command
    if clean in THREE_BIN_COMMANDS:
        return clean
    return None


def three_bin_route(command: str):
    return category_for_command(command.strip().upper())


def _resolve_model_path(path: Path) -> Path:
    return path if path.is_absolute() else resource_path(path)


def _rgb_crop_from_bgr(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> np.ndarray | None:
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3:
        return None
    height, width = frame_bgr.shape[:2]
    x1, y1, x2, y2 = xyxy
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(x1 + 1, min(int(x2), width))
    y2 = max(y1 + 1, min(int(y2), height))
    crop = frame_bgr[y1:y2, x1:x2, :3][:, :, ::-1]
    return np.ascontiguousarray(crop)


__all__ = [
    "THREE_BIN_CLASS_IDS",
    "THREE_BIN_CLASS_NAMES",
    "THREE_BIN_COMMANDS",
    "THREE_BIN_SOURCE",
    "ThreeBinClassifier",
    "ThreeBinPrediction",
    "parse_three_bin_class_name",
    "three_bin_route",
]
