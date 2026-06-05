"""Three-bin semantic taxonomy for the sorter.

The YOLO model keeps its detailed 42-class vocabulary, while the real machine
uses three tested actuator routes: organic, inorganic, and recyclable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.config import ClassMapping


@dataclass(frozen=True)
class WasteCategory:
    code: str
    name: str
    bin_index: int
    voice_text: str


ORGANIC = WasteCategory("O", "Hữu cơ", 1, "Rác hữu cơ, chuyển vào thùng số một.")
INORGANIC = WasteCategory("R", "Vô cơ", 2, "Rác vô cơ, chuyển vào thùng số hai.")
RECYCLABLE = WasteCategory("I", "Tái chế", 3, "Rác tái chế, chuyển vào thùng số ba.")

CATEGORIES_BY_COMMAND = {
    ORGANIC.code: ORGANIC,
    INORGANIC.code: INORGANIC,
    RECYCLABLE.code: RECYCLABLE,
}

TRAINING_CLASS_ORDER_45 = (
    "Aerosols",
    "Aluminum can",
    "Aluminum caps",
    "Cardboard",
    "Cellulose",
    "Ceramic",
    "Combined plastic",
    "Container for household chemicals",
    "Disposable tableware",
    "Electronics",
    "Foil",
    "Furniture",
    "Glass bottle",
    "Iron utensils",
    "Liquid",
    "Metal shavings",
    "Milk bottle",
    "Organic",
    "Paper",
    "Paper bag",
    "Paper cups",
    "Paper shavings",
    "Papier mache",
    "Plastic bag",
    "Plastic bottle",
    "Plastic can",
    "Plastic canister",
    "Plastic caps",
    "Plastic cup",
    "Plastic shaker",
    "Plastic shavings",
    "Plastic toys",
    "Postal packaging",
    "Printing industry",
    "Scrap metal",
    "Stretch film",
    "Tetra pack",
    "Textile",
    "Tin",
    "Unknown plastic",
    "Wood",
    "Zip plastic bag",
    "Pen",
    "Battery",
    "Toothbrush",
)

DEFAULT_CLASS_ORDER = (
    "Cardboard",
    "Cellulose",
    "Paper",
    "Paper bag",
    "Paper cups",
    "Paper shavings",
    "Papier mache",
    "Postal packaging",
    "Printing industry",
    "Combined plastic",
    "Plastic bag",
    "Plastic bottle",
    "Plastic can",
    "Plastic canister",
    "Plastic caps",
    "Plastic cup",
    "Plastic shaker",
    "Plastic shavings",
    "Plastic toys",
    "Stretch film",
    "Unknown plastic",
    "Zip plastic bag",
    "Aerosols",
    "Aluminum can",
    "Aluminum caps",
    "Foil",
    "Iron utensils",
    "Metal shavings",
    "Scrap metal",
    "Tin",
    "Ceramic",
    "Glass bottle",
    "Milk bottle",
    "Liquid",
    "Organic",
    "Container for household chemicals",
    "Disposable tableware",
    "Electronics",
    "Furniture",
    "Tetra pack",
    "Textile",
    "Wood",
    "Pen",
    "Pencil",
    "Marker",
    "Battery",
    "Toothbrush",
    "Banana peel",
    "Fruit peel",
    "Vegetable scraps",
    "Leftover food",
    "Tea leaves",
    "Coffee grounds",
    "Eggshell",
    "Beer can",
    "Soft drink can",
    "Glass jar",
    "Newspaper",
    "Carton box",
    "Milk carton",
    "Clean plastic cup",
    "Shampoo bottle",
    "Food can",
    "Metal bottle cap",
    "Foam food box",
    "Face mask",
    "Dirty nylon bag",
    "Plastic straw",
    "Disposable chopsticks",
    "Snack wrapper",
    "Candy wrapper",
    "Ceramic bowl",
    "Broken glass",
    "Diaper",
    "Cigarette butt",
    "Wet tissue",
    "Medicine blister pack",
    "Milk tea cup",
    "Instant noodle cup",
    "Styrofoam cup",
)

VIETNAMESE_CLASS_ALIASES = {
    "vo chuoi": "Organic",
    "vỏ chuối": "Organic",
    "rac thuc pham": "Organic",
    "rác thực phẩm": "Organic",
    "thuc an thua": "Organic",
    "thức ăn thừa": "Organic",
    "lon bia": "Aluminum can",
    "lon nuoc ngot": "Aluminum can",
    "lon nước ngọt": "Aluminum can",
    "chai nhua pet": "Plastic bottle",
    "chai nhựa pet": "Plastic bottle",
    "chai dau goi": "Plastic bottle",
    "chai dầu gội": "Plastic bottle",
    "hop nhua": "Plastic canister",
    "hộp nhựa": "Plastic canister",
    "hop nhua cung": "Plastic canister",
    "hộp nhựa cứng": "Plastic canister",
    "hop carton": "Cardboard",
    "hộp carton": "Cardboard",
    "thung carton": "Cardboard",
    "thùng carton": "Cardboard",
    "bao giay": "Paper bag",
    "bao giấy": "Paper bag",
    "khau trang": "Textile",
    "vai": "Textile",
    "vải": "Textile",
    "mieng vai": "Textile",
    "miếng vải": "Textile",
    "vai cu": "Textile",
    "vải cũ": "Textile",
    "quan ao cu": "Textile",
    "quần áo cũ": "Textile",
    "khẩu trang": "Textile",
    "hop xop": "Disposable tableware",
    "hộp xốp": "Disposable tableware",
    "ly tra sua": "Plastic cup",
    "ly trà sữa": "Plastic cup",
    "ly nhua": "Plastic cup",
    "ly nhựa": "Plastic cup",
    "tui nylon": "Plastic bag",
    "túi nylon": "Plastic bag",
    "but bi": "Pen",
    "bút bi": "Pen",
    "cay but": "Pen",
    "cây bút": "Pen",
    "pin": "Battery",
    "ban chai danh rang": "Toothbrush",
    "bàn chải đánh răng": "Toothbrush",
    "banana peel": "Organic",
    "leftover food": "Organic",
    "beer can": "Aluminum can",
    "soft drink can": "Aluminum can",
    "newspaper": "Paper",
    "carton box": "Cardboard",
    "clean plastic cup": "Plastic cup",
    "shampoo bottle": "Plastic bottle",
    "foam food box": "Disposable tableware",
    "face mask": "Textile",
    "dirty nylon bag": "Plastic bag",
    "milk tea cup": "Plastic cup",
}

ORGANIC_CLASSES = frozenset(
    {
        "Banana peel",
        "Coffee grounds",
        "Eggshell",
        "Fruit peel",
        "Leftover food",
        "Liquid",
        "Organic",
        "Tea leaves",
        "Vegetable scraps",
        "Wood",
    }
)

RECYCLABLE_CLASSES = frozenset(
    {
        "Aluminum can",
        "Aluminum caps",
        "Beer can",
        "Cardboard",
        "Cellulose",
        "Carton box",
        "Clean plastic cup",
        "Combined plastic",
        "Food can",
        "Foil",
        "Glass bottle",
        "Glass jar",
        "Iron utensils",
        "Metal shavings",
        "Metal bottle cap",
        "Milk bottle",
        "Milk carton",
        "Newspaper",
        "Paper",
        "Paper bag",
        "Paper cups",
        "Paper shavings",
        "Papier mache",
        "Plastic bag",
        "Plastic bottle",
        "Plastic can",
        "Plastic canister",
        "Plastic caps",
        "Plastic cup",
        "Plastic shaker",
        "Plastic shavings",
        "Postal packaging",
        "Printing industry",
        "Scrap metal",
        "Shampoo bottle",
        "Soft drink can",
        "Stretch film",
        "Tetra pack",
        "Tin",
        "Zip plastic bag",
    }
)

INORGANIC_CLASSES = frozenset(
    class_name
    for class_name in DEFAULT_CLASS_ORDER
    if class_name not in ORGANIC_CLASSES and class_name not in RECYCLABLE_CLASSES
)

_CLASS_TO_CATEGORY = {
    **{name.casefold(): ORGANIC for name in ORGANIC_CLASSES},
    **{name.casefold(): INORGANIC for name in INORGANIC_CLASSES},
    **{name.casefold(): RECYCLABLE for name in RECYCLABLE_CLASSES},
}


def category_for_known_class(class_name: str) -> WasteCategory | None:
    """Return a category only when the class is in the model's known taxonomy."""
    key = canonical_class_name(class_name).casefold()
    if not key:
        return None
    return _CLASS_TO_CATEGORY.get(key)


def category_for_class(class_name: str) -> WasteCategory:
    known = category_for_known_class(class_name)
    if known is not None:
        return known
    if class_name in ORGANIC_CLASSES:
        return ORGANIC
    if class_name in RECYCLABLE_CLASSES:
        return RECYCLABLE
    return INORGANIC


def category_for_command(command: str) -> WasteCategory | None:
    return CATEGORIES_BY_COMMAND.get(command.strip().upper())


def category_for_bin_index(bin_index: object) -> WasteCategory | None:
    try:
        value = int(str(bin_index))
    except (TypeError, ValueError):
        return None
    for category in CATEGORIES_BY_COMMAND.values():
        if category.bin_index == value:
            return category
    return None


def default_class_id_for_name(class_name: str) -> int | None:
    key = canonical_class_name(class_name).casefold()
    if not key:
        return None
    for cls_id, name in enumerate(TRAINING_CLASS_ORDER_45):
        if name.casefold() == key:
            return cls_id
    return None


def canonical_class_name(class_name: str) -> str:
    clean = str(class_name or "").strip()
    if not clean:
        return ""
    from app.core.common_waste_catalog import COMMON_WASTE_ALIASES

    common_alias = COMMON_WASTE_ALIASES.get(clean.casefold())
    if common_alias:
        return common_alias
    alias = VIETNAMESE_CLASS_ALIASES.get(clean.casefold())
    if alias:
        return alias
    for known in TRAINING_CLASS_ORDER_45:
        if known.casefold() == clean.casefold():
            return known
    return clean


def normalize_mapping_to_three_bins(mapping: ClassMapping) -> ClassMapping:
    category = (
        category_for_known_class(mapping.class_name)
        or category_for_command(mapping.command)
        or category_for_bin_index(mapping.bin_index)
        or INORGANIC
    )
    return mapping.model_copy(
        update={
            "command": category.code,
            "bin_index": category.bin_index,
        }
    )


def make_three_bin_mappings(
    class_names: Iterable[str] = DEFAULT_CLASS_ORDER,
) -> list[ClassMapping]:
    return [
        ClassMapping(
            class_name=class_name,
            command=category_for_class(class_name).code,
            bin_index=category_for_class(class_name).bin_index,
            enabled=True,
        )
        for class_name in class_names
    ]
