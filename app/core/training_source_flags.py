"""Shared metadata flags for train-only supplemental sources."""

from __future__ import annotations


def is_generated_meta(meta: dict) -> bool:
    source_type = str(meta.get("source_type") or "").lower()
    source = str(meta.get("source") or "").lower()
    generated_sources = ("generated", "imagegen", "synthetic")
    return bool(meta.get("generated")) or source_type in generated_sources or source.startswith(generated_sources)


def is_camera_blur_augmented_meta(meta: dict) -> bool:
    source_type = str(meta.get("source_type") or "").lower()
    source = str(meta.get("source") or "").lower()
    return bool(meta.get("camera_blur_augmented")) or source_type == "camera_blur_augmented" or source.startswith(
        "camera_blur_augmented"
    )


def is_train_only_supplemental_meta(meta: dict) -> bool:
    return is_generated_meta(meta) or is_camera_blur_augmented_meta(meta)


__all__ = [
    "is_camera_blur_augmented_meta",
    "is_generated_meta",
    "is_train_only_supplemental_meta",
]
