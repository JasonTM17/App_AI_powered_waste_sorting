"""Train/evaluate the Phase 21 Kaggle O/R/I classifier candidate."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.three_bin_classifier import THREE_BIN_COMMANDS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("dataset_v2") / "kaggle_three_bin_classifier_v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-train-images", type=int, default=0, help="0 means all train rows.")
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import transforms
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    train_rows = _load_rows(args.dataset / "train.jsonl")
    valid_rows = _load_rows(args.dataset / "valid.jsonl")
    test_rows = _load_rows(args.dataset / "test.jsonl")
    if args.max_train_images > 0:
        train_rows = _balanced_limit(train_rows, args.max_train_images)
    if not train_rows or not valid_rows:
        raise SystemExit("classifier dataset requires train and valid rows")

    run_name = args.name or f"three-bin-kaggle-{datetime.now():%Y%m%d-%H%M%S}"
    run_dir = Path("runs") / "train" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    device = _device(args.device, torch)

    train_tf = transforms.Compose(
        [
            transforms.Resize((args.imgsz, args.imgsz)),
            transforms.RandomApply([transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.2))], p=0.25),
            transforms.ColorJitter(brightness=0.18, contrast=0.22, saturation=0.12),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )
    eval_tf = transforms.Compose(
        [
            transforms.Resize((args.imgsz, args.imgsz)),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )
    blur_tf = transforms.Compose(
        [
            transforms.Resize((args.imgsz, args.imgsz)),
            transforms.GaussianBlur(kernel_size=5, sigma=(0.6, 1.4)),
            transforms.ColorJitter(contrast=0.7),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )

    train_ds = _ManifestDataset(train_rows, train_tf)
    valid_ds = _ManifestDataset(valid_rows, eval_tf)
    test_ds = _ManifestDataset(test_rows or valid_rows, eval_tf)
    blur_ds = _ManifestDataset(test_rows or valid_rows, blur_tf)
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=args.workers)
    valid_loader = DataLoader(valid_ds, batch_size=args.batch, shuffle=False, num_workers=args.workers)
    test_loader = DataLoader(test_ds, batch_size=args.batch, shuffle=False, num_workers=args.workers)
    blur_loader = DataLoader(blur_ds, batch_size=args.batch, shuffle=False, num_workers=args.workers)

    try:
        weights = MobileNet_V3_Small_Weights.DEFAULT
        model = mobilenet_v3_small(weights=weights)
        pretrained = True
    except Exception as exc:
        print(json.dumps({"warning": f"pretrained weights unavailable, using random init: {exc}"}))
        model = mobilenet_v3_small(weights=None)
        pretrained = False
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, len(THREE_BIN_COMMANDS))
    model.to(device)

    class_weights = _class_weights(train_rows, torch).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    best_state = None
    best_macro_f1 = -1.0
    rows_for_csv: list[dict[str, object]] = []
    for epoch in range(1, args.epochs + 1):
        loss = _train_epoch(model, train_loader, criterion, optimizer, device)
        valid_metrics = _evaluate(model, valid_loader, device)
        macro_f1 = float(valid_metrics["macro_f1"])
        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
        row = {"epoch": epoch, "train_loss": loss, **{f"valid_{k}": v for k, v in valid_metrics.items() if isinstance(v, float)}}
        rows_for_csv.append(row)
        print(json.dumps(row, ensure_ascii=False))

    if best_state is not None:
        model.load_state_dict(best_state)
    test_metrics = _evaluate(model, test_loader, device)
    blur_metrics = _evaluate(model, blur_loader, device)
    artifact_path = run_dir / "three_bin_classifier.pt"
    torch.save(
        {
            "model_type": "torchvision_mobilenet_v3_small",
            "classes": THREE_BIN_COMMANDS,
            "input_size": args.imgsz,
            "model_state": {key: value.detach().cpu() for key, value in model.state_dict().items()},
            "test_metrics": test_metrics,
            "blur_metrics": blur_metrics,
        },
        artifact_path,
    )
    _write_csv(run_dir / "results.csv", rows_for_csv)
    _write_confusion_png(run_dir / "confusion_matrix.png", test_metrics["confusion_matrix"])
    report = {
        "model_path": str(artifact_path),
        "dataset": str(args.dataset),
        "epochs": args.epochs,
        "batch": args.batch,
        "input_size": args.imgsz,
        "device": str(device),
        "pretrained": pretrained,
        "train_images": len(train_rows),
        "valid_images": len(valid_rows),
        "test_images": len(test_rows or valid_rows),
        "test_metrics": test_metrics,
        "blur_metrics": blur_metrics,
        "promote": False,
        "gate": {
            "macro_f1_pass": float(test_metrics["macro_f1"]) >= 0.90,
            "per_bin_recall_pass": all(
                float(test_metrics["per_class"][cmd]["recall"]) >= 0.85 for cmd in THREE_BIN_COMMANDS
            ),
            "blur_drop_pass": float(test_metrics["macro_f1"]) - float(blur_metrics["macro_f1"]) <= 0.05,
        },
    }
    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "model": str(artifact_path), "test_macro_f1": test_metrics["macro_f1"]}, indent=2))
    return 0


class _ManifestDataset:
    def __init__(self, rows: list[dict[str, object]], transform: Any) -> None:
        self.rows = rows
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        with Image.open(str(row["image_path"])) as image:
            rgb = image.convert("RGB")
        label = THREE_BIN_COMMANDS.index(str(row["bin_code"]))
        return self.transform(rgb), label


def _load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict) and row.get("bin_code") in THREE_BIN_COMMANDS:
                rows.append(row)
    return rows


def _balanced_limit(rows: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    rng = random.Random(21)
    by_bin: dict[str, list[dict[str, object]]] = {cmd: [] for cmd in THREE_BIN_COMMANDS}
    for row in rows:
        by_bin[str(row["bin_code"])].append(row)
    for values in by_bin.values():
        rng.shuffle(values)
    out: list[dict[str, object]] = []
    while len(out) < limit and any(by_bin.values()):
        for command in THREE_BIN_COMMANDS:
            if by_bin[command] and len(out) < limit:
                out.append(by_bin[command].pop())
    rng.shuffle(out)
    return out


def _class_weights(rows: list[dict[str, object]], torch: Any):
    counts = Counter(str(row["bin_code"]) for row in rows)
    weights = []
    for command in THREE_BIN_COMMANDS:
        weights.append(1.0 / max(1, counts[command]))
    tensor = torch.tensor(weights, dtype=torch.float32)
    return tensor / tensor.mean()


def _train_epoch(model: Any, loader: Any, criterion: Any, optimizer: Any, device: Any) -> float:
    model.train()
    total_loss = 0.0
    total = 0
    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(images), labels)
        loss.backward()
        optimizer.step()
        batch = int(labels.numel())
        total_loss += float(loss.detach().cpu()) * batch
        total += batch
    return total_loss / max(1, total)


def _evaluate(model: Any, loader: Any, device: Any) -> dict[str, Any]:
    import torch

    model.eval()
    confusion = [[0 for _ in THREE_BIN_COMMANDS] for _ in THREE_BIN_COMMANDS]
    with torch.inference_mode():
        for images, labels in loader:
            logits = model(images.to(device))
            preds = torch.argmax(logits, dim=1).cpu().tolist()
            for truth, pred in zip(labels.tolist(), preds, strict=False):
                confusion[int(truth)][int(pred)] += 1
    per_class: dict[str, dict[str, float]] = {}
    f1_values = []
    recalls = []
    for idx, command in enumerate(THREE_BIN_COMMANDS):
        tp = confusion[idx][idx]
        fp = sum(confusion[row][idx] for row in range(len(THREE_BIN_COMMANDS)) if row != idx)
        fn = sum(confusion[idx][col] for col in range(len(THREE_BIN_COMMANDS)) if col != idx)
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-9, precision + recall)
        per_class[command] = {"precision": precision, "recall": recall, "f1": f1}
        f1_values.append(f1)
        recalls.append(recall)
    total = sum(sum(row) for row in confusion)
    correct = sum(confusion[i][i] for i in range(len(THREE_BIN_COMMANDS)))
    return {
        "accuracy": correct / max(1, total),
        "macro_f1": sum(f1_values) / len(f1_values),
        "macro_recall": sum(recalls) / len(recalls),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    keys = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _write_confusion_png(path: Path, matrix: list[list[int]]) -> None:
    cell = 96
    size = cell * (len(THREE_BIN_COMMANDS) + 1)
    image = Image.new("RGB", (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    max_value = max((value for row in matrix for value in row), default=1)
    for idx, command in enumerate(THREE_BIN_COMMANDS):
        draw.text(((idx + 1) * cell + 32, 20), command, fill=(0, 0, 0))
        draw.text((20, (idx + 1) * cell + 36), command, fill=(0, 0, 0))
    for row, values in enumerate(matrix):
        for col, value in enumerate(values):
            intensity = int(255 - 190 * (value / max(1, max_value)))
            x1 = (col + 1) * cell
            y1 = (row + 1) * cell
            draw.rectangle((x1, y1, x1 + cell, y1 + cell), fill=(intensity, intensity, 255), outline=(40, 40, 80))
            draw.text((x1 + 28, y1 + 36), str(value), fill=(0, 0, 0))
    image.save(path)


def _device(requested: str, torch: Any):
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(requested)


if __name__ == "__main__":
    raise SystemExit(main())
