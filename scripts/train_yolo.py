"""Fine-tune Trash Sorter YOLO locally without replacing production weights."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("dataset_v2") / "yolo_trainset" / "data.yaml")
    parser.add_argument("--model", type=Path, default=Path("models") / "best.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=-1, help="-1 lets Ultralytics choose an automatic batch size")
    parser.add_argument("--device", default="0")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--project", type=Path, default=Path("runs") / "train")
    parser.add_argument("--name", default="trash-sorter-v3")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0, help="0 is safest on Windows")
    parser.add_argument("--fraction", type=float, default=1.0, help="Use a subset for smoke tests")
    parser.add_argument("--cache", action="store_true", help="Legacy alias for RAM cache")
    parser.add_argument(
        "--cache-mode",
        choices=("none", "ram", "disk"),
        default="none",
        help="Disk cache is recommended for the 6GB GPU laptop",
    )
    parser.add_argument("--freeze", type=int, default=0, help="Freeze the first N model layers")
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--rect", action="store_true")
    parser.add_argument("--plots", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--exist-ok", action="store_true", help="Allow reusing an existing run name")
    parser.add_argument("--lr0", type=float, default=0.0015, help="Initial learning rate for fine-tuning")
    parser.add_argument("--lrf", type=float, default=0.01, help="Final LR fraction")
    parser.add_argument("--warmup-epochs", type=float, default=2.0)
    parser.add_argument("--close-mosaic", type=int, default=20)
    parser.add_argument("--cos-lr", action="store_true", help="Use cosine LR schedule")
    parser.add_argument("--optimizer", default="SGD", help="Use a fixed optimizer so lr0 is respected")
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"data.yaml not found: {args.data}")
    if not args.model.exists():
        raise SystemExit(f"model not found: {args.model}")
    if not 0 < args.fraction <= 1:
        raise SystemExit("--fraction must be greater than 0 and at most 1")

    data_path = args.data.resolve()
    model_path = args.model.resolve()
    project_path = (ROOT / args.project).resolve() if not args.project.is_absolute() else args.project

    from ultralytics import YOLO

    model = YOLO(str(model_path))
    train_args = dict(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=args.patience,
        project=str(project_path),
        name=args.name,
        seed=args.seed,
        workers=args.workers,
        fraction=args.fraction,
        cache=bool(args.cache) if args.cache_mode == "none" else args.cache_mode,
        exist_ok=args.exist_ok,
        lr0=args.lr0,
        lrf=args.lrf,
        warmup_epochs=args.warmup_epochs,
        close_mosaic=args.close_mosaic,
        cos_lr=args.cos_lr,
        optimizer=args.optimizer,
        amp=args.amp,
        rect=args.rect,
        plots=args.plots,
    )
    if args.freeze > 0:
        train_args["freeze"] = args.freeze
    results = model.train(**train_args)
    save_dir = getattr(results, "save_dir", None)
    print(f"Training complete. Candidate run: {save_dir or args.project / args.name}")
    print("Review metrics and camera smoke test before replacing models/best.pt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
