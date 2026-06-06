import json
from datetime import datetime

import numpy as np
from PIL import Image

from app.core.events import Detection
from app.core.image_embedding import LegacyImageEmbedder
from app.core.manual_reference_recognition import ManualReferenceRecognizer


class _CountingEmbedder:
    name = "counting-legacy"

    def __init__(self) -> None:
        self.calls = 0
        self._delegate = LegacyImageEmbedder()

    def embed(self, rgb):
        self.calls += 1
        return self._delegate.embed(rgb)


def _write_reference(
    queue_dir,
    *,
    reviewed: bool,
    count: int = 3,
    holdout: bool = False,
    cls_name: str = "Pen",
    cls_id: int = 42,
    rgb_color: tuple[int, int, int] = (220, 30, 30),
) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        safe_name = cls_name.lower().replace(" ", "_")
        img_path = queue_dir / f"manual_camera_ref_{safe_name}_{index}.jpg"
        image = Image.new("RGB", (80, 40), (20, 20, 20))
        for x in range(15, 65):
            for y in range(12, 28):
                image.putpixel((x, y), rgb_color)
        image.save(img_path, format="JPEG", quality=95)
        meta = {
            "ts": datetime.now().isoformat(),
            "source": "manual_camera_capture",
            "reviewed": reviewed,
            "recognition_enabled": True,
            "holdout": holdout,
            "boxes": [
                {
                    "cls_id": cls_id,
                    "cls_name": cls_name,
                    "conf": 1.0,
                    "xyxy": [15, 12, 65, 28],
                }
            ],
        }
        img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def _query_frame() -> np.ndarray:
    return _query_frame_for_rgb((220, 30, 30))


def _query_frame_for_rgb(rgb_color: tuple[int, int, int]) -> np.ndarray:
    frame = np.zeros((40, 80, 3), dtype=np.uint8)
    frame[:, :] = (20, 20, 20)
    frame[12:28, 15:65] = tuple(reversed(rgb_color))
    return frame


def test_manual_reference_recognizes_reviewed_sample(tmp_path):
    queue_dir = tmp_path / "queue"
    _write_reference(queue_dir, reviewed=True)
    recognizer = ManualReferenceRecognizer(
        queue_dir,
        min_similarity=0.9,
        refresh_seconds=0,
        query_cache_seconds=0,
        embedder=LegacyImageEmbedder(),
    )

    match = recognizer.classify(
        _query_frame(),
        Detection(999, "Unknown object", 0.39, (15, 12, 65, 28)),
    )

    assert match is not None
    assert match.cls_name == "Pen"
    assert match.cls_id == 42
    assert match.similarity >= 0.9


def test_manual_reference_ignores_unreviewed_sample(tmp_path):
    queue_dir = tmp_path / "queue"
    _write_reference(queue_dir, reviewed=False)
    recognizer = ManualReferenceRecognizer(
        queue_dir,
        min_similarity=0.9,
        refresh_seconds=0,
        query_cache_seconds=0,
        embedder=LegacyImageEmbedder(),
    )

    match = recognizer.classify(
        _query_frame(),
        Detection(999, "Unknown object", 0.39, (15, 12, 65, 28)),
    )

    assert match is None


def test_manual_reference_requires_consensus(tmp_path):
    queue_dir = tmp_path / "queue"
    _write_reference(queue_dir, reviewed=True, count=2)
    recognizer = ManualReferenceRecognizer(
        queue_dir,
        min_similarity=0.9,
        refresh_seconds=0,
        embedder=LegacyImageEmbedder(),
    )

    assert recognizer.classify(
        _query_frame(),
        Detection(999, "Unknown object", 0.39, (15, 12, 65, 28)),
    ) is None


def test_manual_reference_excludes_holdout(tmp_path):
    queue_dir = tmp_path / "queue"
    _write_reference(queue_dir, reviewed=True, holdout=True)
    recognizer = ManualReferenceRecognizer(
        queue_dir,
        min_similarity=0.9,
        refresh_seconds=0,
        embedder=LegacyImageEmbedder(),
    )

    assert recognizer.classify(
        _query_frame(),
        Detection(999, "Unknown object", 0.39, (15, 12, 65, 28)),
    ) is None


def test_manual_reference_caches_stable_query_crop(tmp_path):
    queue_dir = tmp_path / "queue"
    _write_reference(queue_dir, reviewed=True)
    embedder = _CountingEmbedder()
    recognizer = ManualReferenceRecognizer(
        queue_dir,
        min_similarity=0.9,
        refresh_seconds=30,
        query_cache_seconds=2,
        embedder=embedder,
    )
    detection = Detection(999, "Unknown object", 0.39, (15, 12, 65, 28))

    first = recognizer.classify(_query_frame(), detection)
    calls_after_first = embedder.calls
    second = recognizer.classify(_query_frame(), detection)

    assert first is not None
    assert second == first
    assert embedder.calls == calls_after_first


def test_manual_reference_recognizes_multiple_common_waste_classes(tmp_path):
    queue_dir = tmp_path / "queue"
    examples = [
        ("Organic", 17, (40, 180, 60)),
        ("Plastic bottle", 24, (30, 90, 230)),
        ("Textile", 37, (180, 180, 180)),
    ]
    for cls_name, cls_id, color in examples:
        _write_reference(
            queue_dir,
            reviewed=True,
            cls_name=cls_name,
            cls_id=cls_id,
            rgb_color=color,
        )
    recognizer = ManualReferenceRecognizer(
        queue_dir,
        min_similarity=0.9,
        refresh_seconds=0,
        query_cache_seconds=0,
        embedder=LegacyImageEmbedder(),
    )

    for cls_name, _cls_id, color in examples:
        match = recognizer.classify(
            _query_frame_for_rgb(color),
            Detection(999, "Unknown object", 0.39, (15, 12, 65, 28)),
        )

        assert match is not None
        assert match.cls_name == cls_name
