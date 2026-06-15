"""Operator-facing Vietnamese names for canonical waste classes."""

from __future__ import annotations

from app.core.three_bin_classifier import three_bin_display_name

WASTE_DISPLAY_NAMES = {
    "Organic": "Rác hữu cơ",
    "Aluminum can": "Lon nhôm",
    "Plastic bottle": "Chai nhựa PET",
    "Cardboard": "Thùng carton",
    "Paper": "Giấy",
    "Plastic bag": "Túi nylon",
    "Plastic cup": "Ly nhựa",
    "Tin": "Hộp thiếc",
    "Glass bottle": "Chai thủy tinh",
    "Pen": "Bút bi",
    "Battery": "Pin",
    "Toothbrush": "Bàn chải",
    "Textile": "Vải/Quần áo",
    "Disposable tableware": "Hộp xốp/đồ dùng một lần",
    "Unknown plastic": "Nhựa khác",
    "Tetra pack": "Vỏ hộp sữa",
    "Ceramic": "Gốm sứ",
    "Aerosols": "Bình xịt",
    "Electronics": "Đồ điện tử",
    "Plastic caps": "Nắp nhựa",
    "Stretch film": "Màng bọc thực phẩm",
    "Paper cups": "Ly giấy",
    "Aluminum caps": "Nắp nhôm",
    "Foil": "Giấy bạc",
    "Postal packaging": "Bao bì chuyển phát",
    "Scrap metal": "Sắt vụn",
    "Plastic canister": "Can/Hộp nhựa",
    "Paper bag": "Túi giấy",
}


def waste_display_name(cls_name: str) -> str:
    """Return one consistent operator label without exposing model internals."""

    clean = str(cls_name or "").strip()
    generic_name = three_bin_display_name(clean)
    if generic_name != clean:
        return generic_name
    return WASTE_DISPLAY_NAMES.get(clean, clean)


__all__ = ["WASTE_DISPLAY_NAMES", "waste_display_name"]
