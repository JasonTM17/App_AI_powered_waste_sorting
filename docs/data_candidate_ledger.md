# Data Candidate Ledger

Mục tiêu: chỉ import data Roboflow Universe đã lọc kỹ, ưu tiên Object Detection/YOLO, license rõ ràng, nhãn map được về 42 class hiện tại.

## Dataset Hiện Tại

- Source chính: `projectverba/yolo-waste-detection`
- Queue: `dataset_v2/low_conf_queue`
- Catalog: `dataset.db`
- Dataset catalog hiện tại: `14,974` ảnh, `21,204` box, `42` nhãn
- Trusted trainset gốc: `13,104` ảnh, `18,920` box, `42` nhãn
- Data cần duyệt: `776` item
- Manual import: `50` ảnh

## Class Đang Thiếu Data Nhất

Ưu tiên bổ sung trước các class dưới `50` box:

| Class | Box hiện có | Nên bổ sung |
| --- | ---: | ---: |
| Aluminum caps | 1 | 300-800 |
| Metal shavings | 1 | 300-800 |
| Iron utensils | 2 | 300-800 |
| Wood | 2 | 300-800 |
| Cellulose | 3 | 300-800 |
| Furniture | 3 | 300-800 |
| Combined plastic | 4 | 300-800 |
| Foil | 4 | 300-800 |
| Ceramic | 6 | 300-800 |
| Plastic caps | 9 | 300-800 |
| Scrap metal | 12 | 300-800 |
| Electronics | 13 | 300-800 |
| Paper shavings | 15 | 300-800 |
| Disposable tableware | 16 | 300-800 |
| Plastic shavings | 20 | 300-800 |
| Papier mache | 22 | 300-800 |
| Postal packaging | 29 | 300-800 |
| Unknown plastic | 35 | 300-800 |
| Paper cups | 30 | 300-800 |
| Milk bottle | 41 | 300-800 |
| Tetra pack | 43 | 300-800 |
| Aerosols | 46 | 300-800 |
| Plastic canister | 48 | 300-800 |
| Plastic can | 49 | 300-800 |

## Nguồn Roboflow Nên Lấy Thêm

| Ưu tiên | Nguồn | Link | Lý do | Cách dùng |
| --- | --- | --- | --- | --- |
| Cao | TACO / TACO-style | https://universe.roboflow.com/waste-object-detection | Workspace có `TACO7`, `TACO`, `Waste detection`, tổng khoảng `6.04k` ảnh; gần với bottle, can, carton, foil, disposable container. | Import batch nhỏ, map nhãn TACO về 42 class, quarantine nhãn lạ. |
| Cao | Waste Detection 2.0 | https://universe.roboflow.com/dun-yan-oflbi/waste-detection-2.0-hwohv-yuzwo | Có `1.3k` ảnh, 19 class gồm E-Waste, Electric Cable, Organic Waste, Wooden Waste, Plastic bag, Carton, Glass Bottle. | Rất hợp để bù `Electronics`, `Wood`, `Plastic bag`, `Glass bottle`, `Carton/Cardboard`. |
| Cao | Food Waste Detection | https://universe.roboflow.com/food-waste-detection | Object Detection, khoảng `6.74k` ảnh; dùng để tăng Organic và đồ ăn thừa nếu máy phân loại có nhánh hữu cơ. | Chỉ import class map được về `Organic`, `Disposable tableware`, `Paper cups`, còn lại quarantine. |
| Cao | TACO search results | https://universe.roboflow.com/search?q=class%3Afood-waste+object+detection | Search có nhiều bản TACO/TACO-like như `Taco 2.0` khoảng `2,998` ảnh, `TACO_data` khoảng `1,499` ảnh, `Waste Recognition with TACO` khoảng `3,010` ảnh. | Chọn dataset có preview tốt, license rõ, tải YOLOv8. |
| Vừa | TACO_TrashNet | https://universe.roboflow.com/search?q=class%3Aorganic-waste+object+detection | Search thấy `TACO_TrashNet` khoảng `5.69k` ảnh, nhãn gần: cardboard, glass, metal, paper, plastic, plastic bottle/cup/bag, foil, organic waste. | Dùng để tăng data tổng quát, nhưng phải kiểm nhãn và góc chụp. |
| Cẩn thận | Dataset rất lớn / nhiều class | https://universe.roboflow.com/search?q=waste | Có nhiều dataset lớn nhưng nhãn loạn, domain xa băng chuyền. | Không import một lần. Chỉ import 500-2000 ảnh/batch sau khi audit. |

## Luật Import

- Download format: ưu tiên `YOLOv8`, chấp nhận `YOLO v5 PyTorch`.
- Chỉ import Object Detection có `images/`, `labels/`, `data.yaml`.
- Mỗi nguồn phải có `source_name` riêng, ví dụ `taco_candidate`, `waste_detection_2_candidate`.
- Nhãn map được về 42 class thì giữ trusted sau khi duyệt.
- Nhãn lạ đi vào quarantine/untrusted, không được lọt vào trainset sạch.
- Không thay `models/best.pt` bằng candidate nếu chưa evaluate và test camera thật.

## Flow Local

```powershell
python -m uv run python scripts/audit_dataset.py
python -m uv run python scripts/import_roboflow_dataset.py --zip path\to\dataset.zip --source-name taco_candidate
python -m uv run python scripts/audit_dataset.py --rare-threshold 100
python -m uv run python scripts/export_yolo_trainset.py
python -m uv run python scripts/train_yolo.py --device 0 --epochs 100 --imgsz 640 --batch 16 --workers 0 --name trash-sorter-v3 --exist-ok
python -m uv run python scripts/evaluate_yolo.py --model runs\train\trash-sorter-v3\weights\best.pt --split test
```

Sau khi candidate pass metrics và test USB camera, mới promote candidate weight sang `models/best.pt`.
