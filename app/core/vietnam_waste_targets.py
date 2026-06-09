"""Priority targets for common Vietnamese waste model training."""

from __future__ import annotations

from app.core.waste_categories import canonical_class_name

P0_CLASSES = (
    "Pen",
    "Battery",
    "Toothbrush",
    "Textile",
    "Disposable tableware",
    "Unknown plastic",
    "Tetra pack",
    "Ceramic",
    "Aerosols",
    "Electronics",
)
P1_CLASSES = (
    "Organic",
    "Aluminum can",
    "Plastic bottle",
    "Cardboard",
    "Paper",
    "Plastic bag",
    "Plastic cup",
    "Tin",
    "Glass bottle",
)
P2_CLASSES = (
    "Plastic caps",
    "Stretch film",
    "Paper cups",
    "Aluminum caps",
    "Foil",
    "Postal packaging",
    "Scrap metal",
)
VIETNAM_TARGET_CLASSES = tuple(dict.fromkeys((*P0_CLASSES, *P1_CLASSES, *P2_CLASSES)))


def priority_for_class(class_name: str) -> str:
    canonical = canonical_class_name(class_name)
    if canonical in P0_CLASSES:
        return "P0"
    if canonical in P1_CLASSES:
        return "P1"
    if canonical in P2_CLASSES:
        return "P2"
    return "other"


__all__ = ["P0_CLASSES", "P1_CLASSES", "P2_CLASSES", "VIETNAM_TARGET_CLASSES", "priority_for_class"]
