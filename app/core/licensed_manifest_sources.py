"""Build licensed image manifest rows from verified source systems."""

from __future__ import annotations

import csv
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from app.core.licensed_source_ingestion import validate_manual_url_source

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
WIKIMEDIA_USER_AGENT = "TrashSorterPro/2.0 (jasonbmt06@gmail.com) phase12-manifest"
RASTER_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_QUERIES = {
    "Pen": ("ballpoint pen", "blue ballpoint pen"),
    "Battery": ("AA battery", "AAA battery"),
    "Toothbrush": ("toothbrush",),
    "Textile": ("disposable face mask", "surgical mask"),
    "Disposable tableware": (
        "styrofoam food container",
        "foam food container",
        "polystyrene food container",
        "expanded polystyrene food container",
        "EPS food container",
        "takeaway food container",
        "takeout container",
        "take-out box",
        "disposable plastic cutlery",
        "plastic utensils",
        "plastic spoon",
        "disposable spoon",
        "plastic fork",
        "disposable fork",
        "plastic knife",
        "disposable knife",
        "plastic straw",
        "drinking straw",
        "single-use plastic straw",
        "coffee stirrer",
        "styrofoam cup",
        "foam cup",
        "polystyrene cup",
        "disposable cup",
        "single-use plastic cup",
        "disposable plate",
        "paper plate",
        "paper cup",
        "foam tray",
        "paper food container",
        "plastic food container",
        "disposable chopsticks",
        "wooden chopsticks",
    ),
    "Unknown plastic": (
        "snack wrapper",
        "plastic food wrapper",
        "candy wrapper",
        "medicine blister pack",
        "plastic packaging waste",
    ),
    "Tetra pack": ("tetra pak carton", "milk carton"),
    "Ceramic": (
        "ceramic bowl",
        "ceramic cup",
        "ceramic mug",
        "ceramic plate",
        "ceramic teacup",
        "porcelain bowl",
        "porcelain cup",
        "porcelain mug",
        "porcelain plate",
        "porcelain teacup",
        "broken ceramic",
        "broken porcelain",
        "broken pottery",
        "ceramic shard",
        "pottery sherd",
    ),
    "Aerosols": ("aerosol can", "spray can"),
    "Electronics": (
        "small electronics waste",
        "electronic waste charger",
        "USB cable",
        "phone charger",
        "computer mouse",
        "circuit board",
    ),
}


def wikimedia_rows(class_name: str, target: int) -> list[dict[str, object]]:
    return wikimedia_rows_for_queries(class_name, DEFAULT_QUERIES.get(class_name, (class_name,)), target)


def wikimedia_rows_for_queries(
    class_name: str,
    queries: tuple[str, ...],
    target: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for query in queries:
        for page in _query_wikimedia(query, max(target * 2, 20)):
            row = _row_from_wikimedia_page(page, class_name)
            if row is not None:
                image_url = str(row.get("image_url") or "")
                if image_url in seen_urls:
                    continue
                seen_urls.add(image_url)
                rows.append(row)
            if len(rows) >= target:
                return rows
    return rows


def csv_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            manifest_row = _row_from_csv_dict(row)
            if manifest_row is not None:
                rows.append(manifest_row)
    return rows


def class_counts(items: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        name = str(item.get("canonical_class") or "")
        counts[name] = counts.get(name, 0) + 1
    return counts


def count_class(items: list[dict[str, object]], class_name: str) -> int:
    return sum(1 for item in items if item.get("canonical_class") == class_name)


def _query_wikimedia(query: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": query,
        "gsrlimit": str(min(limit, 50)),
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": "640",
    }
    url = f"{WIKIMEDIA_API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": WIKIMEDIA_USER_AGENT})
    time.sleep(0.25)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return []
    pages = payload.get("query", {}).get("pages", {})
    return [page for page in pages.values() if isinstance(page, dict)]


def _row_from_wikimedia_page(page: dict[str, Any], class_name: str) -> dict[str, object] | None:
    info = (page.get("imageinfo") or [{}])[0]
    if str(info.get("mime") or "") not in RASTER_MIME_TYPES:
        return None
    image_url = str(info.get("thumburl") or info.get("url") or "")
    original_image_url = str(info.get("url") or "")
    source_page_url = str(info.get("descriptionurl") or "")
    title_text = " ".join(
        urllib.parse.unquote(str(value or "")).lower()
        for value in (page.get("title"), image_url, source_page_url)
    )
    if not _looks_relevant_for_class(title_text, class_name):
        return None
    meta = info.get("extmetadata") or {}
    license_name = _meta_value(meta, "LicenseShortName") or _meta_value(meta, "UsageTerms")
    author = _clean_html(_meta_value(meta, "Artist") or _meta_value(meta, "Credit") or "Wikimedia Commons")
    return _validated_row(
        class_name,
        image_url,
        source_page_url,
        license_name,
        author,
        "wikimedia",
        original_image_url=original_image_url,
    )


def _row_from_csv_dict(row: dict[str, str]) -> dict[str, object] | None:
    class_name = str(row.get("canonical_class") or row.get("cls_name") or "").strip()
    image_url = str(row.get("image_url") or row.get("source_url") or "").strip()
    source_page_url = str(row.get("source_page_url") or "").strip()
    license_name = str(row.get("license") or row.get("source_license") or "").strip()
    author = str(row.get("author") or row.get("source_author") or "").strip()
    source_type = str(row.get("source_type") or "open_images").strip()
    return _validated_row(class_name, image_url, source_page_url, license_name, author, source_type)


def _validated_row(
    class_name: str,
    image_url: str,
    source_page_url: str,
    license_name: str,
    author: str,
    source_type: str,
    original_image_url: str = "",
) -> dict[str, object] | None:
    try:
        validated = validate_manual_url_source(
            class_name=class_name,
            source_url=image_url,
            source_page_url=source_page_url,
            source_license=license_name,
            source_author=author,
            source_type=source_type,
            generated=False,
        )
    except ValueError:
        return None
    return {
        "image_url": image_url,
        "source_page_url": source_page_url,
        "license": license_name,
        "author": author,
        "source_type": source_type,
        "canonical_class": validated["canonical_class"],
        "original_image_url": original_image_url or image_url,
        "generated": False,
    }


def _looks_relevant_for_class(text: str, class_name: str) -> bool:
    if class_name == "Disposable tableware":
        return any(
            token in text
            for token in (
                "styrofoam",
                "foam",
                "clamshell",
                "takeaway",
                "takeout",
                "take-out",
                "disposable",
                "plastic spoon",
                "plastic_spoon",
                "plastic fork",
                "plastic_fork",
                "plastic knife",
                "plastic_knife",
                "plastic straw",
                "plastic_straw",
                "drinking straw",
                "coffee stirrer",
                "cutlery",
                "utensil",
                "food container",
                "food_container",
                "paper cup",
                "paper_cup",
                "paper plate",
                "paper_plate",
                "foam tray",
                "foam_tray",
                "chopsticks",
                "plastic food container",
                "plastic_food_container",
            )
        )
    if class_name == "Ceramic":
        return any(
            token in text
            for token in (
                "ceramic",
                "porcelain",
                "pottery",
                "earthenware",
                "stoneware",
                "faience",
                "sherd",
                "shard",
                "bowl",
                "cup",
                "mug",
                "plate",
            )
        )
    return True


def _meta_value(meta: dict[str, Any], key: str) -> str:
    value = meta.get(key, {})
    return str(value.get("value") or "") if isinstance(value, dict) else ""


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value))).strip()
