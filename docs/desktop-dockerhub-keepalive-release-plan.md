# Desktop EXE + Docker Hub + Weekly Keepalive Release Plan

Updated: 2026-06-30

This is the tracked repo plan for one combined release: fix/build the Windows desktop app, publish clean Docker Hub artifacts, update GitHub documentation, and add a scheduled Vercel/Supabase keepalive.

## 1. Scope and release boundary

The release has five deliverables:

1. Windows desktop EXE:
   - output: `dist/TrashSorterPro/TrashSorterPro.exe`;
   - includes PySide6 desktop GUI, local camera/UART/audio behavior, assets, config sample, OpenCV runtime, and runtime models as required by `scripts/build_exe.py`;
   - does not run inside Docker.
2. Docker Hub desktop artifact image:
   - `docker.io/nguyenson1710/trash-sorter-desktop-exe:<git-sha>`;
   - contains `dist/TrashSorterPro/`, `desktop-exe.sha256`, and `desktop-release-manifest.json`;
   - default command prints restore instructions; it does not launch the Windows GUI inside Docker.
3. Docker Hub runtime images:
   - `docker.io/nguyenson1710/trash-sorter-web:<git-sha>`;
   - `docker.io/nguyenson1710/trash-sorter-agent:<git-sha>`;
   - optional `latest` tags only after SHA tags pass verification.
4. Optional Docker Hub artifact images:
   - `docker.io/nguyenson1710/trash-sorter-models:<manifest-sha>` if models need their own artifact;
   - `docker.io/nguyenson1710/trash-sorter-dataset-archive:<YYYYMMDD>` only if the owner explicitly wants a large non-runtime archive on Docker Hub after privacy review.
5. Vercel/Supabase keepalive:
   - Vercel Cron calls a protected Next.js route;
   - the route performs one tiny Supabase/Postgres read or single-row upsert;
   - this creates real backend/database activity instead of merely pinging a static page.

Do not publish the whole 70GB workspace as one image. Clean release means split runtime from archive data, remove caches/secrets/local DBs, and push reproducible artifacts with checksums.

## 2. Non-negotiable safety rules

- Preserve local dirty file `web/next-env.d.ts` byte-for-byte. Expected SHA-256:
  `7AD303E40D4FDDF44F156129E397511953A71481C5CFD86B1862649AAAF240CC`.
- Never bake into Docker:
  - `.env*`;
  - database URLs;
  - Supabase service keys;
  - Vercel tokens;
  - Docker credentials;
  - local SQLite DBs;
  - Windows user paths;
  - browser/auth sessions;
  - `.venv`;
  - `web/node_modules`;
  - `runs/`, raw caches, or unreviewed datasets.
- Push the small web image before the large agent image. If web push fails with `insufficient_scope`, stop and fix Docker Hub login/repository permissions before pushing the agent.
- Keep local Docker images until remote Docker Hub digests are verified.
- Do not claim hardware/manual checks pass unless they actually ran.

## 3. Phase plan

### Phase 1: Baseline and scope freeze

Goal: capture the current state before more build/push work.

Steps:

1. Record Git state:
   - `git status --short --branch`;
   - `git log --oneline -10`.
2. Record protected file hash:
   - `Get-FileHash -Algorithm SHA256 web\next-env.d.ts`.
3. Record model hashes:
   - `Get-FileHash models\best.pt, models\new-class-specialist.pt`.
4. Record Docker state:
   - `docker version`;
   - `docker system df`;
   - `docker image ls` filtered to `trash-sorter`.
5. Record disk state:
   - `Get-PSDrive C,D`.
6. Record dependency state:
   - `python --version`;
   - `python -m uv --version`;
   - `Test-Path .venv`;
   - `Test-Path web\node_modules`.
7. Confirm Docker Hub namespace:
   - use `docker info | Select-String Username`;
   - target namespace is `nguyenson1710`;
   - if empty or push fails, owner must run `docker login` or create/provide the right repository namespace.

Exit criteria:

- Baseline evidence exists.
- Protected `web/next-env.d.ts` hash is unchanged.
- Docker Hub namespace/token blocker is known before large push.

### Phase 2: Desktop fix and EXE build

Goal: rebuild the desktop environment, fix reproducible app desktop bugs, and create the Windows EXE.

Steps:

1. Recreate dependencies:
   - set `UV_CACHE_DIR=D:\PHAN LOAI RAC\.uv-cache`;
   - run `python -m uv sync --frozen`;
   - if the default `python` launcher is 3.14, force uv/Python 3.12 because `pyproject.toml` requires `<3.13`.
2. Capture desktop failure before editing:
   - desktop import smoke;
   - focused speaker/controller tests;
   - `python -m uv run python scripts/build_exe.py`.
3. Diagnose root cause:
   - copy exact error;
   - identify file/line;
   - inspect direct callers/tests;
   - do not guess or patch symptoms.
4. Fix only reproducible desktop/build bug:
   - keep hardware speaker/UART/sort dispatch semantics unchanged unless the failure proves they are wrong;
   - add regression test or packaging guard.
5. Verify:
   - targeted `ruff check`;
   - targeted `pytest`;
   - desktop import smoke;
   - PyInstaller build.
6. Confirm output:
   - `dist/TrashSorterPro/TrashSorterPro.exe` exists.
7. Commit intentional desktop change:
   - example: `fix(desktop): stabilize release build`.

Exit criteria:

- Focused desktop gates pass.
- EXE exists.
- Manual acceptance checklist is ready for laptop audio, camera, COM/UART, and UI non-freeze.

### Phase 3: Docker Hub packaging strategy

Goal: turn the large workspace into clean Docker artifacts.

Default images:

| Image | Purpose | Included | Excluded |
| --- | --- | --- | --- |
| `trash-sorter-desktop-exe` | Windows EXE artifact | `dist/TrashSorterPro`, checksum, release manifest | `.env*`, local DB, logs, user config, caches |
| `trash-sorter-web` | Next.js dashboard | standalone Next build, public assets | `.env*`, host `node_modules`, local caches |
| `trash-sorter-agent` | FastAPI/YOLO runtime + bridge command | app, scripts, config sample, `best.pt`, `new-class-specialist.pt` | dataset, runs, local DB, secrets |
| `trash-sorter-models` optional | model artifact | promoted model set + checksum manifest | app source, datasets, secrets |
| `trash-sorter-dataset-archive` optional | non-runtime archive | curated compressed archive only | raw cache, private/unreviewed data, secrets |

Steps:

1. Audit `.dockerignore`.
2. Package the desktop EXE artifact:
   - `python -m uv run python scripts/build_exe.py`;
   - `python -m uv run python scripts/package_desktop_artifact.py`;
   - `docker build -f Dockerfile.desktop-artifact -t trash-sorter-desktop-exe:local .`.
3. Rebuild clean runtime images:
   - `docker build -f Dockerfile.web -t trash-sorter-web:local .`;
   - `docker build -f Dockerfile.agent -t trash-sorter-agent:local .`.
4. Verify model checksums inside agent:
   - `docker run --rm trash-sorter-agent:local sha256sum -c models/runtime-models.sha256`.
5. Smoke local containers:
   - agent `/api/health`;
   - agent `/api/status` and `/api/model/classes` with temporary token;
   - web `/` on a temporary port.
6. Decide whether optional artifact images are needed.
7. Label images with git SHA, build date, source repo, and model manifest hash.

Exit criteria:

- Runtime context excludes secrets/caches/local DB/datasets/runs by default.
- Agent model checksums pass.
- Web and agent local smoke tests pass.
- Optional huge artifact images are explicitly approved before push.

### Phase 4: Registry push and repo documentation

Goal: push verified images to Docker Hub and update the repository with exact run/rollback docs.

Push order:

1. `trash-sorter-web:<git-sha>`;
2. `trash-sorter-agent:<git-sha>`;
3. `trash-sorter-desktop-exe:<git-sha>`;
4. `latest` tags after SHA tags are verified;
5. optional artifact images after explicit approval.

Steps:

1. Confirm Docker Hub login/namespace/repository.
2. Tag images:
   - `docker tag trash-sorter-web:local nguyenson1710/trash-sorter-web:<git-sha>`;
   - `docker tag trash-sorter-agent:local nguyenson1710/trash-sorter-agent:<git-sha>`;
   - `docker tag trash-sorter-desktop-exe:local nguyenson1710/trash-sorter-desktop-exe:<git-sha>`.
3. Push web first:
   - if `insufficient_scope`, stop and fix Docker Hub permissions.
4. Push agent.
5. Push desktop EXE artifact.
6. Capture remote digests:
   - `docker buildx imagetools inspect <image>:<tag>`.
7. Update docs:
   - image names/tags/digests;
   - CPU/GPU compose commands;
   - environment variables;
   - model checksum verification;
   - rollback commands;
   - disk cleanup commands.
8. Commit and push GitHub.

Exit criteria:

- Docker Hub SHA tags exist and have recorded digests.
- `latest` points to the verified SHA digest.
- README/deployment docs are current.
- GitHub repo is pushed.

### Phase 5: Twice-weekly Vercel/Supabase keepalive

Goal: add a scheduled Vercel request that genuinely touches Supabase/Postgres.

Implemented contract:

- route: `web/src/app/api/cron/keepalive/route.ts`;
- env: `CRON_SECRET`;
- schedule in `vercel.json`;
- operation: one cheap Supabase/Postgres read or single-row heartbeat upsert.

Requested weekly schedule:

```json
{
  "path": "/api/cron/keepalive",
  "schedule": "0 3 * * 1"
}
```

Safer schedule recommendation:

```json
{
  "path": "/api/cron/keepalive",
  "schedule": "0 3 * * 1,4"
}
```

Decision: use the safer twice-weekly schedule (`0 3 * * 1,4`). Vercel
interprets the schedule in UTC. Hobby cron execution has hourly precision, so
the request can arrive at any point during the 03:00 UTC hour.

Route contract:

1. Force dynamic execution.
2. Verify `Authorization: Bearer ${CRON_SECRET}`.
3. Reject bad auth with 401.
4. Fail safely if `CRON_SECRET` is missing.
5. Perform one DB operation with timeout.
6. Return sanitized JSON:

```json
{
  "ok": true,
  "touched": "supabase",
  "source": "vercel-cron",
  "timestamp": "2026-06-30T00:00:00.000Z"
}
```

Test cases:

- unauthorized request returns 401;
- missing secret fails closed;
- authorized request calls DB helper once;
- DB failure returns sanitized 5xx;
- successful call updates or reads Supabase;
- no secrets appear in response/logs.

Exit criteria:

- `vercel.json` has cron entry.
- Keepalive route is protected.
- Keepalive touches Supabase/Postgres, not only Vercel.
- Unit tests and Next build pass.
- Production verification confirms fresh heartbeat/read timestamp.

### Phase 6: Release verification and cleanup

Goal: prove desktop, Docker Hub, GitHub, Vercel, and Supabase are all coherent.

Verification checklist:

1. Desktop:
   - focused tests pass;
   - EXE exists;
   - manual Windows startup if safe;
   - laptop audio male/female manual test if user is present.
2. Docker local:
   - `docker compose -f compose.yml config --quiet`;
   - agent health/status/classes with token;
   - web root 200;
   - model checksum inside agent.
3. Docker Hub:
   - pull desktop EXE SHA tag;
   - extract `/artifacts/TrashSorterPro`;
   - run `sha256sum -c desktop-exe.sha256`;
   - pull web SHA tag;
   - pull agent SHA tag;
   - inspect digests;
   - optionally smoke pulled tags.
4. Vercel/Supabase:
   - keepalive unit tests;
   - Next build;
   - authorized production route call;
   - Supabase heartbeat/read timestamp updated.
5. Git:
   - final commit exists;
   - only intentional dirty file remains local if any;
   - `git push origin main`.
6. Disk cleanup:
   - `docker builder prune -af`;
   - do not run `docker system prune -a` unless user approves deleting local images;
   - keep EXE output if user wants local release folder.

Exit criteria:

- Desktop EXE exists.
- Docker Hub remote digests are recorded.
- Vercel cron and Supabase heartbeat are verified.
- GitHub repo is up to date.
- Final evidence report lists pass/fail/blocked and unresolved questions.

## 4. Known blockers before implementation

- Docker Hub push previously failed once with `insufficient_scope` under a different namespace. Current target namespace is `nguyenson1710`; push still requires Docker Desktop login with rights to that namespace.
- Use uv-managed Python 3.12 because `pyproject.toml` requires `<3.13`.
- Keepalive cadence is twice weekly to avoid the Supabase 7-day inactivity edge.
- Manual hardware acceptance needs the Windows machine, camera, COM/UART, and laptop speaker available.

## 5. Source notes

- Vercel Cron Jobs: <https://vercel.com/docs/cron-jobs>
- Supabase Free project pausing: <https://supabase.com/docs/guides/platform/free-project-pausing>
- Docker Hub usage and limits: <https://docs.docker.com/docker-hub/usage/>

## 6. Unresolved questions

- Production route verification must run after the commit containing the route
  is deployed by Vercel.
- The large dataset archive is published as bounded parts because a single
  41 GB build context exhausted local Docker storage during layer creation.
