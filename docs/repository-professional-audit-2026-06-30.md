# Repository professional audit - 2026-06-30

This audit captures what is already professional, what remains risky, and what
should be cleaned before the next public release.

## Current release posture

| Area | Status | Evidence |
| --- | --- | --- |
| Docker runtime images | Done | Web, agent, models, desktop EXE artifact, and dataset archive images were pushed under `nguyenson1710`. |
| Dataset/archive | Done | Split archive plus index image documented in `docs/releases/container-dataset-release-99369b06a697.md`. |
| Keepalive | Configured | Vercel cron exists in both `vercel.json` and `web/vercel.json` with Monday/Thursday schedule. |
| Desktop EXE strategy | Correct | Desktop is distributed as Windows EXE artifact image, not as runnable PySide Linux container. |
| Secrets hygiene | Mostly good | `.env.local`, `config.json`, `.vercel`, `AGENTS.md`, and shortcut files are ignored. |
| Dirty tracked state | Intentional | `web/next-env.d.ts` remains local dirty and must not be staged. |

## Local ignored files that should stay local

These files/folders exist locally or commonly appear locally and should not be
committed:

| Path | Reason |
| --- | --- |
| `.env.local` | Private secrets/API keys/DB URLs. |
| `config.json` | Local hardware and UI settings. |
| `.vercel/` | Local Vercel project metadata. |
| `AGENTS.md` | Local agent instruction file requested to stay out of git. |
| `Trash Sorter Pro.lnk` | Windows shortcut. |
| `dataset_v2/` | Large training/cache data; archived separately. |
| `runs/`, `audit/`, `reports/` | Training/evaluation outputs unless a small curated report is intentionally committed. |
| `dist/`, `build/` | Build outputs; desktop artifact image carries verified bundle. |

## Things already well organized

- `app/core/` is separated from UI and exposes the reusable AI/runtime layer.
- `app/ui/` owns PySide desktop screens and controller wiring.
- `app/agent/` exposes FastAPI/headless runtime for web and bridge use.
- `web/` owns Next.js Admin/User dashboard.
- `scripts/` has focused commands for build, train, eval, bridge, seed, and
  Docker archive publishing.
- `docs/` contains deployment, architecture, model evaluation, release, and QA
  documents.
- Runtime Dockerfiles are separate from the desktop artifact Dockerfile.
- Model checksums are documented for the two production model files.

## Issues to fix before a polished public release

| Priority | Issue | Recommended action |
| --- | --- | --- |
| High | Several Markdown/code strings render Vietnamese as mojibake in terminal snapshots, e.g. `Há»¯u cÆ¡`. | Normalize source files to UTF-8 and verify GitHub rendering before the next release. Do this in a dedicated commit because it will touch many lines. |
| High | Public production login credentials should not be committed. | Create a disposable low-privilege demo User in production, seed demo data, rotate often, and document it only if intentionally public. Never publish real Admin password. |
| Medium | No dedicated Admin screenshots in `docs/assets/screenshots`. | Capture Admin accounts/roles/bin-map/settings screens and add them to the admin guide. |
| Medium | README is long and currently shows encoding artifacts locally. | Keep README concise and link to docs; repair encoding in a focused UTF-8 cleanup. |
| Medium | Root has many deployment files. | Acceptable for now; if it grows further, add a `docs/deployment-index.md` and keep Dockerfiles in root for Docker build ergonomics. |
| Medium | `recognition-audit-report.md` is very large. | Split into summary + archived detail if GitHub readability becomes poor. |
| Low | Many model candidates are present in `models/`. | Keep only production models tracked; ensure candidate files remain ignored or documented as local artifacts. |
| Low | Full mypy has broad existing debt. | Keep release gate targeted to modified desktop/runtime files unless a type-cleanup phase is scheduled. |

## Keepalive audit

Configured cron:

```text
0 3 * * 1,4
```

Meaning: every Monday and Thursday at `03:00 UTC`.

Files:

- `vercel.json`
- `web/vercel.json`
- `web/src/app/api/cron/keepalive/route.ts`
- `web/src/lib/server/keepalive.ts`

The implementation is bounded and safe:

- requires `CRON_SECRET`;
- uses server-side environment variables only;
- touches configured Postgres targets sequentially;
- optionally touches Supabase PostgREST with service role from server env;
- returns sanitized target names and status only.

What cannot be proven from git alone:

- whether Vercel Production currently has `CRON_SECRET`;
- whether production DB/Supabase env values are present;
- whether the latest two cron invocations succeeded in Vercel logs.

## Disk cleanup state

Local cleanup already moved the project toward a lighter workstation state:

- Docker build cache and unused Docker objects were cleaned.
- Large local dataset/cache directories were removed after the Docker Hub archive
  was pushed and verified.
- `D:` free space increased enough for another project.
- `C:` temp/cache cleanup was performed, but Docker/WSL VHD compaction may still
  require an elevated/admin shell if more space is needed.

## Release checklist still recommended

- Pull back every Docker Hub image on a clean machine.
- Extract the desktop EXE artifact and verify checksum manifest.
- Restore dataset archive to a temp folder and verify all part checksums.
- Run web production smoke: login, `/api/health`, Admin dashboard, User
  dashboard, and keepalive endpoint with bearer secret.
- Run agent smoke: `/api/status`, `/api/model/classes`, `/api/health`.
- Run manual Windows EXE smoke with laptop speaker male/female voices.
- Capture missing Admin screenshots.
- Run a focused UTF-8 cleanup pass.

## Unresolved questions

- Which disposable production demo User credential should be made public, if any?
- Should a public Admin demo account exist at all? Recommended answer: no.
- Do you want a dedicated encoding-cleanup release after this documentation pass?
