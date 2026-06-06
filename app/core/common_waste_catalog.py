"""Curated common household waste aliases for manual training."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.waste_categories import category_for_class, default_class_id_for_name


@dataclass(frozen=True)
class CommonWasteItem:
    label: str
    canonical_class: str
    aliases: tuple[str, ...]
    notes: str = ""

    @property
    def class_id(self) -> int | None:
        return default_class_id_for_name(self.canonical_class)

    @property
    def command(self) -> str:
        return category_for_class(self.canonical_class).code

    @property
    def bin_index(self) -> int:
        return category_for_class(self.canonical_class).bin_index

    @property
    def route_label(self) -> str:
        return category_for_class(self.canonical_class).name

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "canonical_class": self.canonical_class,
            "class_id": self.class_id,
            "aliases": list(self.aliases),
            "command": self.command,
            "bin_index": self.bin_index,
            "route_label": self.route_label,
            "notes": self.notes,
        }


COMMON_WASTE_ITEMS: tuple[CommonWasteItem, ...] = (
    CommonWasteItem("Vo chuoi", "Organic", ("vo chuoi", "banana peel")),
    CommonWasteItem("Vo cam/trai cay", "Organic", ("vo cam", "vo trai cay", "fruit peel")),
    CommonWasteItem("Rau thua", "Organic", ("rau thua", "rau cu thua", "vegetable scraps")),
    CommonWasteItem("Com/thuc an thua", "Organic", ("com thua", "thuc an thua", "leftover food")),
    CommonWasteItem("La cay", "Organic", ("la cay", "leaf waste", "wood"), "Use Organic for soft leaves."),
    CommonWasteItem("Lon nuoc", "Aluminum can", ("lon nuoc", "lon bia", "lon nuoc ngot", "beer can")),
    CommonWasteItem("Chai PET", "Plastic bottle", ("chai pet", "chai nhua pet", "chai nuoc suoi")),
    CommonWasteItem("Chai thuy tinh", "Glass bottle", ("chai thuy tinh", "lo thuy tinh", "glass jar")),
    CommonWasteItem("Hop giay", "Cardboard", ("hop giay", "hop carton", "bia carton")),
    CommonWasteItem("Giay bao", "Paper", ("giay", "bao", "newspaper")),
    CommonWasteItem("Tui nylon sach", "Plastic bag", ("tui nylon sach", "tui nylon", "plastic bag")),
    CommonWasteItem("Coc nhua sach", "Plastic cup", ("coc nhua", "ly nhua", "ly tra sua")),
    CommonWasteItem("Hop sua giay", "Tetra pack", ("hop sua giay", "milk carton", "tetra pack")),
    CommonWasteItem("But bi", "Pen", ("but bi", "cay but", "pen")),
    CommonWasteItem("But chi", "Pen", ("but chi", "pencil"), "Current 45-class model stores writing tools as Pen."),
    CommonWasteItem("But long", "Pen", ("but long", "marker"), "Current 45-class model stores writing tools as Pen."),
    CommonWasteItem("Ban chai danh rang", "Toothbrush", ("ban chai danh rang", "toothbrush")),
    CommonWasteItem("Pin", "Battery", ("pin", "pin tieu", "battery")),
    CommonWasteItem("Khau trang", "Textile", ("khau trang", "face mask")),
    CommonWasteItem("Chen/bat gom su", "Ceramic", ("chen su", "bat su", "do gom su", "ceramic bowl")),
    CommonWasteItem(
        "Do dung mot lan",
        "Disposable tableware",
        ("ong hut nhua", "muong nhua", "dua dung mot lan", "foam food box"),
    ),
    CommonWasteItem("Vo goi ban", "Unknown plastic", ("vo goi ban", "vo bim bim", "snack wrapper")),
)


COMMON_WASTE_ALIASES: dict[str, str] = {
    alias.casefold(): item.canonical_class
    for item in COMMON_WASTE_ITEMS
    for alias in (item.label, item.canonical_class, *item.aliases)
}


def common_waste_catalog() -> list[dict[str, object]]:
    return [item.as_dict() for item in COMMON_WASTE_ITEMS]


def common_waste_class_names() -> tuple[str, ...]:
    seen: set[str] = set()
    names: list[str] = []
    for item in COMMON_WASTE_ITEMS:
        if item.canonical_class not in seen:
            seen.add(item.canonical_class)
            names.append(item.canonical_class)
    return tuple(names)


__all__ = [
    "COMMON_WASTE_ALIASES",
    "COMMON_WASTE_ITEMS",
    "CommonWasteItem",
    "common_waste_catalog",
    "common_waste_class_names",
]
