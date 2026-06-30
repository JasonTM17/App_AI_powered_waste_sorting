# Repository professional audit - 2026-06-30

This audit captures what is already professional, what remains risky, and what
should be cleaned before the next public release.

## Current release posture

| Area | Status | Evidence |
| --- | --- | --- |
| Docker runtime images | Done | Web, agent, models, desktop EXE artifact, and dataset archive images were pushed under `nguyenson1710`. |
| Dataset/archive | Done | Split archive plus index image documented in `docs/releases/container-dataset-release-99369b06a697.md`. |
| Keepalive | Fixed + configured | Vercel cron exists in both `vercel.json` and `web/vercel.json` with Monday/Thursday schedule; route now accepts documented Vercel Cron headers plus bearer manual checks. |
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
| Done | UTF-8 audit found the repo content is mostly valid Vietnamese; the earlier mojibake was largely PowerShell display/code-page output. | Removed one real mojibake fallback string in `app/core/pipeline.py`, removed a UTF-8 BOM from the bin-map component, and kept encoding regression tests. |
| Done | Public production demo login was missing. | Created and verified low-privilege `demo-user`; seeded demo stations/history. Real Admin credentials remain private. |
| Done | Dedicated Admin screenshots were missing. | Added Admin accounts, roles, and bin-map screenshots to `docs/assets/screenshots` and linked them from the Admin guide. |
| Medium | README is long, but GitHub/source UTF-8 rendering is now acceptable. | Keep README concise and link to deeper docs; avoid reintroducing terminal-codepage mojibake. |
| Medium | Root has many deployment files. | Acceptable for now; if it grows further, add a `docs/deployment-index.md` and keep Dockerfiles in root for Docker build ergonomics. |
| Medium | `recognition-audit-report.md` is very large. | Split into summary + archived detail if GitHub readability becomes poor. |
| Low | Many model candidates are present in `models/`. | Keep only production models tracked; ensure candidate files remain ignored or documented as local artifacts. |
| Low | Full mypy has broad existing debt. | Keep release gate targeted to modified desktop/runtime files unless a type-cleanup phase is scheduled. |
| Done | `npm ci` reported one high-severity `undici` advisory through `jsdom`. | Updated the lockfile/dependency resolution with `npm audit fix`; `npm audit --audit-level=high` now reports zero vulnerabilities. |

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

- accepts real Vercel Cron requests with `User-Agent: vercel-cron/1.0` and the
  configured `x-vercel-cron-schedule`;
- keeps `CRON_SECRET` for manual bearer verification;
- uses server-side environment variables only;
- touches configured Postgres targets sequentially;
- optionally touches Supabase PostgREST with service role from server env;
- returns sanitized target names and status only.

Vercel CLI evidence on 2026-06-30:

- production env names exist for `CRON_SECRET`, auth/Postgres, Supabase URL, and
  Supabase service-role key;
- no raw secret values were printed;
- `vercel logs --environment production --query "/api/cron/keepalive" --since 14d`
  returned no keepalive records, so deploy the route fix before treating cron as
  fully verified by logs.

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
- Watch the next Monday/Thursday Vercel Cron run and confirm a fresh
  `/api/cron/keepalive` log entry appears in Production logs.

## Unresolved questions

- None for this release polish pass. Admin credentials remain private by design.
