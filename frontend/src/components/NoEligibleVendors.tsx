import type { ScoreFactors } from "../types/contracts";
import { titleCase } from "../lib/format";

export function NoEligibleVendors({ scoreFactors }: { scoreFactors: ScoreFactors }) {
  const exclusions = Object.entries(scoreFactors.candidateSummary.exclusions);

  return (
    <section className="animate-rise-in rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
        <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6 text-amber-600" aria-hidden="true">
          <path
            d="M12 9v4m0 4h.01M10.29 3.86l-8.16 14.14A2 2 0 004 21h16a2 2 0 001.87-2.99L13.71 3.86a2 2 0 00-3.42 0z"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>
      <h2 className="mt-4 text-base font-semibold text-amber-900">No eligible vendors found</h2>
      <p className="mx-auto mt-1.5 max-w-md text-sm text-amber-800">
        {scoreFactors.candidateSummary.vendorsInNetwork} vendors were checked against this job's requirements and none passed
        the eligibility filter. This job needs to be escalated to a supervisor for manual sourcing.
      </p>
      {exclusions.length > 0 && (
        <dl className="mx-auto mt-5 grid max-w-sm grid-cols-1 gap-2 text-left">
          {exclusions.map(([reason, count]) => (
            <div key={reason} className="flex items-center justify-between rounded-lg bg-white px-3 py-2 text-xs">
              <dt className="text-amber-800">{titleCase(reason)}</dt>
              <dd className="font-semibold tabular-nums text-amber-900">{count}</dd>
            </div>
          ))}
        </dl>
      )}
      <button
        type="button"
        disabled
        title="Not wired up in this demo — represents the saga's escalate-to-supervisor path"
        className="mt-6 cursor-not-allowed rounded-xl bg-amber-200 px-4 py-2.5 text-sm font-semibold text-amber-800"
      >
        Escalate to supervisor
      </button>
    </section>
  );
}
