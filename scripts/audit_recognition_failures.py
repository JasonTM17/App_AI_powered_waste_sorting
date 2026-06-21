"""Audit recognition failure screenshots and auto-review queue metadata.

Screenshots from chat are useful evidence, but they contain UI overlays and
must never become training data. This script only summarizes them and inspects
real camera queue metadata to plan manual labeling.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

TARGET_LABELS = {
    "charger": ("cuc sac", "cục sạc", "charger", "wall charger"),
    "cable": ("day sac", "dây sạc", "usb cable", "charging cable"),
    "socket": ("o cam", "ổ cắm", "power strip", "socket"),
    "battery": ("pin", "battery", "aa", "aaa", "9v"),
    "comb": ("luoc", "lược", "comb"),
    "pen": ("but", "bút", "pen"),
    "marker": ("but da", "bút dạ", "marker", "highlighter"),
    "spoon": ("muong", "muỗng", "spoon", "utensil"),
    "plastic_bag": ("bi ni long", "bì ni lông", "tui nylon", "plastic bag"),
    "eggshell": ("vo trung", "vỏ trứng", "eggshell"),
    "plastic_bottle": ("chai", "bottle", "pet"),
    "lighter": ("bat lua", "bật lửa", "lighter"),
}

QUEUE_SOURCES = {"auto_review_queue", "auto_low_conf"}

DISPLAY_LABELS = {
    "charger": "Cục sạc",
    "cable": "Dây sạc",
    "socket": "Ổ cắm điện",
    "battery": "Pin",
    "comb": "Cái lược",
    "pen": "Bút bi",
    "marker": "Bút dạ",
    "spoon": "Muỗng kim loại",
    "spoon_and_pen": "Muỗng kim loại + Bút bi",
    "plastic_bag": "Bì ni lông",
    "eggshell": "Vỏ trứng gà",
    "plastic_bottle": "Chai nhựa PET",
    "lighter": "Bật lửa",
    "unknown": "Chưa xác định",
}

CHAT_EVIDENCE_OBJECTS = {
    "codex-clipboard-4c3d15c6-34a2-4e63-8420-c4d529676320": "charger",
    "codex-clipboard-c21cfe9d-9939-4dff-a2d2-5bb53cddb27d": "charger",
    "codex-clipboard-6df4ba34-ea97-4ebc-ade3-77ec26891628": "charger",
    "codex-clipboard-1b9b54ca-7903-4aeb-ba8b-79c3052df3ee": "socket",
    "codex-clipboard-68ac2aff-d534-48cf-a9ac-c3e7a667645c": "battery",
    "codex-clipboard-3d386e02-4caf-4a63-9545-e09582ed662b": "battery",
    "codex-clipboard-bc487f7f-c4e5-4fc5-8809-9a4e32fd67fc": "comb",
    "codex-clipboard-e9fc88ef-a9f6-4037-aef5-041bedd100af": "marker",
    "codex-clipboard-54073921-8647-4dfb-8884-775509b236ab": "lighter",
    "codex-clipboard-40ad9ae7-a581-4222-beb9-749ad6f6fba7": "plastic_bag",
    "codex-clipboard-fb51083f-3b92-4a4e-ac2a-fc5b1f393055": "eggshell",
    "codex-clipboard-44fa62b8-fc46-4ecc-91cd-7ba56e524006": "eggshell",
    "codex-clipboard-3aeb631e-0474-44d4-8faa-6b35d2b30a4b": "eggshell",
    "codex-clipboard-7b1f2883-bdcc-4fbe-86ff-2879d4fb1a7a": "eggshell",
    "codex-clipboard-2ced75ba-bd19-45cc-b37e-e06273e699a2": "eggshell",
    "codex-clipboard-0af9740b-311f-412b-b22c-0512d282e4f5": "eggshell",
    "codex-clipboard-72a17fc2-a292-47df-854c-80519f091d44": "eggshell",
    "codex-clipboard-1c902bcf-856d-46ba-84d0-987cdbed4f60": "pen",
    "codex-clipboard-745eb2ff-b947-4c1f-9fab-c86d84c3534e": "pen",
    "codex-clipboard-d75f7112-2ce8-4f5e-9a9e-6ea8c052e50b": "spoon",
    "codex-clipboard-7c841f7c-5fcc-46cb-9373-5a60c5b57a66": "spoon",
    "codex-clipboard-09c54917-0ead-4e49-8f0a-9b2ff53797cf": "spoon",
    "codex-clipboard-32f86ecc-e262-4d29-9262-9aaffbdec2c0": "spoon",
    "codex-clipboard-09a6637e-37d2-41d7-a29a-05e6f154431d": "spoon",
    "codex-clipboard-e2cf73fb-ffb0-4f01-b12b-411cc50ba852": "spoon_and_pen",
    "codex-clipboard-de8d8ae2-4c47-46c6-921a-91a7006c5356": "spoon_and_pen",
    "codex-clipboard-ec2ffcd8-f97e-41c4-890a-166f79b656d8": "spoon_and_pen",
    "codex-clipboard-e9afb3c4-817a-4a7d-b066-69953185ac4f": "spoon_and_pen",
    "codex-clipboard-e7941c61-cdc0-42b8-976d-20fb1a6be969": "spoon_and_pen",
    "codex-clipboard-e6b02ca5-30dc-4787-b872-e60239806e31": "spoon_and_pen",
    "codex-clipboard-a59115f4-46b8-4429-8ed0-fbd904e795af": "spoon_and_pen",
    "codex-clipboard-e124dd8b-5aa9-4f0d-a2bb-2107c4d4895c": "plastic_bottle",
}


@dataclass(frozen=True)
class AuditItem:
    path: Path
    kind: str
    true_object: str
    model_label: str
    confidence: str
    problem: str
    action: str
    trainable: bool


def build_audit(
    *,
    clipboard_dir: Path,
    queue_dir: Path,
    captures_dir: Path,
    screenshot_limit: int = 120,
    queue_limit: int = 1000,
    capture_limit: int = 300,
) -> tuple[list[AuditItem], dict[str, Any]]:
    items: list[AuditItem] = []
    items.extend(_clipboard_items(clipboard_dir, screenshot_limit))
    queue_items, queue_stats = _queue_items(queue_dir, queue_limit)
    items.extend(queue_items)
    items.extend(_capture_items(captures_dir, capture_limit))
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "screenshots": sum(1 for item in items if item.kind == "screenshot_audit"),
        "screenshot_target_groups": dict(
            Counter(item.true_object for item in items if item.kind == "screenshot_audit")
        ),
        "queue_items_sampled": queue_stats["sampled"],
        "queue_reasons": dict(queue_stats["reasons"]),
        "queue_priorities": dict(queue_stats["priorities"]),
        "target_groups": dict(queue_stats["target_groups"]),
    }
    return items, summary


def write_report(path: Path, items: list[AuditItem], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recognition Audit Report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Clipboard screenshots audited: {summary['screenshots']} (audit only, not trainable).",
        f"- Screenshot evidence groups: {_format_counter(summary['screenshot_target_groups'], display=True)}.",
        f"- Queue metadata sampled: {summary['queue_items_sampled']}.",
        f"- Queue reasons: {_format_counter(summary['queue_reasons'])}.",
        f"- Review priorities: {_format_counter(summary['queue_priorities'])}.",
        f"- Target object groups: {_format_counter(summary['target_groups'], display=True)}.",
        "",
        "## Rules",
        "",
        "- Screenshots are evidence only because they include UI overlays.",
        "- Trainable data must come from camera crops/images reviewed by Admin.",
        "- Pin is hazardous: show warning and block auto-sort until Admin confirms.",
        "- Unknown or low-confidence inorganic items go to review queue, not straight to a bin.",
        "",
        "## Items",
        "",
        "| File | Kind | Object | Model label | Conf | Problem | Action | Trainable |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items[:500]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(item.path),
                    item.kind,
                    _display_label(item.true_object),
                    item.model_label,
                    item.confidence,
                    item.problem,
                    item.action,
                    "yes" if item.trainable else "no",
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clipboard_items(clipboard_dir: Path, limit: int) -> list[AuditItem]:
    paths = _recent_files(clipboard_dir, "codex-clipboard-*.png", limit)
    items: list[AuditItem] = []
    for path in paths:
        true_object = CHAT_EVIDENCE_OBJECTS.get(path.stem)
        if true_object is None:
            continue
        items.append(
            AuditItem(
                path=path,
                kind="screenshot_audit",
                true_object=true_object,
                model_label="screen_overlay",
                confidence="-",
                problem="Screenshot evidence only; not suitable for training.",
                action=_action_for(true_object, "hazardous" if true_object == "battery" else "high"),
                trainable=False,
            )
        )
    return items


def _queue_items(queue_dir: Path, limit: int) -> tuple[list[AuditItem], dict[str, Any]]:
    items: list[AuditItem] = []
    reasons: Counter[str] = Counter()
    priorities: Counter[str] = Counter()
    target_groups: Counter[str] = Counter()
    for meta_path in _recent_files(queue_dir, "*.json", limit):
        meta = _read_json(meta_path)
        if not meta:
            continue
        source = str(meta.get("source") or "")
        if source and source not in QUEUE_SOURCES:
            continue
        reason = str(meta.get("queue_reason") or meta.get("training_exclusion_reason") or "unknown")
        label, conf = _primary_label(meta)
        priority = str(meta.get("review_priority") or _infer_priority(reason, label))
        group = _target_group(" ".join([label, reason, str(meta.get("suggested_label") or "")]))
        reasons[reason] += 1
        priorities[priority] += 1
        target_groups[group] += 1
        problem = _problem_for(reason, label, priority)
        action = _action_for(group, priority)
        items.append(
            AuditItem(
                path=meta_path.with_suffix(".jpg"),
                kind="camera_queue",
                true_object=group,
                model_label=label,
                confidence=conf,
                problem=problem,
                action=action,
                trainable=False,
            )
        )
    return items, {
        "sampled": len(items),
        "reasons": reasons,
        "priorities": priorities,
        "target_groups": target_groups,
    }


def _capture_items(captures_dir: Path, limit: int) -> list[AuditItem]:
    return [
        AuditItem(
            path=path,
            kind="camera_capture",
            true_object=_target_group(path.stem),
            model_label="capture_history",
            confidence="-",
            problem="Historical camera capture; verify matching JSON before using.",
            action="Keep original file; only train if reviewed metadata has bbox_reviewed=true.",
            trainable=False,
        )
        for path in _recent_files(captures_dir, "*.jpg", limit)
    ]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _primary_label(meta: dict[str, Any]) -> tuple[str, str]:
    boxes = meta.get("boxes")
    if not isinstance(boxes, list) or not boxes:
        return str(meta.get("suggested_label") or "-"), "-"
    best = max(
        (box for box in boxes if isinstance(box, dict)),
        key=lambda box: float(box.get("conf") or 0.0),
        default={},
    )
    label = str(best.get("operator_label") or best.get("cls_name") or "-")
    conf = best.get("conf")
    return label, "-" if conf is None else f"{float(conf):.2f}"


def _target_group(text: str) -> str:
    clean = text.casefold()
    for group, needles in TARGET_LABELS.items():
        if any(needle.casefold() in clean for needle in needles):
            return group
    if "unknown" in clean:
        return "unknown"
    return "other"


def _problem_for(reason: str, label: str, priority: str) -> str:
    clean = " ".join([reason, label, priority]).casefold()
    if "battery" in clean or "pin" in clean or priority == "hazardous":
        return "Hazardous battery needs warning and Admin confirmation."
    if "multiple" in clean or "foreground" in clean:
        return "Multiple/overlap case; block auto-sort and review boxes."
    if "unknown" in clean:
        return "Unknown object; do not route automatically."
    if "low_confidence" in clean:
        return "Low confidence; needs manual label before training."
    return "Needs manual review."


def _infer_priority(reason: str, label: str) -> str:
    clean = " ".join([reason, label]).casefold()
    if "battery" in clean or "pin" in clean or "hazard" in clean:
        return "hazardous"
    if "unknown" in clean or "multiple" in clean or "foreground" in clean:
        return "high"
    if "low_confidence" in clean or "low confidence" in clean:
        return "medium"
    return "normal"


def _action_for(group: str, priority: str) -> str:
    if priority == "hazardous" or group == "battery":
        return "Pin: mark hazardous, no auto-sort; Admin may confirm R/bin 2."
    if group in {"charger", "cable", "socket"}:
        return "Label as electronics/inorganic after reviewing camera crop."
    if group in {"comb", "marker", "lighter"}:
        return "Label as inorganic specialist sample after Admin bbox review."
    if group == "unknown":
        return "Pick exact Vietnamese label in training queue."
    return "Review crop and bbox; keep training_excluded until approved."


def _recent_files(base: Path, pattern: str, limit: int) -> list[Path]:
    if not base.exists():
        return []
    files = [path for path in base.glob(pattern) if path.is_file()]
    files.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
    return files[: max(0, limit)]


def _display_label(group: str) -> str:
    return DISPLAY_LABELS.get(group, group)


def _format_counter(counter: dict[str, int], *, display: bool = False) -> str:
    if not counter:
        return "none"
    return ", ".join(
        f"{_display_label(key) if display else key}={value}"
        for key, value in sorted(counter.items())
    )


def _md(path: Path) -> str:
    return str(path).replace("|", "\\|")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clipboard-dir", type=Path, default=Path.home() / "AppData/Local/Temp")
    parser.add_argument("--queue-dir", type=Path, default=Path("dataset_v2/low_conf_queue"))
    parser.add_argument("--captures-dir", type=Path, default=Path("detection_captures"))
    parser.add_argument("--out", type=Path, default=Path("docs/recognition-audit-report.md"))
    parser.add_argument("--screenshot-limit", type=int, default=120)
    parser.add_argument("--queue-limit", type=int, default=1000)
    parser.add_argument("--capture-limit", type=int, default=300)
    args = parser.parse_args()
    items, summary = build_audit(
        clipboard_dir=args.clipboard_dir,
        queue_dir=args.queue_dir,
        captures_dir=args.captures_dir,
        screenshot_limit=args.screenshot_limit,
        queue_limit=args.queue_limit,
        capture_limit=args.capture_limit,
    )
    write_report(args.out, items, summary)
    print(f"wrote {args.out} with {len(items)} audit rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
