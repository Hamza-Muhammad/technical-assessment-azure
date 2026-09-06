/**
 * finalScore/ruleScore/mlScore are already on a 0-100 scale (backend/domain/rule_score.py:
 * "0-100, versioned weights in config"; blend.py combines them directly on that same
 * scale) — this just rounds for display, it does not rescale.
 */
export function formatScore100(v: number): number {
  return Math.round(v);
}

export function formatPercent(v: number, digits = 0): string {
  return `${(v * 100).toFixed(digits)}%`;
}

export function formatUsd(v: number): string {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Signed, human countdown/overrun relative to now — e.g. "in 1h 52m" or "3h 10m overdue". */
export function formatDueIn(iso: string): string {
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) return iso;
  const diffMs = target - Date.now();
  const overdue = diffMs < 0;
  const abs = Math.abs(diffMs);
  const hours = Math.floor(abs / 3_600_000);
  const minutes = Math.floor((abs % 3_600_000) / 60_000);
  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);
  const label = parts.join(" ");
  return overdue ? `${label} overdue` : `in ${label}`;
}

export function titleCase(input: string): string {
  return input
    .toLowerCase()
    .split(/[_\s]+/)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}
