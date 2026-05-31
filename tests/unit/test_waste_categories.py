from app.core.waste_categories import (
    DEFAULT_CLASS_ORDER,
    INORGANIC,
    ORGANIC,
    RECYCLABLE,
    canonical_class_name,
    category_for_class,
    category_for_known_class,
    default_class_id_for_name,
    make_three_bin_mappings,
)


def test_plastic_container_alias_routes_to_recyclable_canister():
    assert canonical_class_name("hop nhua") == "Plastic canister"
    assert category_for_class("hop nhua") == RECYCLABLE


def test_three_bin_mapping_covers_default_classes():
    mappings = make_three_bin_mappings()

    assert len(mappings) == len(DEFAULT_CLASS_ORDER)
    assert {m.command for m in mappings} == {ORGANIC.code, RECYCLABLE.code, INORGANIC.code}
    assert {m.bin_index for m in mappings} == {1, 2, 3}


def test_category_examples_match_three_bin_rules():
    assert category_for_class("Organic") == ORGANIC
    assert category_for_class("Plastic bottle") == RECYCLABLE
    assert category_for_class("Electronics") == INORGANIC
    assert category_for_class("paper") == RECYCLABLE
    assert category_for_class("Pen") == INORGANIC
    assert category_for_class("Pencil") == INORGANIC
    assert category_for_class("Marker") == INORGANIC
    assert category_for_class("Battery") == INORGANIC
    assert category_for_class("Toothbrush") == INORGANIC
    assert category_for_class("Cardboard") == RECYCLABLE
    assert category_for_class("Aluminum can") == RECYCLABLE
    assert category_for_class("Banana peel") == ORGANIC
    assert category_for_class("Leftover food") == ORGANIC
    assert category_for_class("Beer can") == RECYCLABLE
    assert category_for_class("Milk carton") == RECYCLABLE
    assert category_for_class("Foam food box") == INORGANIC
    assert category_for_class("Face mask") == INORGANIC
    assert category_for_class("Milk tea cup") == RECYCLABLE


def test_all_default_classes_are_known_for_config_repair():
    assert all(category_for_known_class(class_name) is not None for class_name in DEFAULT_CLASS_ORDER)


def test_swapped_display_labels_keep_existing_class_commands():
    assert INORGANIC.code == "R"
    assert RECYCLABLE.code == "I"


def test_pen_mapping_routes_to_inorganic_bin():
    mappings = {mapping.class_name: mapping for mapping in make_three_bin_mappings()}

    assert mappings["Pen"].command == INORGANIC.code
    assert mappings["Pen"].bin_index == INORGANIC.bin_index
    assert mappings["Battery"].command == INORGANIC.code
    assert mappings["Toothbrush"].command == INORGANIC.code


def test_default_class_id_supports_extended_camera_labels():
    assert default_class_id_for_name("Pen") is not None
    assert default_class_id_for_name("pen") == default_class_id_for_name("Pen")
    assert default_class_id_for_name("Textile") == 37
    assert default_class_id_for_name("vải") == 37
    assert default_class_id_for_name("mieng vai") == 37
    assert default_class_id_for_name("Battery") is not None
    assert default_class_id_for_name("Toothbrush") is not None
    assert default_class_id_for_name("Battery") == 43
    assert default_class_id_for_name("Toothbrush") == 44


def test_vietnamese_aliases_resolve_to_existing_training_classes():
    assert canonical_class_name("cây bút") == "Pen"
    assert canonical_class_name("vỏ chuối") == "Organic"
    assert canonical_class_name("lon nước ngọt") == "Aluminum can"
    assert canonical_class_name("khẩu trang") == "Textile"


def test_textile_aliases_cover_common_cloth_names():
    assert canonical_class_name("vải") == "Textile"
    assert canonical_class_name("mieng vai") == "Textile"
    assert canonical_class_name("miếng vải") == "Textile"
    assert canonical_class_name("vai cu") == "Textile"
    assert canonical_class_name("vải cũ") == "Textile"
    assert canonical_class_name("khau trang") == "Textile"
    assert canonical_class_name("khẩu trang") == "Textile"
    assert category_for_class("mieng vai") == INORGANIC
