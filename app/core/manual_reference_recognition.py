"""Conservative immediate recognition from reviewed manual samples."""

from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

import numpy as np
from PIL import Image

from app.core.dataset_trust import classify_dataset_item
from app.core.events import Detection
from app.core.image_embedding import (
    ImageEmbedder,
    cosine_similarity,
    create_image_embedder,
)
from app.utils.logging import logger

MANUAL_REFERENCE_SOURCES = {
    "manual_camera_capture",
    "manual_import",
    "manual_phone_import",
    "manual_web_import",
}


@dataclass(frozen=True)
class ManualReferenceMatch:
    cls_id: int
    cls_name: str
    similarity: float
    image_path: str
    votes: int = 0
    margin: float = 0.0
    backend: str = ""


@dataclass(frozen=True)
class _Reference:
    cls_id: int
    cls_name: str
    image_path: Path
    vector: np.ndarray


class ManualReferenceRecognizer:
    def __init__(
        self,
        queue_dir: Path,
        *,
        enabled: bool = True,
        min_similarity: float = 0.82,
        min_consensus_similarity: float = 0.55,
        min_margin: float = 0.04,
        top_k: int = 5,
        min_votes: int = 3,
        max_references_per_class: int = 30,
        refresh_seconds: float = 30.0,
        query_cache_seconds: float = 1.0,
        embedder: ImageEmbedder | None = None,
    ) -> None:
        self.queue_dir = queue_dir
        self.embedder = embedder or create_image_embedder()
        self._lock = RLock()
        self._references: list[_Reference] = []
        self._last_refresh = 0.0
        self._last_signature: tuple[int, float] = (0, 0.0)
        self._query_cache: dict[int, tuple[float, ManualReferenceMatch | None]] = {}
        self.configure(
            enabled=enabled,
            min_similarity=min_similarity,
            min_consensus_similarity=min_consensus_similarity,
            min_margin=min_margin,
            top_k=top_k,
            min_votes=min_votes,
            max_references_per_class=max_references_per_class,
            refresh_seconds=refresh_seconds,
            query_cache_seconds=query_cache_seconds,
            refresh=False,
        )

    @property
    def reference_count(self) -> int:
        with self._lock:
            return len(self._references)

    def configure(
        self,
        *,
        enabled: bool,
        min_similarity: float,
        min_consensus_similarity: float,
        min_margin: float,
        top_k: int,
        min_votes: int,
        max_references_per_class: int,
        refresh_seconds: float,
        query_cache_seconds: float,
        refresh: bool = True,
    ) -> None:
        with self._lock:
            self.enabled = bool(enabled)
            self.min_similarity = float(min_similarity)
            self.min_consensus_similarity = float(min_consensus_similarity)
            self.min_margin = float(min_margin)
            self.top_k = max(1, int(top_k))
            self.min_votes = max(1, min(int(min_votes), self.top_k))
            self.max_references_per_class = max(1, int(max_references_per_class))
            self.refresh_seconds = max(0.0, float(refresh_seconds))
            self.query_cache_seconds = max(0.0, float(query_cache_seconds))
        if refresh:
            self.refresh(force=True)

    def refresh_if_needed(self) -> None:
        with self._lock:
            should_refresh = self.enabled and time.monotonic() - self._last_refresh >= self.refresh_seconds
        if should_refresh:
            self.refresh()

    def refresh(self, *, force: bool = False) -> None:
        now = time.monotonic()
        signature = self._signature()
        with self._lock:
            self._last_refresh = now
            if not force and signature == self._last_signature:
                return
            self._last_signature = signature
        references = self._load_references()
        with self._lock:
            self._references = references
            self._query_cache.clear()

    def classify(self, frame_bgr: np.ndarray, detection: Detection) -> ManualReferenceMatch | None:
        with self._lock:
            enabled = self.enabled
        if not enabled:
            return None
        self.refresh_if_needed()
        crops = _candidate_rgb_crops_from_bgr(frame_bgr, detection.xyxy)
        with self._lock:
            references = tuple(self._references)
        if not crops or not references:
            return None
        now = time.monotonic()
        best_match: ManualReferenceMatch | None = None
        for crop in crops:
            match = self._classify_crop(crop, now, references)
            if match is None:
                continue
            if best_match is None or match.similarity > best_match.similarity:
                best_match = match
        return best_match

    def _classify_crop(
        self,
        crop: np.ndarray,
        now: float,
        references: tuple[_Reference, ...],
    ) -> ManualReferenceMatch | None:
        cache_key = _difference_hash(crop)
        cache_hit, cached = self._cached_match(cache_key, now)
        if cache_hit:
            return cached
        query = self.embedder.embed(crop)
        if query is None:
            self._store_cached_match(cache_key, None, now)
            return None
        with self._lock:
            top_k = self.top_k
            min_votes = self.min_votes
            min_similarity = self.min_similarity
            min_consensus_similarity = self.min_consensus_similarity
            min_margin = self.min_margin
        ranked = sorted(
            ((reference, cosine_similarity(query, reference.vector)) for reference in references),
            key=lambda item: item[1],
            reverse=True,
        )[:top_k]
        votes = Counter(reference.cls_name for reference, _score in ranked)
        if not votes:
            return None
        winner_name, winner_votes = votes.most_common(1)[0]
        if winner_votes < min_votes:
            self._store_cached_match(cache_key, None, now)
            return None
        class_scores: dict[str, list[float]] = defaultdict(list)
        for reference, score in ranked:
            class_scores[reference.cls_name].append(score)
        winner_scores = sorted(class_scores[winner_name], reverse=True)
        best_score = winner_scores[0]
        consensus_score = winner_scores[min_votes - 1]
        winner_score = float(np.mean(winner_scores[:min_votes]))
        runner_up = max(
            (float(np.mean(scores)) for name, scores in class_scores.items() if name != winner_name),
            default=-1.0,
        )
        margin = winner_score - runner_up if runner_up >= 0 else 1.0
        if (
            best_score < min_similarity
            or consensus_score < min_consensus_similarity
            or margin < min_margin
        ):
            self._store_cached_match(cache_key, None, now)
            return None
        best_reference, _ = next(
            item for item in ranked if item[0].cls_name == winner_name
        )
        match = ManualReferenceMatch(
            cls_id=best_reference.cls_id,
            cls_name=winner_name,
            similarity=best_score,
            image_path=str(best_reference.image_path),
            votes=winner_votes,
            margin=margin,
            backend=self.embedder.name,
        )
        self._store_cached_match(cache_key, match, now)
        return match

    def _cached_match(
        self,
        cache_key: int,
        now: float,
    ) -> tuple[bool, ManualReferenceMatch | None]:
        with self._lock:
            if self.query_cache_seconds <= 0:
                return False, None
            expired = [
                key
                for key, (created_at, _match) in self._query_cache.items()
                if now - created_at > self.query_cache_seconds
            ]
            for key in expired:
                self._query_cache.pop(key, None)
            for key, (_created_at, match) in self._query_cache.items():
                if (key ^ cache_key).bit_count() <= 4:
                    return True, match
        return False, None

    def _store_cached_match(
        self,
        cache_key: int,
        match: ManualReferenceMatch | None,
        now: float,
    ) -> None:
        with self._lock:
            if self.query_cache_seconds <= 0:
                return
            if len(self._query_cache) >= 32:
                oldest = min(self._query_cache, key=lambda key: self._query_cache[key][0])
                self._query_cache.pop(oldest, None)
            self._query_cache[cache_key] = (now, match)

    def _signature(self) -> tuple[int, float]:
        if not self.queue_dir.exists():
            return (0, 0.0)
        files = list(_manual_meta_files(self.queue_dir))
        latest = max((_mtime(path) for path in files), default=0.0)
        return (len(files), latest)

    def _load_references(self) -> list[_Reference]:
        references: list[_Reference] = []
        per_class: Counter[str] = Counter()
        for meta_file in sorted(_manual_meta_files(self.queue_dir), key=_mtime, reverse=True):
            meta = _read_meta(meta_file)
            if not _can_use_as_reference(meta):
                continue
            image_path = meta_file.with_suffix(".jpg")
            if not image_path.exists():
                continue
            try:
                with Image.open(image_path) as image:
                    rgb = image.convert("RGB")
                    for box in meta.get("boxes") or []:
                        cls_name, cls_id = _canonical_reference_label(
                            box.get("cls_name"),
                            box.get("cls_id"),
                        )
                        if not cls_name or per_class[cls_name] >= self.max_references_per_class:
                            continue
                        vector = _embedding_from_pil_crop(
                            self.embedder,
                            rgb,
                            box.get("xyxy") or [],
                        )
                        if vector is None:
                            continue
                        references.append(
                            _Reference(
                                cls_id=cls_id,
                                cls_name=cls_name,
                                image_path=image_path,
                                vector=vector,
                            )
                        )
                        per_class[cls_name] += 1
            except Exception as exc:
                logger.debug("manual reference load skipped {}: {}", image_path, exc)
        logger.info(
            "manual reference recognizer loaded {} references with {}",
            len(references),
            self.embedder.name,
        )
        return references


def _can_use_as_reference(meta: dict) -> bool:
    source = str(meta.get("source") or "")
    if source not in MANUAL_REFERENCE_SOURCES:
        return False
    if not classify_dataset_item(meta).trainable or meta.get("reviewed") is not True:
        return False
    if meta.get("holdout") is True:
        return False
    return bool(meta.get("recognition_enabled", True))


def _canonical_reference_label(cls_name: object, cls_id: object) -> tuple[str, int]:
    from app.core.waste_categories import canonical_class_name, default_class_id_for_name

    raw_name = str(cls_name or "").strip()
    class_name = canonical_class_name(raw_name) or raw_name
    try:
        fallback_id = int(str(cls_id).strip())
    except (TypeError, ValueError):
        fallback_id = 0
    known_id = default_class_id_for_name(class_name)
    return class_name, fallback_id if known_id is None else known_id


def _rgb_crop_from_bgr(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> np.ndarray | None:
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3:
        return None
    x1, y1, x2, y2 = _clamp_box(xyxy, frame_bgr.shape[1], frame_bgr.shape[0])
    crop = frame_bgr[y1:y2, x1:x2, :3][:, :, ::-1]
    return np.ascontiguousarray(crop)


def _candidate_rgb_crops_from_bgr(
    frame_bgr: np.ndarray,
    xyxy: tuple[int, int, int, int],
) -> list[np.ndarray]:
    if frame_bgr.ndim != 3 or frame_bgr.shape[2] < 3:
        return []
    height, width = frame_bgr.shape[:2]
    crops: list[np.ndarray] = []
    seen: set[tuple[int, int, int, int]] = set()
    for box in _candidate_crop_boxes(xyxy, width, height):
        if box in seen:
            continue
        seen.add(box)
        x1, y1, x2, y2 = box
        crop = frame_bgr[y1:y2, x1:x2, :3][:, :, ::-1]
        if crop.size:
            crops.append(np.ascontiguousarray(crop))
    return crops


def _candidate_crop_boxes(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    base = _clamp_box(xyxy, width, height)
    boxes = [base]
    x1, y1, x2, y2 = base
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)
    aspect = max(box_w, box_h) / max(1, min(box_w, box_h))
    area_ratio = (box_w * box_h) / max(1.0, float(width * height))
    if box_w >= box_h and aspect >= 3.0:
        boxes.append(
            _expanded_box(
                base,
                width,
                height,
                x_margin=max(box_w * 1.2, box_h * 5.0),
                y_margin=max(box_h * 1.4, box_w * 0.10),
            )
        )
        if area_ratio <= 0.05 and aspect >= 4.0:
            boxes.append(
                _expanded_box(
                    base,
                    width,
                    height,
                    x_margin=max(box_w * 1.8, box_h * 8.0),
                    y_margin=max(box_h * 2.0, box_w * 0.14),
                )
            )
    return boxes


def _expanded_box(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
    *,
    x_margin: float,
    y_margin: float,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    return _clamp_box(
        (
            round(x1 - x_margin),
            round(y1 - y_margin),
            round(x2 + x_margin),
            round(y2 + y_margin),
        ),
        width,
        height,
    )


def _embedding_from_pil_crop(
    embedder: ImageEmbedder,
    image: Image.Image,
    xyxy: list[object],
) -> np.ndarray | None:
    if len(xyxy) < 4:
        return None
    try:
        raw = (
            int(float(str(xyxy[0]))),
            int(float(str(xyxy[1]))),
            int(float(str(xyxy[2]))),
            int(float(str(xyxy[3]))),
        )
    except (TypeError, ValueError):
        return None
    box = _clamp_box(raw, image.width, image.height)
    return embedder.embed(np.asarray(image.crop(box).convert("RGB")))


def _clamp_box(
    xyxy: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xyxy
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(x1 + 1, min(int(x2), width))
    y2 = max(y1 + 1, min(int(y2), height))
    return x1, y1, x2, y2


def _read_meta(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _manual_meta_files(queue_dir: Path):
    yield from queue_dir.glob("manual*.json")


def _difference_hash(rgb: np.ndarray) -> int:
    image = Image.fromarray(rgb).convert("L").resize((9, 8))
    pixels = np.asarray(image)
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bool(bit))
    return value


__all__ = ["ManualReferenceMatch", "ManualReferenceRecognizer"]
