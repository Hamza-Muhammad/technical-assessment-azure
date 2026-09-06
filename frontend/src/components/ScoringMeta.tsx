import type { ScoreFactors } from "../types/contracts";
import { formatDateTime } from "../lib/format";

/** Small, unobtrusive strip of scoring-run metadata — the "clean interfaces and data
 * contracts" signal, kept out of the way of the primary decision flow. */
export function ScoringMeta({ scoreFactors }: { scoreFactors: ScoreFactors }) {
  const { binding, candidateSummary, latencyMs, generatedAtUtc, scoringRunId } = scoreFactors;
  return (
    <p className="truncate text-[11px] text-slate-400" title={`Scoring run ${scoringRunId}`}>
      {binding.modelName} {binding.modelVersion} · {binding.scoringMode.replaceAll("_", " ")}
      {binding.degradedReason && ` (${binding.degradedReason.replaceAll("_", " ").toLowerCase()})`} · {latencyMs}ms ·{" "}
      {candidateSummary.afterHardFilter} of {candidateSummary.vendorsInNetwork} candidates eligible · generated{" "}
      {formatDateTime(generatedAtUtc)}
    </p>
  );
}
