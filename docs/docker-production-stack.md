# Docker production stack

Date: 2026-06-30

This guide covers the production Docker path for the web dashboard, headless
FastAPI/YOLO agent, and Supabase bridge. The Windows PySide6 desktop app stays
as a Windows EXE because camera, COM/UART, laptop audio, and GUI behavior are
host/hardware concerns.

## Runtime shape

- `trash-web`: Next.js standalone dashboard on port `3000`.
- `trash-agent`: FastAPI/headless YOLO runtime on port `8765`.
- `supabase-bridge`: sync process using the agent image and read-only host data.
- `postgres-dev`: optional local dev database, enabled only with profile
  `dev-db`.

Default Docker builds include exactly these runtime models:

| File | SHA-256 |
| --- | --- |
| `models/best.pt` | `5453BE15AFCF94732906D72031B2F94B3307B4CE749546906E2FA857BE9B11E5` |
| `models/new-class-specialist.pt` | `8FD59B6CF94E79B74112C3071DEBC794D52CF3EA37695563401D93939AA593BE` |

`Dockerfile.agent` verifies `models/runtime-models.sha256` during build. If a
model changes, update the manifest deliberately as part of model promotion.

## Required environment

Copy `docker.env.example` to a private env file outside Git or export variables
in the shell. Do not commit real secrets.

Important defaults:

```powershell
$env:TRASH_SORTER_CLIENT_REQUEST_CONCURRENCY="2"
$env:TRASH_SORTER_HARDWARE_REQUEST_CONCURRENCY="1"
$env:TRASH_SORTER_DB_QUEUE_CONCURRENCY="1"
$env:TRASH_SORTER_DB_LOCK_TIMEOUT_MS="2000"
$env:TRASH_SORTER_DB_STATEMENT_TIMEOUT_MS="15000"
```

Secrets such as `DATABASE_URL`, `TRASH_SORTER_AUTH_DATABASE_URL`,
`TRASH_SORTER_SUPABASE_DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and hardware
bridge secrets must be provided only at runtime.

## Local CPU stack

```powershell
docker compose -f compose.yml config
docker compose -f compose.yml build trash-web trash-agent supabase-bridge
docker compose -f compose.yml up -d trash-agent trash-web
```

Smoke checks:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/api/health
Invoke-WebRequest http://127.0.0.1:8765/api/status
Invoke-WebRequest http://127.0.0.1:8765/api/model/classes
Invoke-WebRequest http://127.0.0.1:3000
```

The agent image is CUDA-capable through the locked Torch CUDA packages, but it
runs on CPU when no NVIDIA GPU is exposed.

## Optional GPU exposure

Use the override only on machines with NVIDIA Container Toolkit:

```powershell
docker compose -f compose.yml -f compose.gpu.yml config
docker compose -f compose.yml -f compose.gpu.yml up -d trash-agent
```

The GPU override only adds NVIDIA device reservation/environment. It does not
create a second Python dependency graph.

## Supabase bridge

The bridge container mounts the Windows desktop data directory read-only:

```powershell
$env:TRASH_SORTER_HOST_DATA_DIR="$env:APPDATA\TrashSorter"
$env:TRASH_SORTER_SUPABASE_DATABASE_URL="postgresql://..."
docker compose -f compose.yml up -d supabase-bridge
```

The sync cycle is serialized by domain:

1. operations
2. demo targets
3. history
4. training

Each domain transaction applies bounded `lock_timeout` and `statement_timeout`,
retries lock/deadlock/serialization errors at the transaction boundary, and
writes a heartbeat after a successful cycle. Docker healthcheck validates the
heartbeat freshness.

## Vercel production web

Vercel remains the recommended public web host. Set build-time browser values in
Vercel project settings:

```text
NEXT_PUBLIC_AGENT_URL
NEXT_PUBLIC_CLOUD_API_URL
NEXT_PUBLIC_USE_CLOUD_HARDWARE_BRIDGE
TRASH_SORTER_CLIENT_REQUEST_CONCURRENCY=2
TRASH_SORTER_HARDWARE_REQUEST_CONCURRENCY=1
```

Set server-side values only as private Vercel environment variables:

```text
CRON_SECRET
DATABASE_URL
TRASH_SORTER_AUTH_DATABASE_URL
TRASH_SORTER_SUPABASE_DATABASE_URL
TRASH_SORTER_HARDWARE_BRIDGE_URL
TRASH_SORTER_HARDWARE_BRIDGE_SECRET
DEEPSEEK_API_KEY
```

The Vercel request scheduler is process-local. It limits bursts inside a single
serverless process/container; it is not a distributed global lock.

### Twice-weekly database keepalive

Both `vercel.json` files define the same production schedule so the cron remains
active whether Vercel's Root Directory is the repository root or `web/`:

```text
0 3 * * 1,4
```

This runs on Monday and Thursday at 03:00 UTC. Vercel Hobby may execute within
the scheduled hour. The protected route `/api/cron/keepalive`:

1. requires `Authorization: Bearer ${CRON_SECRET}`;
2. fails closed when the secret or database configuration is absent;
3. deduplicates identical auth/Supabase database URLs;
4. touches configured databases sequentially with bounded query timeout;
5. returns only sanitized target names and timestamps.

Vercel injects the bearer header automatically when `CRON_SECRET` is configured
in Production. Generate a long random value in Vercel; never add it to Git.

## Publish images to Docker Hub

After local build and smoke tests pass:

```powershell
$repo="docker.io/<dockerhub-user>"
docker tag trash-sorter-web:local "$repo/trash-sorter-web:$(git rev-parse --short HEAD)"
docker tag trash-sorter-web:local "$repo/trash-sorter-web:latest"
docker tag trash-sorter-agent:local "$repo/trash-sorter-agent:$(git rev-parse --short HEAD)"
docker tag trash-sorter-agent:local "$repo/trash-sorter-agent:latest"
docker push "$repo/trash-sorter-web:$(git rev-parse --short HEAD)"
docker push "$repo/trash-sorter-web:latest"
docker push "$repo/trash-sorter-agent:$(git rev-parse --short HEAD)"
docker push "$repo/trash-sorter-agent:latest"
```

Because `trash-agent` contains the two model artifacts, do not push it to a
public registry unless the model license/project policy allows public model
distribution.

The release namespace for this project is:

```text
docker.io/nguyenson1710
```

The `Publish release containers` GitHub Actions workflow mirrors an already
verified Docker Hub release tag to `ghcr.io/JasonTM17` so the web, agent, model,
and desktop artifact images also appear under the repository's **Packages**
section. The workflow never receives Docker Hub credentials because it reads
the public source images and authenticates to GHCR with the repository-scoped
`GITHUB_TOKEN`.

## Free local disk safely

After images are pushed and at least one remote pull has been verified:

```powershell
docker builder prune
docker image prune
docker system df
```

Use `docker system prune -a` only after confirming no other local projects need
their cached images. Do not delete tracked files under `models/` from the Git
working tree just to free disk; that would remove the production artifacts from
the repository unless a new external model-download flow is implemented.

## Model promotion and rollback

Promotion:

1. Evaluate candidate model with `scripts/evaluate_yolo.py`.
2. Manually replace only the approved runtime artifact.
3. Update `models/runtime-models.sha256`.
4. Build `trash-agent` and confirm checksum verification.
5. Smoke `/api/model/classes` before pushing.

Rollback:

1. Revert the model/manifest commit or retag the previous Docker image digest.
2. Redeploy `trash-agent` from the previous image tag.
3. Keep desktop EXE and Docker images tied to the same verified Git commit.

## Windows EXE

Desktop GUI release still uses:

```powershell
python -m uv run python scripts/build_exe.py
```

The EXE is the supported path for real camera, COM/UART, laptop audio testing,
and PySide6 UI operation on Windows.
