import { useEffect, useState } from "react";
import type { AuditResponse } from "../types/contracts";
import { apiClient } from "../api/client";
import { formatDateTime, titleCase } from "../lib/format";

interface AuditTrailProps {
  jobId: string;
  refreshKey?: string | number;
}

interface AuditRow {
  key: string;
  occurredAtUtc: string;
  label: string;
  detail: string;
}

function toAuditRows(audit: AuditResponse): AuditRow[] {
  const events = audit.events.map((entry, index) => ({
    key: entry.event.messageId || `event-${index}`,
    occurredAtUtc: entry.loggedAtUtc,
    label: titleCase(entry.event.type.replace(/\.v\d+$/, "").replaceAll(".", "_")),
    detail: entry.scoringRunId ? `scoring run ${entry.scoringRunId}` : `job ${entry.jobId}`,
  }));
  const decisions = audit.decisions.map((entry, index) => ({
    key: `decision-${index}`,
    occurredAtUtc: entry.loggedAtUtc,
    label: entry.decision.assignmentSource ? titleCase(entry.decision.assignmentSource) : "Decision",
    detail: `${entry.decision.selectedVendorId}${entry.decision.overrideReasonCode ? ` · ${entry.decision.overrideReasonCode}` : ""}`,
  }));
  return [...events, ...decisions].sort((a, b) => a.occurredAtUtc.localeCompare(b.occurredAtUtc));
}

export function AuditTrail({ jobId, refreshKey }: AuditTrailProps) {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setError(null);
    apiClient.getAudit(jobId).then((audit) => {
      if (!cancelled) setRows(toAuditRows(audit));
    }).catch((cause) => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load the audit trail.");
    });
    return () => { cancelled = true; };
  }, [jobId, refreshKey]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Audit trail</h2>
          <p className="mt-1 text-xs text-slate-500">Events and decisions recorded for this job.</p>
        </div>
        {rows && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">{rows.length} entries</span>}
      </div>
      {rows === null && !error && <p className="mt-4 text-xs text-slate-500">Loading audit events...</p>}
      {error && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">Audit could not be loaded: {error}</p>}
      {rows?.length === 0 && <p className="mt-4 text-xs text-slate-500">No audit entries have been returned yet.</p>}
      {rows && rows.length > 0 && (
        <ol className="mt-4 space-y-2 border-l border-slate-200 pl-4">
          {rows.map((row) => (
            <li key={row.key} className="text-xs text-slate-700">
              <span className="font-mono text-slate-400">{formatDateTime(row.occurredAtUtc)}</span>
              <span className="mx-2 font-semibold text-slate-800">{row.label}</span>
              <span className="text-slate-500">{row.detail}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
