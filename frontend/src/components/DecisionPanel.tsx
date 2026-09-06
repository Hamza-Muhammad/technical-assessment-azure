import { useState } from "react";
import type { AssignmentResponse, OverrideReasonCode, VendorProfile } from "../types/contracts";
import { apiClient } from "../api/client";
import { Button } from "./ui/Button";

const REASON_OPTIONS: { value: OverrideReasonCode; label: string }[] = [
  { value: "CUSTOMER_RELATIONSHIP", label: "Customer relationship" },
  { value: "LOCAL_KNOWLEDGE", label: "Local knowledge" },
  { value: "CAPACITY_DATA_WRONG", label: "Capacity data is wrong" },
  { value: "PRIOR_QUALITY_ISSUE", label: "Prior quality issue" },
  { value: "MODEL_DISAGREE_OTHER", label: "Disagree with model — other" },
];

interface DecisionPanelProps {
  jobId: string;
  recommendedVendorId: string;
  selectedVendorId: string;
  vendors: Record<string, VendorProfile>;
  onDecided: (response: AssignmentResponse, isOverride: boolean, reasonCode?: OverrideReasonCode) => void;
}

export function DecisionPanel({
  jobId,
  recommendedVendorId,
  selectedVendorId,
  vendors,
  onDecided,
}: DecisionPanelProps) {
  const [reasonCode, setReasonCode] = useState<OverrideReasonCode | "">("");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const isOverride = selectedVendorId !== recommendedVendorId;
  const selectedName = vendors[selectedVendorId]?.displayName ?? selectedVendorId;
  const reasonMissing = isOverride && reasonCode === "";

  async function handleSubmit() {
    setTouched(true);
    if (reasonMissing) return;
    setSubmitting(true);
    setError(null);
    try {
      // Real backend/contracts/models.py AssignmentRequest shape: jobId travels in the URL,
      // correlationId/scoringRunId are resolved server-side from the job's stored
      // ScoreFactors, so they aren't sent here even though this component tracks them
      // locally (for the confirmation banner text and the accept-vs-override branch).
      const response = await apiClient.submitAssignment(jobId, {
        selectedVendorId,
        overrideReasonCode: isOverride ? (reasonCode as OverrideReasonCode) : undefined,
        note: isOverride && note.trim() ? note.trim() : undefined,
      });
      onDecided(response, isOverride, isOverride ? (reasonCode as OverrideReasonCode) : undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to submit the decision. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
      <h3 className="text-sm font-semibold text-slate-800">Dispatch decision</h3>
      <p className="mt-1 text-xs text-slate-500">
        {isOverride ? (
          <>
            Overriding the AI recommendation to assign <strong className="text-slate-700">{selectedName}</strong>. A reason code
            is required.
          </>
        ) : (
          <>
            Accepting the AI top pick: <strong className="text-slate-700">{selectedName}</strong>.
          </>
        )}
      </p>

      {isOverride && (
        <div className="mt-4 space-y-3">
          <div>
            <label htmlFor="reasonCode" className="block text-xs font-medium text-slate-600">
              Override reason <span className="text-rose-500">*</span>
            </label>
            <select
              id="reasonCode"
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value as OverrideReasonCode)}
              className={`mt-1 w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-violet-300 ${
                touched && reasonMissing ? "border-rose-400" : "border-slate-300"
              }`}
            >
              <option value="" disabled>
                Select a reason…
              </option>
              {REASON_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {touched && reasonMissing && <p className="mt-1 text-xs text-rose-500">A reason code is required to override.</p>}
          </div>
          <div>
            <label htmlFor="note" className="block text-xs font-medium text-slate-600">
              Note <span className="text-slate-400">(optional)</span>
            </label>
            <textarea
              id="note"
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add context for the record…"
              className="mt-1 w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-300"
            />
          </div>
        </div>
      )}

      {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-600">{error}</p>}

      <div className="mt-4">
        <Button onClick={handleSubmit} loading={submitting} className="w-full" variant={isOverride ? "secondary" : "primary"}>
          {isOverride ? "Confirm override & assign" : "Accept recommendation & assign"}
        </Button>
      </div>
    </div>
  );
}
