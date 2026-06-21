# Audit nhận diện ảnh lịch sử

Ngày chạy: 2026-06-21

## Kết quả

- Lịch sử có 774 dòng, nhưng chỉ 156 dòng còn ảnh camera gốc.
- Không có ảnh nào mang nhãn `human_verified`; nhãn lịch sử chỉ là dự đoán model cũ.
- Model hiện tại trùng chính xác nhãn cũ ở 74/156 ảnh.
- Model hiện tại cùng tuyến thùng với nhãn cũ ở 100/156 ảnh.
- Có 115/156 ảnh cần Admin xem lại và 7 ảnh không có detection.
- Đã đưa 156 ảnh vào queue phục hồi, mặc định `training_excluded=true`.

## Kiểm tra trực quan

- ID 667, 677, 726: Bút bi. Nhãn lịch sử của ID 677 là `Aluminum can`, sai.
- ID 764: Muỗng kim loại. Model hiện tại đoán `Glass bottle`, sai.
- ID 632, 694: vật bị che hoặc không có vật đủ rõ, không được train.
- ID 750, 753: màn hình OBS mất camera, không được train.
- Nhiều ảnh ID 619-653 chủ yếu chứa bàn tay hoặc cảnh nền, không phải mẫu rác sạch.
- Các cụm bút, muỗng, chai, lá và giấy vẫn có ảnh hữu ích, nhưng phải duyệt bbox từng ảnh.

## Quy tắc an toàn

- Không lấy nhãn lịch sử cũ làm ground truth.
- Không tự train từ ảnh phục hồi.
- Chỉ ảnh được Admin xác nhận tên vật và bbox mới được bật `recognition_enabled`.
- Ảnh trắng, OBS, bàn tay che vật hoặc không đủ bằng chứng phải quarantine/no-evidence.
- Pin phải được gắn `hazardous`; không tự phân loại hoặc gửi UART.

## Tệp kết quả

- Báo cáo máy: `runs/eval/history-capture-model-audit.json`
- Contact sheets: `runs/eval/history-contact-sheets/page-1.jpg` đến `page-4.jpg`
- Queue phục hồi: `dataset_v2/low_conf_queue/history_recovery_*.jpg|json`
