"""Unicode-safe operator-facing Vietnamese names for canonical waste classes."""

from __future__ import annotations

import re

from app.core.three_bin_classifier import three_bin_display_name

WASTE_DISPLAY_NAMES = {
    "Organic": "R\u00e1c h\u1eefu c\u01a1",
    "Aluminum can": "Lon nh\u00f4m",
    "Plastic bottle": "Chai nh\u1ef1a PET",
    "Cardboard": "Th\u00f9ng carton",
    "Paper": "Gi\u1ea5y",
    "Plastic cup": "Ly nh\u1ef1a",
    "Tin": "H\u1ed9p thi\u1ebfc",
    "Glass bottle": "Chai th\u1ee7y tinh",
    "Iron utensils": "Mu\u1ed7ng/n\u0129a kim lo\u1ea1i",
    "Eggshell": "V\u1ecf tr\u1ee9ng",
    "Plastic bag": "B\u00ec ni l\u00f4ng",
    "Wood": "G\u1ed7/\u0111\u1ed3 g\u1ed7",
    "Pen": "B\u00fat bi",
    "Battery": "Pin",
    "Toothbrush": "B\u00e0n ch\u1ea3i",
    "Textile": "V\u1ea3i/Qu\u1ea7n \u00e1o",
    "Disposable tableware": "H\u1ed9p x\u1ed1p/\u0111\u1ed3 d\u00f9ng m\u1ed9t l\u1ea7n",
    "Unknown plastic": "Nh\u1ef1a kh\u00e1c",
    "Tetra pack": "V\u1ecf h\u1ed9p s\u1eefa",
    "Ceramic": "G\u1ed1m s\u1ee9",
    "Aerosols": "B\u00ecnh x\u1ecbt",
    "Electronics": "\u0110\u1ed3 \u0111i\u1ec7n t\u1eed",
    "Plastic caps": "N\u1eafp nh\u1ef1a",
    "Stretch film": "M\u00e0ng b\u1ecdc th\u1ef1c ph\u1ea9m",
    "Paper cups": "Ly gi\u1ea5y",
    "Aluminum caps": "N\u1eafp nh\u00f4m",
    "Foil": "Gi\u1ea5y b\u1ea1c",
    "Postal packaging": "Bao b\u00ec chuy\u1ec3n ph\u00e1t",
    "Scrap metal": "S\u1eaft v\u1ee5n",
    "Plastic canister": "Can/H\u1ed9p nh\u1ef1a",
    "Container for household chemicals": "Chai h\u00f3a ch\u1ea5t gia d\u1ee5ng",
    "Printing industry": "Gi\u1ea5y/in \u1ea5n c\u00f4ng nghi\u1ec7p",
    "Liquid": "Ch\u1ea5t l\u1ecfng",
    "Milk bottle": "Chai s\u1eefa",
    "Plastic shavings": "M\u1ea3nh nh\u1ef1a v\u1ee5n",
    "Paper bag": "T\u00fai gi\u1ea5y",
    "Leaf": "L\u00e1 c\u00e2y",
    "Wooden spoon": "Th\u00eca g\u1ed7",
    "Plastic fork": "N\u0129a nh\u1ef1a d\u00f9ng m\u1ed9t l\u1ea7n",
}

LEGACY_OPERATOR_LABELS = {
    "V? tr?ng g?": "V\u1ecf tr\u1ee9ng g\u00e0",
    "Vo trung": "V\u1ecf tr\u1ee9ng g\u00e0",
    "Vo trung ga": "V\u1ecf tr\u1ee9ng g\u00e0",
    "V? tr?ng": "V\u1ecf tr\u1ee9ng",
    "Chai nh?a": "Chai nh\u1ef1a PET",
    "Mu?ng g?": "Mu\u1ed7ng g\u1ed7",
    "La cay": "L\u00e1 c\u00e2y",
    "Muong kim loai": "Mu\u1ed7ng kim lo\u1ea1i",
    "Chai nhua PET": "Chai nh\u1ef1a PET",
    "Gom su": "G\u1ed1m s\u1ee9",
    "Giay vo": "Gi\u1ea5y v\u00f2",
    "But bi": "B\u00fat bi",
    "Thia go": "Th\u00eca g\u1ed7",
    "Cai luoc": "C\u00e1i l\u01b0\u1ee3c",
    "Luoc nhua": "C\u00e1i l\u01b0\u1ee3c",
    "Luoc": "C\u00e1i l\u01b0\u1ee3c",
    "But da": "B\u00fat d\u1ea1",
    "Bat lua": "B\u1eadt l\u1eeda",
    "O cam dien": "\u1ed4 c\u1eafm \u0111i\u1ec7n",
    "Cu sac": "C\u1ee5c s\u1ea1c",
    "Cuc sac": "C\u1ee5c s\u1ea1c",
    "Day sac": "D\u00e2y s\u1ea1c",
    "Bi ni long": "B\u00ec ni l\u00f4ng",
    "Tui nylon": "B\u00ec ni l\u00f4ng",
    "But da quang": "Bút dạ quang",
    "Bang xoa": "Băng xoá",
    "Pin 9V": "Pin 9V",
    "Pin AA": "Pin AA/AAA",
    "Pin AAA": "Pin AA/AAA",
    "Ba mia": "B\u00e3 m\u00eda",
    "ba mia": "B\u00e3 m\u00eda",
    "B\u00e3 m\u00eda": "B\u00e3 m\u00eda",
}

_MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00c4", "\u00c6", "\u00ef\u00bf\u00bd", "?")


def waste_display_name(cls_name: str) -> str:
    clean = str(cls_name or "").strip()
    generic_name = three_bin_display_name(clean)
    if generic_name != clean:
        return generic_name
    return WASTE_DISPLAY_NAMES.get(clean, clean)


def normalize_operator_label(operator_label: str, cls_name: str = "") -> str:
    """Repair historic labels at display time; never rewrite source metadata."""
    clean = re.sub(r"\s+", " ", str(operator_label or "")).strip()
    clean = LEGACY_OPERATOR_LABELS.get(clean, clean)
    if any(marker in clean for marker in _MOJIBAKE_MARKERS):
        clean = _repair_utf8_mojibake(clean)
        clean = LEGACY_OPERATOR_LABELS.get(clean, clean)
    if not clean or "?" in clean or any(marker in clean for marker in _MOJIBAKE_MARKERS[:-1]):
        return waste_display_name(cls_name)
    return clean


def waste_detection_display_name(cls_name: str, operator_label: str = "") -> str:
    return normalize_operator_label(operator_label, cls_name) or waste_display_name(cls_name)


def _repair_utf8_mojibake(value: str) -> str:
    current = value
    for encoding in ("cp1252", "latin-1"):
        try:
            candidate = current.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if _mojibake_score(candidate) < _mojibake_score(current):
            current = candidate
    return current


def _mojibake_score(value: str) -> int:
    return sum(value.count(marker) for marker in _MOJIBAKE_MARKERS[:-1])


__all__ = [
    "LEGACY_OPERATOR_LABELS",
    "WASTE_DISPLAY_NAMES",
    "normalize_operator_label",
    "waste_detection_display_name",
    "waste_display_name",
]
