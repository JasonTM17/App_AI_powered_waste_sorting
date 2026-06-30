from app.core.common_waste_catalog import COMMON_WASTE_ITEMS, SPECIALIST_REVIEW_LABELS
from app.core.waste_display import waste_detection_display_name


def _escaped_marker(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def test_operator_catalog_has_clean_utf8_labels_and_aliases() -> None:
    broken_markers = tuple(
        _escaped_marker(value)
        for value in (
            r"\u00c3",
            r"\u00c2",
            r"\u00c4",
            r"\u00c6",
            r"\u00ef\u00bf\u00bd",
            r"\ufffd",
        )
    )
    values = [
        value
        for item in COMMON_WASTE_ITEMS
        for value in (item.label, *item.aliases)
    ]

    assert values
    assert not [value for value in values if any(marker in value for marker in broken_markers)]


def test_specialist_review_labels_cover_problem_objects_in_vietnamese() -> None:
    assert {
        "Cái lược",
        "Bút dạ",
        "Bật lửa",
        "Pin AA/AAA",
        "Pin 9V",
        "Ổ cắm điện",
        "Cục sạc",
        "Dây sạc",
    }.issubset(set(SPECIALIST_REVIEW_LABELS))


def test_legacy_eggshell_overlay_is_repaired_before_display() -> None:
    assert waste_detection_display_name("Organic", "V? tr?ng g?") == "Vỏ trứng gà"
