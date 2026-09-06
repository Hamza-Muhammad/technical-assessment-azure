import type { RankedCandidate, VendorProfile } from "../types/contracts";
import { formatScore100 } from "../lib/format";
import { Badge } from "./ui/Badge";
import { ScoreBreakdown } from "./ScoreBreakdown";

const RANK_MEDAL: Record<number, string> = {
  1: "bg-amber-400 text-amber-950",
  2: "bg-slate-300 text-slate-800",
  3: "bg-orange-300 text-orange-900",
};

interface VendorCardProps {
  candidate: RankedCandidate;
  vendor?: VendorProfile;
  selected: boolean;
  isTopPick: boolean;
  onSelect: () => void;
}

export function VendorCard({ candidate, vendor, selected, isTopPick, onSelect }: VendorCardProps) {
  const name = vendor?.displayName ?? candidate.vendorId;

  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={`w-full rounded-2xl border p-4 text-left transition-all ${
        selected
          ? "border-violet-400 bg-violet-50/60 shadow-sm ring-2 ring-violet-200"
          : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
              RANK_MEDAL[candidate.rank] ?? "bg-slate-100 text-slate-600"
            }`}
          >
            {candidate.rank}
          </span>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-slate-900">{name}</span>
              {isTopPick && (
                <Badge tone="brand" className="py-0.5">
                  AI top pick
                </Badge>
              )}
            </div>
            {vendor && <span className="text-xs text-slate-500">{vendor.tier} · {vendor.performance.jobsCompleted} jobs / {vendor.performance.windowDays}d</span>}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold tabular-nums text-slate-900">{formatScore100(candidate.finalScore)}</div>
          <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">final score</div>
        </div>
      </div>

      <div className="mt-3.5">
        <ScoreBreakdown
          ruleScore={candidate.ruleScore}
          mlScore={candidate.mlScore}
          confidence={candidate.confidence}
          confidenceBand={candidate.confidenceBand}
        />
      </div>
    </button>
  );
}
