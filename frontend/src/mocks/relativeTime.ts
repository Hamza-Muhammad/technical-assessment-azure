/**
 * SLA countdowns (`formatDueIn` in src/lib/format.ts) are computed against the real
 * clock (`Date.now()`), but these fixtures are static TS modules. Hardcoding absolute
 * timestamps (as backend/data/jobs.json does, since it's just seed data, not something
 * rendered as a live countdown) would make the "response due in Xh" badges read as stale
 * or nonsensical whenever the demo is actually run. This computes them relative to
 * import time instead, so the countdowns always look like a live, in-flight job.
 */
export function hoursFromNow(hours: number): string {
  return new Date(Date.now() + hours * 3_600_000).toISOString();
}
