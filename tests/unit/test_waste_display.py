from app.core.waste_display import waste_display_name


def test_waste_display_name_translates_canonical_classes():
    assert waste_display_name("Organic") == "Rác hữu cơ"
    assert waste_display_name("Paper bag") == "Túi giấy"


def test_waste_display_name_hides_three_bin_internal_label():
    assert waste_display_name("Kaggle 3-bin O") == "Nhóm Hữu cơ (AI chưa xác định vật cụ thể)"


def test_waste_display_name_preserves_unknown_custom_class():
    assert waste_display_name("Custom class") == "Custom class"
