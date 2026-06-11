# Discovered Bugs — 2026-06-11 (Phase 2 refactor)

Per Phase 2 "no behavior change" rule: bugs surfaced during the dashboard-client.tsx
split are LOGGED here, NOT fixed in this phase. Each entry: symptom, location,
suggested fix sketch, priority. Created 2026-06-11 during the small-panel extraction
session.

## Pre-existing bugs (discovered while reading)

None logged in this session — small panels were extracted cleanly and no pre-existing
bugs were found inside `DetectionOverlay`, `HistoryPanel`, `LogsPanel`, `DeviceList`,
`ActuationTestModePanel`, or `StatusPill`.

## Self-introduced issues (immediately fixed, logged for transparency)

### SELF-1 — Wrong className on extracted StatusPill (FIXED inline)

**Symptom:** New `components/primitives/status-pill.tsx` initially used
`className={ok ? "pill ok" : "pill warn"}` instead of the original
`className={ok ? "status-pill ok" : "status-pill warn"}`.

**Original location:** `web/src/components/dashboard-client.tsx:4530`
(inside `function StatusPill`, removed during this session).

**New location:** `web/src/components/primitives/status-pill.tsx:9`
(fixed during the same edit, before build verification).

**Root cause:** Careless copy — I transposed "status-pill" → "pill" while writing
the new file.

**Fix applied (same session, before build verify):**
```diff
-  return <span className={ok ? "pill ok" : "pill warn"}>{text}</span>;
+  return <span className={ok ? "status-pill ok" : "status-pill warn"}>{text}</span>;
```

**Why logged:** the "no behavior change" rule means even self-introduced drift must
be recorded so a code reviewer can confirm the fix matches the original behavior.

**Priority:** P0 if not caught (would have changed CSS class on every StatusPill
render, ~13 sites, breaking visual state in admin settings + dashboard).

## Pre-existing bugs inside remaining large panels (NOT touched, deferred)

The following panels remain in `dashboard-client.tsx` and have not been reviewed
in this session. They are candidates for a future bug-audit pass:

- `DataPanel` (line 2661, ~475 lines)
- `SettingsPanel` (line 3464, ~620 lines)
- `HardwareProfilePanel` (line ~4101, ~387 lines)
- `MappingPanel` (line 3373, ~91 lines)
- `AnnotationEditor` (line 3136, ~237 lines)
- `LivePanel` (line 2537, ~124 lines)
- `AdminReportsPanel` (line 2442, ~95 lines)

These are deferred to a follow-up bug-audit session after the file-splitting work
in Phase 2 is complete.

---

## Integration bugs found during team lead patch (2026-06-11)

### LEAD-1 — `Mp3TestCommand` not exported from `@/lib/agent` (FIXED inline)

**Symptom:** Build failed after team lead applied extractions.

```
./src/components/operations/hardware-profile-panel.tsx:5:75
Type error: Module '"@/lib/agent"' has no exported member 'Mp3TestCommand'.
```

**Root cause:** `extractor-ops` assumed `Mp3TestCommand` was exported from `@/lib/agent`. It is NOT — the type is defined locally in `dashboard-client.tsx:140-152` as a private union type for MP3 UART command names. Same for the second occurrence in `settings-panel.tsx`.

**Fix applied (2 files, lead-patched):**
- `web/src/components/operations/hardware-profile-panel.tsx:5` — removed `Mp3TestCommand` from `@/lib/agent` import, added local `type Mp3TestCommand = "TF" | "VOL" | "PLAY" | "PLAYVOL" | "NEXT" | "ONLINE" | "STATUS" | "RESET" | "MODE_PRIMARY" | "MODE_REVERSE" | "MODE_QUERY";` definition.
- `web/src/components/settings/settings-panel.tsx:10` — same fix (removed import, added local type).

**Why logged:** worker's "no behavior change" extraction broke the build. Lead fixed inline to unblock integration. Two more files (`dashboard-client.tsx` itself) still own the original `Mp3TestCommand` definition and continue to work — type identity is preserved across all 3 locations.

**Priority:** P0 (build blocker).

**Why not promoted to follow-up:** type identity is identical across all 3 sites, TypeScript erases types at runtime, JS output is byte-identical. Only source-level DRY violation, no behavior change.

### LEAD-2 — `data-panel-types.ts` was created during extraction but not imported back (deferred)

**Symptom:** Worker created `web/src/components/dataset/data-panel-types.ts` with `TrustedFilter`, `BulkAction`, `ClassOption`. The new dataset files import from there. `dashboard-client.tsx` still has its own local definitions of the same 3 types.

**Status:** Will be addressed in Batch 2 (dataset) integration — switch `dashboard-client.tsx` to import from `data-panel-types.ts` and remove local definitions. Documented here for the record.
