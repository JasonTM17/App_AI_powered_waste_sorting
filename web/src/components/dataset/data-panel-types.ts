// Shared types used by data-panel.tsx and data-panel-list.tsx.

import type { DatasetItem, DatasetSummary } from "@/lib/agent";

export type TrustedFilter = "all" | "trusted" | "untrusted";
export type BulkAction = "delete" | "relabel" | "quarantine" | "mark_trusted" | "mark_untrusted";
export type ClassOption = { id: number; name: string };

export type { DatasetItem, DatasetSummary };
