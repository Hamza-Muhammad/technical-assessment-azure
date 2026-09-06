import type { ConfidenceBand } from "../types/contracts";
import { Badge, type BadgeTone } from "./ui/Badge";
import { MeterBar } from "./ui/MeterBar";

const BAND_TONE: Record<ConfidenceBand, BadgeTone> = {
  HIGH: "success",
  MEDIUM: "warning",
  LOW: "danger",
};

interface ScoreBreakdownProps {
  /** 0-100 scale (backend/domain/rule_score.py). */
  ruleScore: number;
  /** 0-100 scale, or null when this run was RULES_ONLY / an ML-fallback (mlTrustFactor 0). */
  mlScore?: number | null;
  /** 0-1 scale (backend/domain/blend.py compute_confidence). */
  confidence: number;
  confidenceBand: ConfidenceBand;
}

/**
 * The core "make the data model legible" widget: final score's two inputs (rule vs. ML)
 * plus the resulting confidence, as three small inline meters — visible at a glance,
 * never hidden behind a click.
 */
export function ScoreBreakdown({ ruleScore, mlScore, confidence, confidenceBand }: ScoreBreakdownProps) {
  return (
    <div className="space-y-1.5">
      <MeterBar label="Rule" value={ruleScore / 100} valueLabel={String(Math.round(ruleScore))} tone="slate" title="Deterministic rule score (stage 2), 0-100" />
      {mlScore != null ? (
        <MeterBar label="ML" value={mlScore / 100} valueLabel={String(Math.round(mlScore))} tone="violet" title="ML uplift score (stage 3), 0-100" />
      ) : (
        <div className="flex items-center gap-2" title="ML uplift not applied this run (RULES_ONLY / ML fallback)">
          <span className="w-9 shrink-0 text-[11px] font-medium uppercase tracking-wide text-slate-400">ML</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100" />
          <span className="w-9 shrink-0 text-right text-xs font-medium text-slate-400">n/a</span>
        </div>
      )}
      <div className="flex items-center gap-2">
        <span className="w-9 shrink-0 text-[11px] font-medium uppercase tracking-wide text-slate-400">Conf.</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full rounded-full ${confidenceBand === "HIGH" ? "bg-emerald-500" : confidenceBand === "MEDIUM" ? "bg-amber-500" : "bg-rose-500"}`}
            style={{ width: `${confidence * 100}%` }}
          />
        </div>
        <Badge tone={BAND_TONE[confidenceBand]} className="shrink-0 py-0.5">
          {confidenceBand}
        </Badge>
      </div>
    </div>
  );
}
