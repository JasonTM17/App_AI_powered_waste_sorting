# GD5800 Voice Pack

This folder bundles the laptop-speaker MP3 files used when the Settings page is
switched to `Loa máy tính`. The desktop and local agent choose one pack through
`speaker.voice_gender`.

## File map

- `Giọng nữ/Phân loại hữu cơ.mp3` -> `O`
- `Giọng nữ/Phân loại Vô cơ.mp3` -> `R`
- `Giọng nữ/Phân loại rác tái chế.mp3` -> `I`
- `Giọng nữ/Xin chỉ bỏ 1 loại rác thôi.mp3` -> multi-object warning
- `Giọng nam/Phân loại rác hữu cơ.mp3` -> `O`
- `Giọng nam/Phân loại rác vô cơ.mp3` -> `R`
- `Giọng nam/Phân loại rác tái chế.mp3` -> `I`
- `Giọng nam/XIn chỉ để 1 loại rác.mp3` -> multi-object warning

The desktop app plays these files when the UART dispatch is accepted and is
about to be sent, so the laptop speaker stays in sync with the actual dispatch
moment. Hardware mode still uses the GD5800 / OPEN-SMART audio tracks.
