# Container and dataset artifact release `99369b06a697`

Date: 2026-06-30

This release publishes the verified runtime, model, desktop EXE artifact, and
dataset archive images for commit `99369b06a697`.

Docker Hub namespace: `docker.io/nguyenson1710`

## Published runtime artifacts

| Artifact | Tag | Digest |
| --- | --- | --- |
| Web dashboard | `nguyenson1710/trash-sorter-web:99369b06a697` | `sha256:9b0ce23c8c673a3fc55503b1faba5e8097a0aa246ef8ac6f9284fee5e6351bd6` |
| Headless FastAPI/YOLO agent | `nguyenson1710/trash-sorter-agent:99369b06a697` | `sha256:ce27b8f19681c33a8527551ff1f52a7365737cce0ff46734de2b86178f46eba4` |
| Runtime model artifact | `nguyenson1710/trash-sorter-models:99369b06a697` | `sha256:e694a9b23807423d1cd925fc2db7cdb5dfbde7cad0324350bd7c0988f5daf94c` |
| Windows desktop EXE artifact | `nguyenson1710/trash-sorter-desktop-exe:99369b06a697` | `sha256:f05770117016f963f46c12ec6fc0b67b382a620ff69b02528ba02ad5ce36c6d7` |
| Dataset archive index | `nguyenson1710/trash-sorter-dataset-archive:99369b06a697` | `sha256:4aad51a7e73a8fff06dc780e1b6c7f902a454c25289466eb628ceb4119c1e53e` |

The same runtime artifacts were mirrored to GitHub Packages through the
`Publish release containers` workflow:

<https://github.com/JasonTM17/App_AI_powered_waste_sorting/actions/runs/28422160524>

## Dataset archive layout

The dataset archive is intentionally split into ten independent part images
instead of one huge image. The index image contains only metadata and restore
instructions. Payload images are tagged as:

```text
nguyenson1710/trash-sorter-dataset-archive:99369b06a697-part01
...
nguyenson1710/trash-sorter-dataset-archive:99369b06a697-part10
```

Total compressed archive payload: `41,448,199,333` bytes, about `38.60 GiB`.

Excluded from the archive: `.env*`, local database files, SQLite files, logs,
and `config.json`.

| Part | Slug | Size | Archive SHA-256 | Remote digest |
| --- | --- | ---: | --- | --- |
| 01 | `classifiers` | 2.76 GiB | `203e5d4d7da58ffc630a54e8004ac2f17a6a0edc34194bd9e97c4d9b5e7dcfea` | `sha256:69f0a3dee63050b9ac6717d48adf1a3f95a289debf10b5112e30a0b3d6ae9817` |
| 02 | `low-conf-queue` | 4.70 GiB | `84a31fd591d30059146f02ae2f2a83ffd455a1601eeac2cbd0d0f076cb064a8e` | `sha256:cc354eee12274551b6f7c137c0fa4ff845c2f5e6756325d824073c5ed1114814` |
| 03 | `camera-anchor` | 5.82 GiB | `cb4ef577ac510e8d3b04cd40823d964f28364498ee27d942884c6e0012baa350` | `sha256:64e3c0940a0223cd0317db97d7ebc63a017caab37e34cffd1e0541929b71a78c` |
| 04 | `camera-truth` | 4.00 GiB | `d4d6ab4acf0200f7741e60cfad0b7f4f68a46ebf524bed1c303262c9b51cf0aa` | `sha256:0ccd95bc7b3d64571829acb47b9ca0fccfb1bf03025f10ff0716341e8d38e4b4` |
| 05 | `can-bottle` | 4.10 GiB | `2212c117dd8f855e51b136857e9b71f7ce26660faa8311293a9a30a802549a09` | `sha256:25d15041d596a762b1afd54f8fae1891add115e729b6c295ab806ff277ffbd32` |
| 06 | `fast-common` | 2.10 GiB | `7179fc3be82a58e8b5aa2200e9095f1f427441bbe1d95d118bb808c6c356b788` | `sha256:f8fba1efcd3a2c0e48d0e56c0816cf8084b63ab9faf228052e7914ee2a28e216` |
| 07 | `fast-pen` | 1.64 GiB | `b236fd908a2e02622e535c3546544933ac2b0cd6b143cfb608bba2d472efe985` | `sha256:7379b5ed61fd1c19a1bbc6966aafcfcdc632afd7cf49ef6d4ad60aa1366860bd` |
| 08 | `kaggle-real` | 5.32 GiB | `a327e41fe3d1d28605a8855aec09fff9b967c622260b969932ad49f6e47bebe0` | `sha256:e10fae2ab36a087648258fc33112956d2f2b7ac56eaf15d0862234537f849680` |
| 09 | `balanced-strong` | 2.60 GiB | `35e7d3fab6062c21e893adbfb07050e5e9054d91cd10191d408199aca41192d1` | `sha256:2aff6b1e27eefc506e3697b2536de9b446dc14133ccf529a401fc898ef63195d` |
| 10 | `trainset-weak` | 5.57 GiB | `ee2d80c781bbab058e8e081cf34aff70b94137d741a73507cc5185410cfd2bb8` | `sha256:5b3e739c3beb8e91e29d8f2b45a4d51c4b92103f4e72cd9f00656349a9f55397` |

## Restore dataset on Windows

Each part is an independent `.tar.zst` archive rooted at `dataset_v2/`. Do not
concatenate parts. Extract every archive into the same restore destination.

```powershell
$release = "99369b06a697"
$repo = "nguyenson1710/trash-sorter-dataset-archive"
$restoreRoot = "D:\trash-sorter-restore"
$partsRoot = Join-Path $restoreRoot "parts"
New-Item -ItemType Directory -Force -Path $restoreRoot, $partsRoot | Out-Null

for ($i = 1; $i -le 10; $i++) {
  $part = "part{0:D2}" -f $i
  $tag = "${repo}:${release}-${part}"
  docker pull $tag
  $cid = docker create $tag
  $partDir = Join-Path $partsRoot $part
  New-Item -ItemType Directory -Force -Path $partDir | Out-Null
  docker cp "${cid}:/artifacts/dataset/." $partDir
  docker rm $cid

  $shaFile = Get-ChildItem -LiteralPath $partDir -Filter "*.sha256" | Select-Object -First 1
  $expected = (Get-Content -LiteralPath $shaFile.FullName).Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)[0]
  $archive = Get-ChildItem -LiteralPath $partDir -Filter "*.tar.zst" | Select-Object -First 1
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive.FullName).Hash.ToLowerInvariant()
  if ($actual -ne $expected) {
    throw "Checksum mismatch for $part"
  }
  tar.exe --zstd -xf $archive.FullName -C $restoreRoot
}
```

After restore, the dataset is under:

```text
D:\trash-sorter-restore\dataset_v2
```

## Verification evidence

- Every part image was pushed to Docker Hub, inspected with `docker buildx
  imagetools inspect`, pulled back, and verified with the bundled `.sha256`.
- The index image was pushed, pulled back, and verified with
  `dataset-v2-99369b06a697.release-manifest.json.sha256`.
- `latest` for `trash-sorter-dataset-archive` points to the same digest as the
  immutable `99369b06a697` index tag.
- Protected file `web/next-env.d.ts` remained unchanged with SHA-256
  `7AD303E40D4FDDF44F156129E397511953A71481C5CFD86B1862649AAAF240CC`.

## Keepalive status

Vercel Cron is configured to call `/api/cron/keepalive` twice weekly:

```text
0 3 * * 1,4
```

That means Monday and Thursday at 03:00 UTC. The route accepts documented Vercel
Cron headers or manual bearer `CRON_SECRET`, then touches configured
Postgres/Supabase targets with sanitized output only.
