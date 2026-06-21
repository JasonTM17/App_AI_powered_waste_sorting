from app.core.common_waste_catalog import COMMON_WASTE_ITEMS, common_waste_catalog
from app.core.waste_categories import (
    INORGANIC,
    ORGANIC,
    RECYCLABLE,
    canonical_class_name,
    category_for_class,
    default_class_id_for_name,
)


def test_common_waste_catalog_routes_examples_to_three_bins():
    rows = {item.label: item for item in COMMON_WASTE_ITEMS}

    assert rows["Vo chuoi"].canonical_class == "Organic"
    assert rows["Vo chuoi"].command == ORGANIC.code
    assert rows["Vỏ trứng gà"].canonical_class == "Organic"
    assert rows["Vỏ trứng gà"].command == ORGANIC.code
    assert rows["Lon nuoc"].canonical_class == "Aluminum can"
    assert rows["Lon nuoc"].command == RECYCLABLE.code
    assert rows["But bi"].canonical_class == "Pen"
    assert rows["But bi"].command == INORGANIC.code
    assert rows["Khau trang"].canonical_class == "Textile"
    assert rows["Khau trang"].command == INORGANIC.code
    assert rows["Cái lược"].canonical_class == "Unknown plastic"
    assert rows["Cái lược"].command == INORGANIC.code
    assert rows["Bì ni lông"].canonical_class == "Plastic bag"
    assert rows["Bì ni lông"].command == RECYCLABLE.code
    assert rows["Pin AA/AAA"].command == INORGANIC.code
    assert rows["Hộp xốp bẩn"].command == INORGANIC.code
    assert rows["Gốm sứ vỡ"].command == INORGANIC.code


def test_common_aliases_canonicalize_to_training_classes():
    assert canonical_class_name("vo chuoi") == "Organic"
    assert canonical_class_name("vo trung") == "Organic"
    assert canonical_class_name("vo trung ga") == "Organic"
    assert canonical_class_name("eggshell") == "Organic"
    assert canonical_class_name("bã mía") == "Organic"
    assert canonical_class_name("lon nuoc") == "Aluminum can"
    assert canonical_class_name("chai pet") == "Plastic bottle"
    assert canonical_class_name("hop sua giay") == "Tetra pack"
    assert canonical_class_name("but bi") == "Pen"
    assert canonical_class_name("but chi") == "Pen"
    assert canonical_class_name("vải") == "Textile"
    assert canonical_class_name("khau trang") == "Textile"
    assert canonical_class_name("lon do hop") == "Tin"
    assert canonical_class_name("chai dau goi") == "Plastic bottle"
    assert canonical_class_name("hop xop") == "Disposable tableware"
    assert canonical_class_name("muong kim loai") == "Iron utensils"
    assert canonical_class_name("vi thuoc") == "Unknown plastic"
    assert canonical_class_name("cai luoc") == "Unknown plastic"
    assert canonical_class_name("lược nhựa") == "Unknown plastic"
    assert canonical_class_name("găng tay cao su") == "Unknown plastic"
    assert canonical_class_name("bi ni long") == "Plastic bag"
    assert canonical_class_name("pin aa") == "Battery"
    assert canonical_class_name("cục sạc") == "Electronics"
    assert category_for_class(canonical_class_name("vo goi ban")) == INORGANIC


def test_common_waste_catalog_stays_inside_training_taxonomy():
    assert all(default_class_id_for_name(item.canonical_class) is not None for item in COMMON_WASTE_ITEMS)


def test_common_waste_catalog_api_shape_is_serializable():
    rows = common_waste_catalog()

    assert len(rows) >= 30
    assert {"label", "canonical_class", "command", "bin_index", "aliases"} <= set(rows[0])
    assert {row["canonical_class"] for row in rows} >= {"Organic", "Pen", "Plastic bottle"}
