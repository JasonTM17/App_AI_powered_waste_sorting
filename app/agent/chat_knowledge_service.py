"""Local knowledge/RAG store for role-aware Trash Sorter chat."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from app.utils.paths import app_data_dir, resource_path

ChatRole = Literal["admin", "user"]
EntrySource = Literal["seed", "local"]

SEED_PACK_PATH = resource_path("app/agent/knowledge_packs/trash_sorter_base.json")
LOCAL_PACK_NAME = "chat_knowledge.local.json"
ALWAYS_INCLUDE_IDS = ("taxonomy-three-bins", "admin-data-safety")
ROLE_DEFAULT_IDS: dict[ChatRole, tuple[str, ...]] = {
    "admin": ("admin-operational-triage", "deepseek-backend-key-setup"),
    "user": ("user-eco-score-habits", "user-wellness-boundary"),
}


@dataclass(frozen=True)
class KnowledgeEntry:
    id: str
    title: str
    roles: frozenset[ChatRole]
    keywords: tuple[str, ...]
    text: str
    enabled: bool = True
    updated_at: str = ""
    source: EntrySource = "seed"


@dataclass(frozen=True)
class KnowledgeCatalog:
    entries: list[KnowledgeEntry]
    local_path: Path
    status: str = "ok"
    error: str = ""


def local_knowledge_path() -> Path:
    return app_data_dir() / LOCAL_PACK_NAME


def load_knowledge_catalog() -> KnowledgeCatalog:
    """Load seed knowledge plus local overrides without raising on local file errors."""
    seed_entries = _read_pack(SEED_PACK_PATH, source="seed", strict=True)
    local_path = local_knowledge_path()
    try:
        local_entries = _read_pack(local_path, source="local", strict=False) if local_path.exists() else []
    except ValueError as exc:
        return KnowledgeCatalog(
            entries=seed_entries,
            local_path=local_path,
            status="local_error",
            error=str(exc),
        )
    merged = {entry.id: entry for entry in seed_entries}
    for entry in local_entries:
        merged[entry.id] = entry
    return KnowledgeCatalog(entries=sorted(merged.values(), key=lambda item: item.id), local_path=local_path)


def list_knowledge_entries() -> KnowledgeCatalog:
    return load_knowledge_catalog()


def upsert_knowledge_entry(payload: Mapping[str, object]) -> KnowledgeCatalog:
    local_path = local_knowledge_path()
    entries = {entry.id: entry for entry in _local_entries_or_empty(local_path)}
    entry = _entry_from_payload(payload, source="local")
    entries[entry.id] = entry
    _write_local_entries(local_path, entries.values())
    return load_knowledge_catalog()


def patch_knowledge_entry(entry_id: str, payload: Mapping[str, object]) -> KnowledgeCatalog:
    catalog = load_knowledge_catalog()
    current = next((entry for entry in catalog.entries if entry.id == entry_id), None)
    if current is None:
        raise KeyError(entry_id)
    merged: dict[str, object] = _entry_to_dict(current)
    for key in ("title", "roles", "keywords", "text", "enabled"):
        if key in payload and payload[key] is not None:
            merged[key] = payload[key]
    merged["id"] = entry_id
    merged["source"] = "local"
    merged["updated_at"] = _now_iso()
    return upsert_knowledge_entry(merged)


def reload_knowledge_entries() -> KnowledgeCatalog:
    return load_knowledge_catalog()


def evaluate_knowledge_retrieval(
    *,
    role: ChatRole,
    question: str,
    context: dict[str, object] | None = None,
    limit: int = 6,
) -> dict[str, object]:
    ranked = _rank_entries(role=role, question=question, context=context)
    selected = _select_ranked(role, ranked, limit=limit)
    return {
        "role": role,
        "question": question,
        "snippets": [_to_snippet(entry) for entry in selected],
        "scores": [{"id": entry.id, "title": entry.title, "score": score} for score, entry in ranked[:10]],
        "payload_chars": sum(len(entry.text) for entry in selected),
    }


def retrieve_knowledge_snippets(
    *,
    role: ChatRole,
    question: str,
    context: dict[str, object] | None = None,
    limit: int = 6,
) -> list[dict[str, str]]:
    """Return role-appropriate snippets ranked by accent-insensitive relevance."""
    ranked = _rank_entries(role=role, question=question, context=context)
    selected = _select_ranked(role, ranked, limit=limit)
    return [_to_snippet(entry) for entry in selected]


def _rank_entries(
    *,
    role: ChatRole,
    question: str,
    context: dict[str, object] | None,
) -> list[tuple[int, KnowledgeEntry]]:
    query_tokens = _tokens(question)
    query_tokens.update(_context_tokens(context))
    scored: list[tuple[int, KnowledgeEntry]] = []
    for entry in load_knowledge_catalog().entries:
        if not entry.enabled or role not in entry.roles:
            continue
        score = _entry_score(entry, query_tokens)
        scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return scored


def _select_ranked(role: ChatRole, ranked: Sequence[tuple[int, KnowledgeEntry]], *, limit: int) -> list[KnowledgeEntry]:
    by_id = {entry.id: entry for _score, entry in ranked}
    selected: list[KnowledgeEntry] = []
    for entry_id in (*ALWAYS_INCLUDE_IDS, *ROLE_DEFAULT_IDS[role]):
        entry = by_id.get(entry_id)
        if entry and entry not in selected:
            selected.append(entry)
    for score, entry in ranked:
        if len(selected) >= max(1, min(limit, 8)):
            break
        if score <= 0 and selected:
            continue
        if entry not in selected:
            selected.append(entry)
    return selected[: max(1, min(limit, 8))]


def _entry_score(entry: KnowledgeEntry, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0
    title_tokens = _tokens(entry.title)
    keyword_tokens = set().union(*(_tokens(item) for item in entry.keywords)) if entry.keywords else set()
    text_tokens = _tokens(entry.text)
    return (
        len(query_tokens & title_tokens) * 5
        + len(query_tokens & keyword_tokens) * 4
        + len(query_tokens & text_tokens)
    )


def _read_pack(path: Path, *, source: EntrySource, strict: bool) -> list[KnowledgeEntry]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if strict:
            raise
        return []
    except json.JSONDecodeError as exc:
        raise ValueError(f"Knowledge file is not valid JSON: {path}") from exc
    rows = payload.get("entries", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"Knowledge file must contain an entries list: {path}")
    return [_entry_from_payload(row, source=source) for row in rows if isinstance(row, dict)]


def _local_entries_or_empty(path: Path) -> list[KnowledgeEntry]:
    try:
        return _read_pack(path, source="local", strict=False) if path.exists() else []
    except ValueError:
        return []


def _entry_from_payload(payload: Mapping[str, object], *, source: EntrySource) -> KnowledgeEntry:
    title = _clean_text(payload.get("title", ""), limit=140)
    entry_id = _clean_id(payload.get("id", "")) or _slug(title)
    roles = _roles(payload.get("roles", []))
    keywords = tuple(_clean_text(item, limit=80) for item in _list(payload.get("keywords", [])) if _clean_text(item))
    return KnowledgeEntry(
        id=entry_id,
        title=title or entry_id,
        roles=roles,
        keywords=keywords,
        text=_clean_text(payload.get("text", ""), limit=1600),
        enabled=bool(payload.get("enabled", True)),
        updated_at=_clean_text(payload.get("updated_at", ""), limit=40) or _now_iso(),
        source=source,
    )


def _write_local_entries(path: Path, entries: Sequence[KnowledgeEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "entries": [_entry_to_dict(entry, source="local") for entry in entries]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _entry_to_dict(entry: KnowledgeEntry, *, source: EntrySource | None = None) -> dict[str, object]:
    return {
        "id": entry.id,
        "title": entry.title,
        "roles": sorted(entry.roles),
        "keywords": list(entry.keywords),
        "text": entry.text,
        "enabled": entry.enabled,
        "updated_at": entry.updated_at or _now_iso(),
        "source": source or entry.source,
    }


def _to_snippet(entry: KnowledgeEntry) -> dict[str, str]:
    return {"id": entry.id, "title": entry.title, "text": _clean_text(entry.text, limit=900)}


def _context_tokens(context: dict[str, object] | None) -> set[str]:
    if not context:
        return set()
    return _tokens(" ".join(_flatten_values(context)))


def _flatten_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        items: list[str] = []
        for nested in value.values():
            items.extend(_flatten_values(nested))
        return items
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        items = []
        for nested in value:
            items.extend(_flatten_values(nested))
        return items
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    return []


def _tokens(value: str) -> set[str]:
    normalized = _strip_accents(value)
    return {part.casefold() for part in re.findall(r"[\w]+", normalized) if len(part) > 1}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value))
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _roles(value: object) -> frozenset[ChatRole]:
    roles = {str(item).strip() for item in _list(value)}
    clean = {item for item in roles if item in {"admin", "user"}}
    return frozenset(clean or {"admin", "user"})  # type: ignore[arg-type]


def _list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _clean_id(value: object) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", _strip_accents(str(value or "").casefold())).strip("-")[:80]


def _slug(value: str) -> str:
    return _clean_id(value) or f"knowledge-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _clean_text(value: object, *, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


__all__ = [
    "ChatRole",
    "KnowledgeCatalog",
    "KnowledgeEntry",
    "evaluate_knowledge_retrieval",
    "list_knowledge_entries",
    "local_knowledge_path",
    "patch_knowledge_entry",
    "reload_knowledge_entries",
    "retrieve_knowledge_snippets",
    "upsert_knowledge_entry",
]
