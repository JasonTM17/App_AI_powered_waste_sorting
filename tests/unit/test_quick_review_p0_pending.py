from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from scripts.quick_review_p0_pending import review_pending


def _write_pending(queue: Path, name: str, cls_name: str) -> None:
    img = queue / f"manual_web_{name}.jpg"
    Image.new("RGB", (80, 60), (240, 240, 240)).save(img)
    img.with_suffix(".json").write_text(
        json.dumps(
            {
                "source": "manual_web_import",
                "source_type": "wikimedia",
                "source_url": f"https://example.test/{name}.jpg",
                "source_page_url": f"https://example.test/page/{name}",
                "source_license": "CC BY-SA 4.0",
                "license": "CC BY-SA 4.0",
                "source_author": "Example",
                "canonical_class": cls_name,
                "reviewed": False,
                "needs_annotation": True,
                "generated": False,
                "boxes": [{"cls_id": 0, "cls_name": cls_name, "conf": 1.0, "xyxy": [0, 0, 80, 60]}],
            }
        ),
        encoding="utf-8",
    )


def test_quick_review_marks_train_and_holdout(tmp_path):
    queue = tmp_path / "queue"
    queue.mkdir()
    for index in range(4):
        _write_pending(queue, f"pen_{index}", "Pen")

    report = review_pending(
        queue,
        tmp_path / "dataset.db",
        classes=("Pen",),
        train_target=4,
        holdout_target=2,
    )

    assert report["reviewed_total"] == 4
    metas = [json.loads(path.read_text(encoding="utf-8")) for path in queue.glob("*.json")]
    assert sum(meta["reviewed"] is True for meta in metas) == 4
    assert sum(meta["holdout"] is True for meta in metas) == 2
    assert {meta["review_method"] for meta in metas} == {"phase12_assisted_review"}
    assert {tuple(meta["boxes"][0]["xyxy"]) for meta in metas} == {(0, 0, 80, 60)}
