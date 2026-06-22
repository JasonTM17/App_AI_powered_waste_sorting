# Project Changelog

## 2026-06-22

### Improved

- Added an evidence-based `Plastic bag` confidence threshold for blurry USB-camera input while leaving thresholds for other classes unchanged.
- Preserved the specialist model when loading a newly trained candidate for live testing.
- Added four product demonstration videos and a hardware prototype poster to the repository showcase.

### Verified

- Desktop recognition/configuration regression suite passed.
- Web unit tests and production build passed.

## 2026-06-21

### Fixed

- Opened the desktop camera automatically on startup and cropped the Live view to the configured white-tray ROI while preserving detection-box alignment.
- Rejected low-confidence fallback boxes that cover most of the tray, preventing the empty white ROI from appearing as one giant unknown object.
- Fixed local web startup so the hardware bridge secret from env files no longer blocks direct localhost agent calls, and backfilled legacy local history/station ownership to the `nguyen-son` user.
- Added a payload-free Supabase Realtime pulse channel so Admin/User dashboards refresh scoped cloud data immediately while retaining authenticated API reads and polling fallback.
- Rearmed automatic sorting after one visually verified empty-tray frame, even when the next object arrives while the mechanism is still returning.
- Prevented dark tray rails and full-frame YOLO false positives from hiding a real empty-tray transition.
- Added regression coverage for verified-empty detection, early next-object timing, and second dispatch.
- Relaxed automatic dispatch globally to accept confidence from 0.45 and objects filling the camera frame, including legacy user configurations.
- Removed confidence-based dispatch blocking for recognized mapped classes and lowered Pen recognition thresholds, so a recognized item always produces a sort command.
- Relaxed live dispatch for blurry cameras: one ROI foreground object with multiple labels is collapsed to the best sortable label, and dispatch re-arms immediately after ACK for faster consecutive sorting.
- Decoupled Live camera preview FPS from YOLO inference latency and enabled GPU half precision by default, keeping the 720p tray view fluid while inference continues in the background.
