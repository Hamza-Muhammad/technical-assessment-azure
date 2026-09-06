import type { RankedCandidate, VendorProfile } from "../types/contracts";
import { titleCase } from "../lib/format";
import { Badge } from "./ui/Badge";

const DATA_SUFFICIENCY_TONE = {
  SUFFICIENT: "success",
  SPARSE: "warning",
  COLD_START: "danger",
} as const;

/**
 * Unobtrusive guardrail strip, evaluated against the TOP-ranked candidate only (per the
 * product brief) — this is what makes the screen read as a production system with gates,
 * not a demo that always trusts the model.
 */
export function AutomationGateStatus({ topCandidate, topVendor }: { topCandidate: RankedCandidate; topVendor?: VendorProfile }) {
  const sufficiency = topVendor?.performance.dataSufficiency;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {topCandidate.automationEligible ? (
        <Badge tone="success" dot>
          Auto-assign eligible
        </Badge>
      ) : (
        <Badge
          tone="warning"
          dot
          title={topCandidate.blockingGates.length ? `Blocking: ${topCandidate.blockingGates.join(", ")}` : undefined}
        >
          Needs dispatcher review
          {topCandidate.blockingGates.length > 0 && ` · ${topCandidate.blockingGates.length} gate${topCandidate.blockingGates.length > 1 ? "s" : ""} blocking`}
        </Badge>
      )}
      {sufficiency && (
        <Badge tone={DATA_SUFFICIENCY_TONE[sufficiency]} dot>
          Data: {titleCase(sufficiency)}
        </Badge>
      )}
    </div>
  );
}
