from __future__ import annotations

from app.core.common_waste_catalog import CommonWasteItem
from scripts.build_vietnam50_licensed_manifest import _queries_for_item


def test_queries_prioritize_english_alias_before_vietnamese_alias():
    item = CommonWasteItem(
        "Lon nuoc",
        "Aluminum can",
        ("lon nuoc", "lon bia", "beer can"),
    )

    queries = _queries_for_item(item)

    assert queries[:2] == ("beer can", "Aluminum can")
    assert "lon nuoc" in queries
