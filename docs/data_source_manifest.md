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
