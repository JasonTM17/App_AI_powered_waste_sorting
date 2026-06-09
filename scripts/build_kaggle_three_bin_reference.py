"""Build a lightweight three-bin reference classifier from Kaggle real images."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.image_embedding import LegacyImageEmbedder, MobileNetV3SmallEmbedder  # noqa: E402
from app.core.kaggle_real_image_pipeline import read_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dataset_v2") / "phase20_kaggle_classification_manifest.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("dataset_v2") / "phase20_kaggle_three_bin_reference.json",
    )
    parser.add_argument("--embedder", choices=("legacy", "mobilenet"), default="legacy")
    parser.add_argument("--max-images", type=int, default=0, help="0 means all manifest rows.")
    parser.add_argument("--max-per-bin", type=int, default=0, help="0 means no per-bin cap.")
    parser.add_argument("--max-per-class", type=int, default=0, help="0 means no per-class cap.")
    parser.add_argument("--progress-every", type=int, default=2000)
    args = parser.parse_args()

    embedder = LegacyImageEmbedder() if args.embedder == "legacy" else MobileNetV3SmallEmbedder()
    vector_sums: dict[str, np.ndarray] = {}
    class_counts: Counter[str] = Counter()
    bin_counts: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    used = 0
    for row in read_manifest(args.manifest):
        if args.max_images > 0 and used >= args.max_images:
            break
        bin_code = str(row.get("bin_code") or "")
        canonical_class = str(row.get("canonical_class") or "")
        if not bin_code:
            skipped["missing_bin"] += 1
            continue
        if args.max_per_bin > 0 and bin_counts[bin_code] >= args.max_per_bin:
            skipped["bin_cap"] += 1
            continue
        if args.max_per_class > 0 and class_counts[canonical_class] >= args.max_per_class:
            skipped["class_cap"] += 1
            continue
        image_path = Path(str(row.get("source_path") or ""))
        if not image_path.exists():
            skipped["missing_image"] += 1
            continue
        vector = _embed_image(embedder, image_path)
        if vector is None:
            skipped["embed_failed"] += 1
            continue
        vector_sums[bin_code] = vector if bin_code not in vector_sums else vector_sums[bin_code] + vector
        class_counts[canonical_class] += 1
        bin_counts[bin_code] += 1
        used += 1
        if args.progress_every > 0 and used % args.progress_every == 0:
            print(f"embedded {used} images")

    artifact = {
        "created_at": datetime.now().isoformat(),
        "manifest": str(args.manifest),
        "embedder": embedder.name,
        "max_images": args.max_images,
        "max_per_bin": args.max_per_bin,
        "max_per_class": args.max_per_class,
        "images": used,
        "by_bin": dict(sorted(bin_counts.items())),
        "by_class": dict(sorted(class_counts.items())),
        "skipped": dict(sorted(skipped.items())),
        "centroids": _centroids(vector_sums),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in artifact.items() if k != "centroids"}, indent=2, ensure_ascii=False))
    print(f"Reference artifact: {args.out}")
    return 0


def _embed_image(embedder: Any, image_path: Path) -> np.ndarray | None:
    try:
        with Image.open(image_path) as image:
            rgb = np.asarray(image.convert("RGB"))
    except OSError:
        return None
    return embedder.embed(rgb)


def _centroids(vector_sums: dict[str, np.ndarray]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for bin_code, centroid_sum in vector_sums.items():
        norm = float(np.linalg.norm(centroid_sum))
        if norm <= 1e-9:
            continue
        out[bin_code] = (centroid_sum / norm).astype(float).tolist()
    return out


if __name__ == "__main__":
    raise SystemExit(main())
