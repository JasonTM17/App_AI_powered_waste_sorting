"""Summarize restored history captures that still need manual review.

The report is intentionally conservative: it never changes queue metadata and
never treats old history labels as ground truth.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

MANUAL_VISUAL_NOTES: dict[int, tuple[str, str]] = {
    632: ("quarantine", "No clear single object; do not train."),
    667: ("candidate", "Likely ballpoint pen; bbox/label must be reviewed."),
    677: ("candidate", "Likely ballpoint pen; old label was wrong."),
    694: ("quarantine", "Occluded or unclear frame; do not train."),
    726: ("candidate", "Likely ballpoint pen; current model drifted."),
    750: ("quarantine", "OBS/no-camera frame; do not train."),
    753: ("quarantine", "OBS/no-camera frame; do not train."),
    764: ("candidate", "Likely metal spoon; current model drifted."),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("dataset_v2/low_conf_queue"),
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("runs/eval/history-capture-model-audit.json"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/history-recovery-review-manifest.md"),
    )
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()

    audit_rows = _load_audit_rows(args.audit)
    rows = _load_queue_rows(args.queue, audit_rows)
    report = build_markdown(rows, args.queue, args.audit, args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "queue_rows": len(rows),
                "out": str(args.out.resolve()),
                "high_priority": sum(row["review_priority"] == "high" for row in rows),
                "quarantine_notes": sum(row["visual_status"] == "quarantine" for row in rows),
                "candidate_notes": sum(row["visual_status"] == "candidate" for row in rows),
            },
            ensure_ascii=False,
        )
    )
    return 0


def build_markdown(rows: list[dict[str, Any]], queue: Path, audit: Path, limit: int) -> str:
    priority_counts = Counter(str(row["review_priority"]) for row in rows)
    old_counts = Counter(str(row["old_model_label"]) for row in rows)
    current_counts = Counter(str(row["current_model_label"]) for row in rows)
    by_pair: Counter[str] = Counter(
        f"{row['old_model_label']} -> {row['current_model_label']}" for row in rows
    )
    route_rows = [row for row in rows if row.get("route_agreement") is False]
    exact_drift_rows = [row for row in rows if row.get("exact_agreement") is False]

    lines = [
        "# History Recovery Review Manifest",
        "",
        "This file is generated from preserved camera history and queue metadata.",
        "Old history labels are model predictions, not human ground truth.",
        "",
        "## Summary",
        "",
        f"- Queue: `{queue}`",
        f"- Audit source: `{audit}`",
        f"- Restored captures: {len(rows)}",
        f"- High priority review: {priority_counts.get('high', 0)}",
        f"- Medium priority review: {priority_counts.get('medium', 0)}",
        f"- Exact label drift: {len(exact_drift_rows)}",
        f"- Route/bin drift: {len(route_rows)}",
        f"- Manual candidate notes: {sum(row['visual_status'] == 'candidate' for row in rows)}",
        f"- Manual quarantine notes: {sum(row['visual_status'] == 'quarantine' for row in rows)}",
        "",
        "## Review Rules",
        "",
        "- Do not train from any `history_recovery_*.jpg` until Admin reviews label and bbox.",
        "- Keep `training_excluded=true` and `recognition_enabled=false` for unreviewed images.",
        "- Quarantine no-camera, hand-covered, blank, or unclear frames.",
        "- For clear objects, correct the full-object bbox before enabling as reference/training.",
        "- Battery/pin samples must be marked hazardous and must not auto-sort.",
        "",
        "## Top Old Labels",
        "",
        _counter_table(old_counts, "Old model label"),
        "",
        "## Top Current Labels",
        "",
        _counter_table(current_counts, "Current model label"),
        "",
        "## Top Drifts",
        "",
        _counter_table(by_pair, "Old -> current"),
        "",
        "## Priority Review Rows",
        "",
        "| history_id | priority | old label | current label | conf | exact | route | visual note | queue image |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in _priority_rows(rows)[: max(0, limit)]:
        lines.append(
            "| {history_id} | {review_priority} | {old_model_label} | {current_model_label} | "
            "{current_model_confidence:.2f} | {exact} | {route} | {visual_note} | `{image}` |".format(
                history_id=row["history_id"],
                review_priority=row["review_priority"],
                old_model_label=_escape_cell(str(row["old_model_label"])),
                current_model_label=_escape_cell(str(row["current_model_label"])),
                current_model_confidence=float(row["current_model_confidence"]),
                exact="yes" if row.get("exact_agreement") else "no",
                route="yes" if row.get("route_agreement") else "no",
                visual_note=_escape_cell(str(row["visual_note"] or "")),
                image=Path(str(row["image_path"])).as_posix(),
            )
        )
    lines.extend(
        [
            "",
            "## Suggested Next Pass",
            "",
            "1. Review quarantine notes first and mark them no-evidence.",
            "2. Review clear pen/spoon/bottle/leaf examples and correct bbox.",
            "3. Capture new real-camera samples for charger, socket, cable, comb, marker, lighter, plastic bag, eggshell, and batteries.",
            "4. Train specialist only after enough reviewed images exist per label.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_audit_rows(path: Path) -> dict[int, dict[str, Any]]:
    if not path.is_file():
        return {}
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(row["history_id"]): row
        for row in report.get("rows", [])
        if isinstance(row, dict) and "history_id" in row
    }


def _load_queue_rows(queue: Path, audit_rows: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for meta_path in sorted(queue.glob("history_recovery_*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        history_id = int(meta.get("history_id") or meta_path.stem.rsplit("_", 1)[-1])
        audit = audit_rows.get(history_id, {})
        status, note = MANUAL_VISUAL_NOTES.get(history_id, ("", ""))
        image_path = meta_path.with_suffix(".jpg")
        rows.append(
            {
                "history_id": history_id,
                "review_priority": str(meta.get("review_priority") or ""),
                "old_model_label": str(meta.get("old_model_label") or ""),
                "current_model_label": str(meta.get("current_model_label") or ""),
                "current_model_confidence": float(meta.get("current_model_confidence") or 0.0),
                "training_excluded": bool(meta.get("training_excluded", True)),
                "recognition_enabled": bool(meta.get("recognition_enabled", False)),
                "reviewed": bool(meta.get("reviewed", False)),
                "image_path": str(image_path),
                "meta_path": str(meta_path),
                "blur_score": float(meta.get("blur_score") or 0.0),
                "exact_agreement": audit.get("exact_agreement"),
                "route_agreement": audit.get("route_agreement"),
                "visual_status": status,
                "visual_note": note,
            }
        )
    return rows


def _priority_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority_rank = {"high": 0, "hazardous": 0, "medium": 1, "low": 2}
    status_rank = {"quarantine": 0, "candidate": 1, "": 2}
    return sorted(
        rows,
        key=lambda row: (
            priority_rank.get(str(row["review_priority"]), 3),
            status_rank.get(str(row["visual_status"]), 2),
            bool(row.get("route_agreement")),
            float(row["current_model_confidence"]),
            int(row["history_id"]),
        ),
    )


def _counter_table(counter: Counter[str], label: str) -> str:
    if not counter:
        return f"| {label} | count |\n| --- | ---: |"
    lines = [f"| {label} | count |", "| --- | ---: |"]
    for key, count in counter.most_common(12):
        lines.append(f"| {_escape_cell(str(key))} | {count} |")
    return "\n".join(lines)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


if __name__ == "__main__":
    raise SystemExit(main())
