import type { RankedCandidate, VendorProfile } from "../types/contracts";
import { formatScore100, titleCase } from "../lib/format";
import { Badge } from "./ui/Badge";

interface RationaleDetailProps {
  candidate: RankedCandidate;
  vendor?: VendorProfile;
}

export function RationaleDetail({ candidate, vendor }: RationaleDetailProps) {
  const name = vendor?.displayName ?? candidate.vendorId;
  // Mirrors backend/domain/factor_builder.py _normalize(): sorted by |contribution|, largest first.
  const sortedFactors = [...candidate.factors].sort((a, b) => Math.abs(b.contributionPct) - Math.abs(a.contributionPct));

  // narrative is only ever populated when rationale.source === "LLM" (backend/domain/rationale.py) —
  // every other path (disabled feature flag, call failure, failed groundedness check) returns
  // narrative: null and relies on the always-available deterministic `template`.
  const displayText = candidate.rationale.narrative ?? candidate.rationale.template;
  const isAiNarrated = candidate.rationale.source === "LLM" && !!candidate.rationale.narrative;

  return (
    <div key={candidate.vendorId} className="animate-rise-in space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
            Rank #{candidate.rank} recommendation
          </p>
          <h2 className="text-lg font-bold text-slate-900">{name}</h2>
        </div>
        <div className="text-right">
          <div className="text-3xl font-extrabold tabular-nums text-slate-900">{formatScore100(candidate.finalScore)}</div>
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">/ 100</div>
        </div>
      </div>

      {/* The trust centerpiece: plain-English rationale, set apart typographically. */}
      <figure className="relative rounded-2xl border border-violet-100 bg-gradient-to-br from-violet-50 to-white p-5">
        <svg className="absolute left-4 top-4 h-6 w-6 text-violet-200" fill="currentColor" viewBox="0 0 32 32" aria-hidden="true">
          <path d="M9.352 4C4.456 7.456 1 13.12 1 19.36c0 5.088 3.072 8.064 6.624 8.064 3.36 0 5.856-2.688 5.856-5.856 0-3.168-2.208-5.472-5.088-5.472-.576 0-1.344.096-1.536.192.48-3.264 3.552-7.104 6.624-9.024L9.352 4Zm16.512 0c-4.8 3.456-8.256 9.12-8.256 15.36 0 5.088 3.072 8.064 6.624 8.064 3.264 0 5.856-2.688 5.856-5.856 0-3.168-2.304-5.472-5.184-5.472-.576 0-1.248.096-1.44.192.48-3.264 3.456-7.104 6.528-9.024L25.864 4Z" />
        </svg>
        <blockquote className="pl-8 font-serif text-[15px] italic leading-relaxed text-slate-800">
          {displayText}
        </blockquote>
        <figcaption className="mt-3 flex flex-wrap items-center gap-2 pl-8 text-xs text-slate-500">
          {isAiNarrated ? (
            <Badge tone="brand">AI-generated narrative</Badge>
          ) : (
            <Badge tone="neutral">Deterministic template{candidate.rationale.fallbackUsed ? " (AI narration unavailable this run)" : ""}</Badge>
          )}
          {candidate.rationale.groundednessCheck === "PASSED" && <span>Grounded in the factors below — no invented numbers</span>}
          {candidate.rationale.groundednessCheck === "FAILED" && (
            <span className="text-amber-600">AI narrative failed the groundedness check — template shown instead</span>
          )}
        </figcaption>
      </figure>

      {candidate.counterfactual && (
        <p className="rounded-xl bg-slate-50 px-4 py-2.5 text-xs text-slate-500">
          <span className="font-semibold text-slate-600">What would change this: </span>
          {candidate.counterfactual}
        </p>
      )}

      <div>
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Contributing factors
        </h3>
        <ul className="mt-2 space-y-2">
          {sortedFactors.map((factor) => (
            <li key={factor.id} className="rounded-xl border border-slate-100 bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-800">{titleCase(factor.id)}</span>
                  <Badge tone={factor.source === "ML" ? "brand" : "info"} className="py-0">
                    {factor.source}
                  </Badge>
                </div>
                <span className="text-sm font-semibold tabular-nums text-slate-600">
                  {factor.contributionPct > 0 ? "+" : ""}
                  {factor.contributionPct}%
                </span>
              </div>
              <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full ${factor.contributionPct >= 0 ? "bg-emerald-400" : "bg-rose-400"}`}
                  style={{ width: `${Math.min(100, Math.abs(factor.contributionPct))}%` }}
                />
              </div>
              <p className="mt-1.5 text-xs text-slate-500">{factor.evidence}</p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
