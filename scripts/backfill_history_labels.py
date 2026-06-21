"""Back up and backfill auditable Vietnamese labels in history.db."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.core.history import HistoryService
from app.utils.paths import db_path

# These no-evidence decisions were made by direct inspection of preserved captures.
# No ambiguous object is promoted to a concrete human-verified label automatically.
REVIEWED_UNKNOWN_ROWS: dict[int, tuple[str, str, str]] = {
    722: ("20260605-121923-049475-t40-41c2aa.jpg", "no_evidence", ""),
    719: ("20260605-121912-595181-t37-475dbc.jpg", "no_evidence", ""),
    715: ("20260605-121904-896620-t33-a798b8.jpg", "no_evidence", ""),
    714: ("20260605-121902-243726-t32-fdef40.jpg", "no_evidence", ""),
    713: ("20260605-121900-668212-t31-bc4239.jpg", "no_evidence", ""),
    704: ("20260605-121753-349372-t22-db5d8f.jpg", "no_evidence", ""),
    703: ("20260605-121752-922542-t21-2446c2.jpg", "no_evidence", ""),
    700: ("20260605-121748-691786-t18-6df882.jpg", "no_evidence", ""),
    699: ("20260605-121747-735206-t17-1c95cd.jpg", "no_evidence", ""),
    693: ("20260605-121737-344216-t11-03547b.jpg", "no_evidence", ""),
    691: ("20260605-121735-546743-t9-37258e.jpg", "no_evidence", ""),
    686: ("20260605-121730-124016-t4-0db392.jpg", "no_evidence", ""),
    685: ("20260605-121729-809482-t3-2d01ef.jpg", "no_evidence", ""),
    683: ("20260605-121726-881776-t1-e1fa61.jpg", "no_evidence", ""),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=db_path())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = args.db.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"History database not found: {source}")
    output_dir = (args.output_dir or source.parent / "history-label-reports").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    if args.apply:
        backup = output_dir / f"history-before-labels-{stamp}.db"
        _sqlite_backup(source, backup)
        target = source
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="trash-sorter-label-dry-run-"))
        target = temp_dir / "history.db"
        _sqlite_backup(source, target)
        backup = None

    service = HistoryService(target)
    try:
        before = _raw_snapshots(target)
        service.backfill_labels()
        _apply_reviewed_unknown_rows(service)
        _mark_disputed_image_labels_for_review(service)
        after = _raw_snapshots(target)
    finally:
        service.close()

    report_rows = []
    for row_id in sorted(after):
        old = before[row_id]
        new = after[row_id]
        report_rows.append(
            {
                "id": row_id,
                "cls_name": new["cls_name"],
                "old_display_label": old["display_label"],
                "new_display_label": new["display_label"],
                "old_label_status": old["label_status"],
                "new_label_status": new["label_status"],
                "label_source": new["label_source"],
                "old_route_label": old["route_label"],
                "new_route_label": new["route_label"],
                "old_bin_index": old["bin_index"],
                "new_bin_index": new["bin_index"],
                "old_uart_command": old["uart_command"],
                "new_uart_command": new["uart_command"],
                "changed": old != new,
            }
        )

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "database": str(source),
        "backup": str(backup) if backup else None,
        "total": len(report_rows),
        "changed": sum(bool(row["changed"]) for row in report_rows),
        "statuses": dict(Counter(str(row["new_label_status"]) for row in report_rows)),
        "empty_display_labels": sum(not str(row["new_display_label"]).strip() for row in report_rows),
        "raw_class_changes": sum(
            before[row_id]["cls_name"] != after[row_id]["cls_name"] for row_id in after
        ),
    }
    json_path = output_dir / f"history-label-backfill-{stamp}.json"
    csv_path = output_dir / f"history-label-backfill-{stamp}.csv"
    json_path.write_text(
        json.dumps({"summary": summary, "rows": report_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report_rows[0]) if report_rows else [])
        if report_rows:
            writer.writeheader()
            writer.writerows(report_rows)
    print(json.dumps({**summary, "json_report": str(json_path), "csv_report": str(csv_path)}, ensure_ascii=False))
    return 0


def _apply_reviewed_unknown_rows(service: HistoryService) -> None:
    for row_id, (expected_name, status, label) in REVIEWED_UNKNOWN_ROWS.items():
        row = service.get(row_id)
        if row is None or str(row.cls_name) != "Unknown object":
            continue
        actual_name = Path(str(getattr(row, "image_path", "") or "")).name
        if actual_name != expected_name:
            continue
        target_label = label if status == "human_verified" else "Chưa xác định vật"
        if row.label_status == status and row.display_label == target_label:
            continue
        note = (
            "Ảnh lịch sử cho thấy rõ một cây bút bi."
            if status == "human_verified"
            else "Ảnh trống, mờ hoặc bị che; không đủ bằng chứng để xác định vật."
        )
        service.review_label(
            row_id,
            display_label=label,
            reviewed_by="history-audit-2026-06-21",
            review_note=note,
            status=status,
        )


def _mark_disputed_image_labels_for_review(service: HistoryService) -> None:
    """Do not present model-only labels as facts after the user disputed the batch."""
    for row in service.query(limit=1_000_000):
        if row.label_status != "model_inferred":
            continue
        image_path = Path(str(getattr(row, "image_path", "") or ""))
        annotated_path = Path(str(getattr(row, "annotated_path", "") or ""))
        if not image_path.is_file() and not annotated_path.is_file():
            continue
        service.review_label(
            int(row.id),
            display_label="",
            reviewed_by="user-report-2026-06-21",
            review_note=(
                "Người dùng báo cáo lô ảnh cũ bị nhận diện sai; cần Admin xem ảnh và xác nhận "
                "tên vật, không sử dụng nhãn model như kết luận."
            ),
            status="needs_review",
        )


def _snapshot(row) -> dict[str, object]:
    return {
        "cls_name": str(getattr(row, "cls_name", "") or ""),
        "display_label": str(getattr(row, "display_label", "") or ""),
        "label_status": str(getattr(row, "label_status", "") or ""),
        "label_source": str(getattr(row, "label_source", "") or ""),
        "route_label": str(getattr(row, "route_label", "") or ""),
        "bin_index": getattr(row, "bin_index", None),
        "uart_command": str(getattr(row, "uart_command", "") or ""),
    }


def _raw_snapshots(database: Path) -> dict[int, dict[str, object]]:
    snapshots: dict[int, dict[str, object]] = {}
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            "select id, cls_name, display_label, label_status, label_source, "
            "route_label, bin_index, uart_command from detections order by id"
        ):
            snapshots[int(row["id"])] = {
                "cls_name": str(row["cls_name"] or ""),
                "display_label": str(row["display_label"] or ""),
                "label_status": str(row["label_status"] or ""),
                "label_source": str(row["label_source"] or ""),
                "route_label": str(row["route_label"] or ""),
                "bin_index": row["bin_index"],
                "uart_command": str(row["uart_command"] or ""),
            }
    return snapshots


def _sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)


if __name__ == "__main__":
    raise SystemExit(main())
