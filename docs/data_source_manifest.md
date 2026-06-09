# Data Source Manifest

This repository publishes source code and provenance records only. Dataset
images, local camera captures, generated images, SQLite catalogs, run folders,
and model weights are excluded by `.gitignore`.

## Imported Sources

| Source id | Purpose | Upstream | License metadata | Local policy |
| --- | --- | --- | --- | --- |
| `roboflow_pen_v3` | Pen detection | User-downloaded `PEN.v3i.yolov8.zip` | Preserve Roboflow export metadata | Reviewed train/val/test only |
| `roboflow_version2` | Battery and toothbrush | User-downloaded `Version2.v1i.yolov8.zip` | Preserve Roboflow export metadata | Reviewed train/val/test only |
| `roboflow_cardboard_paper` | Cardboard and paper | User-downloaded `cardboard-paper.v1i.yolov8.zip` | Preserve Roboflow export metadata | Reviewed train/val/test only |
| `manual_camera_capture` | Real tray-camera domain | Local USB camera | Private local capture | Never pushed |
| `manual_web_import` | Licensed supplemental images | Explicit image and source-page URL | Author and license are required in item metadata | Review before training |
| `generated_*` | Rare-view augmentation | Image generation tool and prompt record | Generated-content record | Train only, maximum 20% per class |

## Preferred Public Sources

- Open Images: https://storage.googleapis.com/openimages/web/index.html
- Wikimedia Commons: https://commons.wikimedia.org/
- Roboflow Universe projects with an explicit license and downloadable object-detection annotations.

Google Images may be used for discovery only. An image is imported only when
its direct URL, source page, author, and usage license are recorded.

## Phase 8 Licensed Manifest Format

Bulk imports use `scripts/import_licensed_image_manifest.py` with a JSON list
or `{ "items": [...] }`. Each item must include:

```json
{
  "image_url": "https://example.org/direct-image.jpg",
  "source_page_url": "https://example.org/page-with-license",
  "license": "CC-BY-4.0",
  "author": "Example Author",
  "source_type": "wikimedia",
  "canonical_class": "Pen",
  "generated": false
}
```

Allowed `source_type` values are `licensed_url`, `open_images`, `wikimedia`,
`roboflow`, `generated`, and `other`. Generated images are forced to train-only,
disabled for immediate reference recognition, and capped at 20% per class.

Phase 8 priority classes:

- P0: `Pen`, `Battery`, `Toothbrush`, `Textile`, `Disposable tableware`,
  `Unknown plastic`, `Tetra pack`, `Ceramic`, `Aerosols`, `Electronics`.
- P1: `Organic`, `Aluminum can`, `Plastic bottle`, `Cardboard`, `Paper`,
  `Plastic bag`, `Plastic cup`, `Tin`, `Glass bottle`.
- P2: `Plastic caps`, `Stretch film`, `Paper cups`, `Aluminum caps`, `Foil`,
  `Postal packaging`, `Scrap metal`.

## Phase 9 Web + Camera Blur Workflow

Use Google only to find source pages, then use source metadata from Wikimedia,
Open Images, or another explicitly licensed page. Build a manifest first:

```powershell
python -m uv run python scripts/build_p0_licensed_manifest.py --per-class 40
python -m uv run python scripts/import_licensed_image_manifest.py dataset_v2/phase9_p0_licensed_manifest.json --delay-seconds 1.25
```

After bbox review, add camera-blur train-only variants for the weak classes:

```powershell
python -m uv run python scripts/augment_camera_blur_pack.py --variants 2 --max-per-class 48
python -m uv run python scripts/audit_phase9_readiness.py
```

Camera-blur metadata fields:

- `camera_blur_augmented: true`
- `augmentation_parent`: original reviewed image path.
- `augmentation_profile`: augmentation recipe name.
- `split: train`, `split_lock: true`, `recognition_enabled: false`.

Camera-blur augmented images are never valid/test/reference samples.

## Fixed Training Taxonomy

Fast Pen fine-tuning uses the existing 45-class V6 contract. Vietnamese object
names are aliases to those classes, for example:

- `cây bút`, `bút bi` -> `Pen`
- `vỏ chuối`, `thức ăn thừa` -> `Organic`
- `lon bia`, `lon nước ngọt` -> `Aluminum can`
- `chai nhựa PET` -> `Plastic bottle`
- `hộp carton` -> `Cardboard`
- `khẩu trang` -> `Textile`
- `hộp xốp` -> `Disposable tableware`
- `ly trà sữa` -> `Plastic cup`

## Candidate Promotion

The current V6 epoch-8 candidate is not production-approved. A candidate may
replace production weights only after:

- Pen precision and recall are each at least 0.85 on real holdout captures.
- Overall mAP50 and mAP50-95 regress by no more than 0.02 from V5.
- Ten unseen camera poses pass at least 9/10.
- One guarded `R/voco/bin2` hardware test returns `ACK:R` without repeating.
