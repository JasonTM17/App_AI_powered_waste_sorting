from app.core.vision_label_provider import suggest_unknown_labels
from app.core.web_source_discovery import discover_web_sources


def _classes(result: dict[str, object]) -> list[str]:
    return [str(item["canonical_class"]) for item in result["suggestions"]]  # type: ignore[index]


def test_vision_label_provider_maps_vietnamese_aliases_to_routes(monkeypatch):
    monkeypatch.delenv("VISION_LABEL_COMMAND", raising=False)

    pen = suggest_unknown_labels(manual_hint="but bi")
    blister = suggest_unknown_labels(manual_hint="vi thuoc")
    mask = suggest_unknown_labels(manual_hint="khau trang")

    assert _classes(pen) == ["Pen"]
    assert pen["suggestions"][0]["command"] == "R"  # type: ignore[index]
    assert pen["suggestions"][0]["bin_index"] == 2  # type: ignore[index]
    assert _classes(blister) == ["Unknown plastic"]
    assert _classes(mask) == ["Textile"]


def test_vision_label_provider_blocks_labels_outside_taxonomy(monkeypatch):
    monkeypatch.delenv("VISION_LABEL_COMMAND", raising=False)

    result = suggest_unknown_labels(manual_hint="Yoga Mat")

    assert result["suggestions"] == []
    assert "not mapped" in str(result["message"])


def test_web_source_discovery_is_unavailable_without_google_config(monkeypatch):
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)

    result = discover_web_sources(cls_name="Pen", query="but bi", limit=3)

    assert result["available"] is False
    assert result["candidates"] == []
    assert "not configured" in str(result["message"])


def test_web_source_discovery_rejects_non_taxonomy_class(monkeypatch):
    monkeypatch.setenv("GOOGLE_CSE_API_KEY", "key")
    monkeypatch.setenv("GOOGLE_CSE_ID", "cx")

    result = discover_web_sources(cls_name="Yoga Mat", query="", limit=3)

    assert result["available"] is False
    assert result["candidates"] == []
    assert "45-class" in str(result["message"])
