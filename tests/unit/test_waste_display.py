import pytest

from app.core.waste_display import (
    normalize_operator_label,
    waste_detection_display_name,
    waste_display_name,
)


def test_waste_display_name_translates_canonical_classes():
    assert waste_display_name("Organic") == "Rác hữu cơ"
    assert waste_display_name("Paper bag") == "Túi giấy"


def test_waste_display_name_hides_three_bin_internal_label():
    assert (
        waste_display_name("Kaggle 3-bin O")
        == "Nhóm Hữu cơ (chưa xác định vật cụ thể)"
    )


def test_waste_display_name_preserves_unknown_custom_class():
    assert waste_display_name("Custom class") == "Custom class"


def test_waste_display_name_translates_visual_correction_classes():
    assert waste_display_name("Eggshell") == "Vỏ trứng"
    assert waste_display_name("Wood") == "Gỗ/đồ gỗ"
    assert waste_display_name("Printing industry") == "Giấy/in ấn công nghiệp"
    assert waste_display_name("Container for household chemicals") == "Chai hóa chất gia dụng"
    assert waste_display_name("Liquid") == "Chất lỏng"
    assert waste_display_name("Milk bottle") == "Chai sữa"
    assert waste_display_name("Plastic shavings") == "Mảnh nhựa vụn"


@pytest.mark.parametrize(
    ("legacy", "cls_name", "expected"),
    [
        ("V? tr?ng g?", "Organic", "Vỏ trứng gà"),
        ("Chai nh?a", "Plastic bottle", "Chai nhựa PET"),
        ("Mu?ng g?", "Wood", "Muỗng gỗ"),
        ("La cay", "Leaf", "Lá cây"),
        ("Muong kim loai", "Iron utensils", "Muỗng kim loại"),
        ("But bi", "Pen", "Bút bi"),
        ("Vo trung", "Organic", "Vỏ trứng gà"),
        ("Bi ni long", "Plastic bag", "Bì ni lông"),
        ("Cuc sac", "Electronics", "Cục sạc"),
        ("But da quang", "Pen", "Bút dạ quang"),
        ("Bang xoa", "Unknown plastic", "Băng xoá"),
        ("Pin AA", "Battery", "Pin AA/AAA"),
        ("Ba mia", "Organic", "B\u00e3 m\u00eda"),
        ("B\u00c3\u00a3 m\u00c3\u00ada", "Organic", "B\u00e3 m\u00eda"),
    ],
)
def test_normalize_operator_label_repairs_legacy_camera_labels(
    legacy: str,
    cls_name: str,
    expected: str,
):
    assert normalize_operator_label(legacy, cls_name) == expected


def test_corrupted_unknown_operator_label_falls_back_to_canonical_display_name():
    assert waste_detection_display_name("Paper bag", "T?i gi?y") == "Túi giấy"
