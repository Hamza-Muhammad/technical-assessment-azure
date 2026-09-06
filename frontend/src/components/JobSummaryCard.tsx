import type { JobEvent } from "../types/contracts";
import { formatDueIn, formatUsd, titleCase } from "../lib/format";
import { Badge, type BadgeTone } from "./ui/Badge";

const PRIORITY_TONE: Record<string, BadgeTone> = {
  P1: "danger",
  P2: "warning",
  P3: "info",
};

/** Dispatcher-friendly gloss for the raw P1/P2/P3 codes — not a contract field, display only. */
const PRIORITY_LABEL: Record<string, string> = {
  P1: "P1 · Emergency",
  P2: "P2 · Urgent",
  P3: "P3 · Standard",
};

const RISK_TONE: Record<string, BadgeTone> = {
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "neutral",
};

function Stat({ label, value, emphasize }: { label: string; value: string; emphasize?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={`mt-0.5 text-sm ${emphasize ? "font-semibold text-slate-900" : "text-slate-700"}`}>{value}</dd>
    </div>
  );
}

export function JobSummaryCard({ job }: { job: JobEvent }) {
  const { site, job: jobDetails, sla, risk, accountTier } = job.data;
  const priorityTone = PRIORITY_TONE[jobDetails.priority] ?? "neutral";
  const riskTone = RISK_TONE[risk.riskTier] ?? "neutral";

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">{jobDetails.tradeCategory}</h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Site {site.siteId} · <span className="font-mono">{job.jobId}</span>
          </p>
          {/* addressRef is a PII-redaction token (e.g. "pii://address/...", not a resolved
              street address) — shown as a reference, not presented as a human address, per
              Part 1's "full address released to a vendor only after acceptance" design. */}
          <p className="mt-0.5 font-mono text-[11px] text-slate-400" title="PII-redacted address reference">
            {site.addressRef}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={priorityTone} dot>
            {PRIORITY_LABEL[jobDetails.priority] ?? jobDetails.priority}
          </Badge>
          <Badge tone={riskTone} dot>
            {titleCase(risk.riskTier)} risk
          </Badge>
          {jobDetails.isRecall && <Badge tone="danger">Recall</Badge>}
          {risk.safetyRisk && <Badge tone="danger">Safety risk</Badge>}
          <Badge tone="neutral">{titleCase(accountTier)} account</Badge>
        </div>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-slate-100 pt-5 sm:grid-cols-4">
        <Stat label="Response due" value={formatDueIn(sla.responseDueUtc)} emphasize />
        <Stat label="Resolution due" value={formatDueIn(sla.resolutionDueUtc)} />
        <Stat label="Not-to-exceed" value={formatUsd(jobDetails.notToExceedUsd)} />
        <Stat label="Revenue at risk" value={formatUsd(risk.revenueAtRiskUsd)} />
      </dl>
    </section>
  );
}
