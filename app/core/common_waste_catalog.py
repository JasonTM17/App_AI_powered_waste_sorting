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
    CommonWasteItem(
        "V\u1ecf tr\u1ee9ng g\u00e0",
        "Organic",
        ("vo trung", "vo trung ga", "v\u1ecf tr\u1ee9ng", "v\u1ecf tr\u1ee9ng g\u00e0", "eggshell"),
        "Runtime display may relabel clear eggshell frames.",
    ),
    CommonWasteItem("Ba ca phe/tra", "Organic", ("ba ca phe", "ba tra", "coffee grounds", "tea leaves")),
    CommonWasteItem("La cay", "Organic", ("la cay", "leaf waste", "wood"), "Use Organic for soft leaves."),
    CommonWasteItem("Vo dua/vo trai cay cung", "Organic", ("vo dua", "vo xoai", "vo dua hau", "fruit rind")),
    CommonWasteItem("Xuong/thit ca thua", "Organic", ("xuong", "xuong ga", "xuong ca", "fish bone")),
    CommonWasteItem("Ba mia", "Organic", ("ba mia", "bã mía", "sugarcane bagasse")),
    CommonWasteItem("Lon nuoc", "Aluminum can", ("lon nuoc", "lon bia", "lon nuoc ngot", "beer can")),
    CommonWasteItem("Lon do hop", "Tin", ("lon do hop", "hop ca", "food can")),
    CommonWasteItem("Vo lon sua bot", "Tin", ("lon sua bot", "vo lon sua", "milk powder can")),
    CommonWasteItem("Nap chai kim loai", "Aluminum caps", ("nap lon", "nap chai kim loai", "metal bottle cap")),
    CommonWasteItem("Chai PET", "Plastic bottle", ("chai pet", "chai nhua pet", "chai nuoc suoi")),
    CommonWasteItem("Chai dau goi/sua tam", "Plastic bottle", ("chai dau goi", "chai sua tam", "shampoo bottle")),
    CommonWasteItem("Chai gia vi nhua", "Plastic bottle", ("chai tuong ot", "chai nuoc tuong", "chai dau an")),
    CommonWasteItem("Nap chai nhua", "Plastic caps", ("nap chai nhua", "plastic bottle cap")),
    CommonWasteItem("Chai thuy tinh", "Glass bottle", ("chai thuy tinh", "lo thuy tinh", "glass jar")),
    CommonWasteItem("Lo thuoc thuy tinh", "Glass bottle", ("lo thuoc thuy tinh", "chai thuoc thuy tinh")),
    CommonWasteItem("Hop giay", "Cardboard", ("hop giay", "hop carton", "bia carton")),
    CommonWasteItem("Thung carton", "Cardboard", ("thung carton", "carton box")),
    CommonWasteItem("Vo hop banh giay", "Cardboard", ("vo hop banh", "hop banh giay", "paper snack box")),
    CommonWasteItem("Giay bao", "Paper", ("giay", "bao", "newspaper")),
    CommonWasteItem("Giay van phong/sach cu", "Paper", ("giay van phong", "sach cu", "vo tap", "office paper")),
    CommonWasteItem("Ly giay", "Paper cups", ("ly giay", "coc giay", "paper cup")),
    CommonWasteItem("Bao bi giao hang", "Postal packaging", ("bao bi giao hang", "tui giao hang", "shipping mailer")),
    CommonWasteItem(
        "B\u00ec ni l\u00f4ng",
        "Plastic bag",
        ("bi ni long", "b\u00ec ni l\u00f4ng", "tui nylon sach", "tui nylon", "plastic bag"),
    ),
    CommonWasteItem("Tui zip", "Zip plastic bag", ("tui zip", "zip plastic bag")),
    CommonWasteItem("Mang boc thuc pham", "Stretch film", ("mang boc thuc pham", "plastic wrap")),
    CommonWasteItem("Coc nhua sach", "Plastic cup", ("coc nhua", "ly nhua", "ly tra sua")),
    CommonWasteItem("Hop sua chua/ly nhua nho", "Plastic cup", ("hop sua chua", "ly nhua nho", "yogurt cup")),
    CommonWasteItem("Can nhua", "Plastic canister", ("can nhua", "binh nhua", "plastic jerry can")),
    CommonWasteItem("Chai sua nhua", "Milk bottle", ("chai sua nhua", "milk bottle")),
    CommonWasteItem("Hop sua giay", "Tetra pack", ("hop sua giay", "milk carton", "tetra pack")),
    CommonWasteItem("Giay bac", "Foil", ("giay bac", "mang nhom", "aluminum foil")),
    CommonWasteItem("Phe lieu kim loai nho", "Scrap metal", ("phe lieu kim loai", "sat vun", "scrap metal")),
    CommonWasteItem("But bi", "Pen", ("but bi", "cay but", "pen")),
    CommonWasteItem("But chi", "Pen", ("but chi", "pencil"), "Current 45-class model stores writing tools as Pen."),
    CommonWasteItem("But long", "Pen", ("but long", "marker"), "Current 45-class model stores writing tools as Pen."),
    CommonWasteItem(
        "B\u00fat d\u1ea1",
        "Pen",
        ("but da", "b\u00fat d\u1ea1", "highlighter", "marker pen"),
        "Keep the detailed operator label for the future specialist model.",
    ),
    CommonWasteItem(
        "Cái lược",
        "Unknown plastic",
        ("cai luoc", "lược", "luoc nhua", "lược nhựa", "plastic comb", "comb"),
        "Use reviewed camera references to keep the specific operator label while routing to inorganic bin 2.",
    ),
    CommonWasteItem(
        "Bàn chải tóc",
        "Unknown plastic",
        ("ban chai toc", "bàn chải tóc", "hair brush"),
    ),
    CommonWasteItem(
        "Găng tay cao su",
        "Unknown plastic",
        ("gang tay cao su", "găng tay cao su", "rubber glove"),
    ),
    CommonWasteItem(
        "Miếng bọt biển rửa chén",
        "Unknown plastic",
        ("mieng bot bien", "bọt biển rửa chén", "dish sponge"),
    ),
    CommonWasteItem(
        "Băng keo đã dùng",
        "Unknown plastic",
        ("bang keo", "băng keo", "used adhesive tape"),
    ),
    CommonWasteItem(
        "Băng xoá",
        "Unknown plastic",
        ("bang xoa", "băng xoá", "correction tape"),
    ),
    CommonWasteItem(
        "Dây thun cao su",
        "Unknown plastic",
        ("day thun", "dây thun", "rubber band"),
    ),
    CommonWasteItem("Ban chai danh rang", "Toothbrush", ("ban chai danh rang", "toothbrush")),
    CommonWasteItem("Pin", "Battery", ("pin", "pin tieu", "battery")),
    CommonWasteItem(
        "Pin AA/AAA",
        "Battery",
        ("pin aa", "pin aaa", "pin ti\u1ec3u", "aa battery", "aaa battery"),
        "Hazardous waste: never dispatch without Admin confirmation.",
    ),
    CommonWasteItem(
        "Pin 9V",
        "Battery",
        ("pin 9v", "pin vuong", "9v battery"),
        "Hazardous waste: never dispatch without Admin confirmation.",
    ),
    CommonWasteItem(
        "B\u1eadt l\u1eeda",
        "Unknown plastic",
        ("bat lua", "b\u1eadt l\u1eeda", "lighter"),
        "Review manually before using as a specialist reference.",
    ),
    CommonWasteItem(
        "Bút dạ quang",
        "Pen",
        ("but da quang", "bút dạ quang", "highlighter", "marker highlighter"),
    ),
    CommonWasteItem("Khau trang", "Textile", ("khau trang", "face mask")),
    CommonWasteItem(
        "Quan ao/vai cu",
        "Textile",
        ("quan ao cu", "quần áo cũ", "vai", "vải", "vai cu", "vải cũ", "mieng vai", "miếng vải", "rag", "old clothes"),
    ),
    CommonWasteItem("Chen/bat gom su", "Ceramic", ("chen su", "bat su", "do gom su", "ceramic bowl")),
    CommonWasteItem("Ta giay/giay uot", "Textile", ("ta giay", "giay uot", "wet tissue", "diaper")),
    CommonWasteItem("Tã giấy", "Textile", ("ta em be", "tã em bé", "used diaper")),
    CommonWasteItem("Khăn giấy ướt", "Textile", ("khan giay uot", "khăn ướt", "wet wipe")),
    CommonWasteItem(
        "Do dung mot lan",
        "Disposable tableware",
        ("ong hut nhua", "muong nhua", "dua dung mot lan", "hop xop", "ly xop", "foam food box"),
    ),
    CommonWasteItem("Khay xop", "Disposable tableware", ("khay xop", "hop xop dung thuc an", "styrofoam tray")),
    CommonWasteItem(
        "Hộp xốp bẩn",
        "Disposable tableware",
        ("hop xop ban", "hộp xốp bẩn", "dirty foam food box"),
    ),
    CommonWasteItem("Ống hút nhựa", "Disposable tableware", ("ong hut nhua", "ống hút", "plastic straw")),
    CommonWasteItem(
        "Đũa dùng một lần",
        "Disposable tableware",
        ("dua dung mot lan", "đũa dùng một lần", "disposable chopsticks"),
    ),
    CommonWasteItem("Chai hoa chat gia dung", "Container for household chemicals", ("chai nuoc rua chen", "chai tay rua", "chemical bottle")),
    CommonWasteItem("Binh xit", "Aerosols", ("binh xit", "chai xit", "aerosol can")),
    CommonWasteItem("Do dien tu nho", "Electronics", ("day sac", "tai nghe hong", "bo mach", "small electronics")),
    CommonWasteItem(
        "\u1ed4 c\u1eafm \u0111i\u1ec7n",
        "Electronics",
        ("o cam dien", "\u1ed5 c\u1eafm", "power strip", "socket"),
    ),
    CommonWasteItem(
        "C\u1ee5c s\u1ea1c",
        "Electronics",
        ("cuc sac", "c\u1ee5c s\u1ea1c", "bo sac", "wall charger", "charger"),
    ),
    CommonWasteItem(
        "D\u00e2y s\u1ea1c",
        "Electronics",
        ("day sac", "d\u00e2y s\u1ea1c", "charging cable", "usb cable"),
    ),
    CommonWasteItem("Bong den/den led hong", "Electronics", ("bong den hong", "den led hong", "broken led bulb")),
    CommonWasteItem("Dây sạc hỏng", "Electronics", ("day sac hong", "dây sạc hỏng", "broken charger cable")),
    CommonWasteItem("Tai nghe hỏng", "Electronics", ("tai nghe hong", "broken earphones")),
    CommonWasteItem("Gốm sứ vỡ", "Ceramic", ("gom su vo", "gốm sứ vỡ", "broken ceramic")),
    CommonWasteItem("Vo goi ban", "Unknown plastic", ("vo goi ban", "vo bim bim", "snack wrapper")),
    CommonWasteItem(
        "Bao bì nhiều lớp",
        "Unknown plastic",
        ("bao bi nhieu lop", "bao bì nhiều lớp", "multilayer packaging"),
    ),
    CommonWasteItem("Vo keo/vi thuoc", "Unknown plastic", ("vo keo", "vo banh", "vi thuoc", "candy wrapper", "medicine blister")),
    CommonWasteItem("Dau loc thuoc la", "Unknown plastic", ("dau loc thuoc la", "cigarette butt")),
)


COMMON_WASTE_ALIASES: dict[str, str] = {
    alias.casefold(): item.canonical_class
    for item in COMMON_WASTE_ITEMS
    for alias in (item.label, item.canonical_class, *item.aliases)
}

SPECIALIST_REVIEW_LABELS = (
    "C\u00e1i l\u01b0\u1ee3c",
    "B\u1eadt l\u1eeda",
    "B\u00fat d\u1ea1",
    "Pin AA/AAA",
    "Pin 9V",
    "\u1ed4 c\u1eafm \u0111i\u1ec7n",
    "C\u1ee5c s\u1ea1c",
    "D\u00e2y s\u1ea1c",
)


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
    "SPECIALIST_REVIEW_LABELS",
    "CommonWasteItem",
    "common_waste_catalog",
    "common_waste_class_names",
]
