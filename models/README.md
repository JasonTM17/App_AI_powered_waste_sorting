# Runtime Models

Fresh checkouts include the two model files enabled by `config.example.json`:

| File | Purpose | Size | SHA-256 |
|---|---|---:|---|
| `best.pt` | Primary 45-class YOLO detector | 5,397,573 bytes | `5453BE15AFCF94732906D72031B2F94B3307B4CE749546906E2FA857BE9B11E5` |
| `new-class-specialist.pt` | Specialist detector used for Pen, Battery, and Toothbrush | 5,406,853 bytes | `8FD59B6CF94E79B74112C3071DEBC794D52CF3EA37695563401D93939AA593BE` |

Other `.pt` files are local training outputs or optional candidates and remain
ignored. Promote a candidate only after evaluation and real-camera acceptance,
then update this manifest and the configured path in the same focused commit.

Verify the tracked files on Windows:

```powershell
Get-FileHash models/best.pt,models/new-class-specialist.pt -Algorithm SHA256
```
