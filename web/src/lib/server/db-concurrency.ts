import { envConcurrency } from "@/lib/request-scheduler";

export function databasePoolConcurrency(raw = process.env.TRASH_SORTER_DB_QUEUE_CONCURRENCY) {
  return envConcurrency(raw, 1);
}
