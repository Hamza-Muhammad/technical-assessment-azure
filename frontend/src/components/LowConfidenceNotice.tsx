import type { RankedCandidate } from "../types/contracts";
import { titleCase } from "../lib/format";

export function LowConfidenceNotice({ topCandidate }: { topCandidate: RankedCandidate }) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4">
      <svg viewBox="0 0 24 24" fill="none" className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true">
        <path
          d="M12 9v4m0 4h.01M10.29 3.86l-8.16 14.14A2 2 0 004 21h16a2 2 0 001.87-2.99L13.71 3.86a2 2 0 00-3.42 0z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div>
        <p className="text-sm font-semibold text-amber-900">Low-confidence recommendation — dispatcher review required</p>
        <p className="mt-0.5 text-xs text-amber-800">
          The top-ranked vendor did not clear the automation gate
          {topCandidate.blockingGates.length > 0 && (
            <>
              : <span className="font-medium">{topCandidate.blockingGates.map(titleCase).join(", ")}</span>
            </>
          )}
          . Review the score breakdown and rationale below before deciding.
        </p>
      </div>
    </div>
  );
}
