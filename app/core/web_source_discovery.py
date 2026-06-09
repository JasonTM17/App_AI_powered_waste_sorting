"""Licensed web source discovery for Learn Now."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.waste_categories import TRAINING_CLASS_ORDER_45, canonical_class_name


@dataclass(frozen=True)
class WebSourceCandidate:
    title: str
    image_url: str
    source_page_url: str
    source_type: str
    canonical_class: str
    license: str = ""
    author: str = ""
    thumbnail_url: str = ""
    import_ready: bool = False
    reason: str = "License metadata must be verified before import."

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def discover_web_sources(
    *,
    cls_name: str,
    query: str,
    limit: int = 10,
) -> dict[str, object]:
    """Search configured web sources without importing unverified images."""
    class_name = canonical_class_name(cls_name)
    if class_name not in TRAINING_CLASS_ORDER_45:
        return _response(False, "Class is not in the 45-class taxonomy.", [])
    api_key = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_ID", "").strip()
    if not api_key or not cx:
        return _response(
            False,
            "Google Programmable Search is not configured; use Wikimedia/Open Images or manual URL with license metadata.",
            [],
        )
    search_query = _query_text(query, class_name)
    try:
        data = _google_cse(api_key, cx, search_query, limit)
    except httpx.HTTPError as exc:
        return _response(False, f"Google search failed: {exc}", [])
    candidates = [_candidate(item, class_name) for item in data.get("items") or []]
    return _response(True, f"Found {len(candidates)} discovery candidate(s). Verify license before import.", candidates)


def _google_cse(api_key: str, cx: str, query: str, limit: int) -> dict[str, Any]:
    params: dict[str, str | int] = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": max(1, min(10, int(limit))),
        "rights": "cc_publicdomain,cc_attribute,cc_sharealike",
        "safe": "active",
    }
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        res = client.get("https://www.googleapis.com/customsearch/v1", params=params)
        res.raise_for_status()
        return res.json()


def _candidate(item: dict[str, Any], class_name: str) -> WebSourceCandidate:
    raw_image = item.get("image")
    image: dict[str, Any] = raw_image if isinstance(raw_image, dict) else {}
    source_page = str(image.get("contextLink") or item.get("link") or "")
    image_url = str(item.get("link") or "")
    title = str(item.get("title") or class_name)
    thumbnail = str(image.get("thumbnailLink") or "")
    page = source_page.casefold()
    is_wikimedia = "commons.wikimedia.org" in page or "wikimedia.org" in page
    source_type = "wikimedia" if is_wikimedia else "google_cse"
    reason = (
        "Wikimedia result still needs license/author metadata before import."
        if is_wikimedia
        else "Google result is discovery-only until source license and author are verified."
    )
    return WebSourceCandidate(
        title=title,
        image_url=image_url,
        source_page_url=source_page,
        source_type=source_type,
        canonical_class=class_name,
        thumbnail_url=thumbnail,
        reason=reason,
    )


def _query_text(query: str, class_name: str) -> str:
    clean = str(query or "").strip()
    if clean:
        return clean
    return f"{class_name} waste object Wikimedia Commons"


def _response(
    available: bool,
    message: str,
    candidates: list[WebSourceCandidate],
) -> dict[str, object]:
    return {
        "available": available,
        "message": message,
        "candidates": [item.as_dict() for item in candidates],
    }


__all__ = ["WebSourceCandidate", "discover_web_sources"]
