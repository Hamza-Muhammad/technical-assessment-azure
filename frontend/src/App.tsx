import { useCallback, useEffect, useState } from "react";
import type { AssignmentResponse, JobContextResponse, OverrideReasonCode } from "./types/contracts";
import { apiClient } from "./api/client";
import { JobSummaryCard } from "./components/JobSummaryCard";
import { VendorList } from "./components/VendorList";
import { RationaleDetail } from "./components/RationaleDetail";
import { DecisionPanel } from "./components/DecisionPanel";
import { ConfirmationBanner } from "./components/ConfirmationBanner";
import { AutomationGateStatus } from "./components/AutomationGateStatus";
import { ScoringMeta } from "./components/ScoringMeta";
import { LowConfidenceNotice } from "./components/LowConfidenceNotice";
import { NoEligibleVendors } from "./components/NoEligibleVendors";
import { ErrorBanner } from "./components/ErrorBanner";
import { CreateJobModal } from "./components/CreateJobModal";
import { Button } from "./components/ui/Button";
import { AuditTrail } from "./components/AuditTrail";

interface Decision {
  response: AssignmentResponse;
  isOverride: boolean;
  reasonCode?: OverrideReasonCode;
}

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [context, setContext] = useState<JobContextResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVendorId, setSelectedVendorId] = useState<string>("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [vendorResponse, setVendorResponse] = useState<boolean | null>(null);
  const [vendorResponding, setVendorResponding] = useState(false);
  const [vendorError, setVendorError] = useState<string | null>(null);

  const load = useCallback((id: string) => {
    setLoading(true);
    setError(null);
    setDecision(null);
    setVendorResponse(null);
    setVendorError(null);
    apiClient
      .getJobContext(id)
      .then((data) => {
        setContext(data);
        setSelectedVendorId(data.scoreFactors.ranked[0]?.vendorId ?? "");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Something went wrong."))
      .finally(() => setLoading(false));
  }, []);

  async function respondToVendor(accepted: boolean) {
    if (!jobId) return;
    setVendorResponding(true);
    setVendorError(null);
    try {
      await apiClient.submitVendorResponse(jobId, accepted);
      setVendorResponse(accepted);
    } catch (cause) {
      setVendorError(cause instanceof Error ? cause.message : "Could not send the vendor response.");
    } finally {
      setVendorResponding(false);
    }
  }

  useEffect(() => {
    if (jobId) load(jobId);
  }, [jobId, load]);

  const topCandidate = context?.scoreFactors.ranked[0];
  const selectedCandidate = context?.scoreFactors.ranked.find((c) => c.vendorId === selectedVendorId);
  const needsReview = topCandidate ? !topCandidate.automationEligible || topCandidate.confidenceBand === "LOW" : false;

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-violet-500">RetailFixIt</p>
            <h1 className="text-lg font-bold text-slate-900">Dispatch Console</h1>
          </div>
          <div>
            <button type="button" onClick={() => setCreateOpen(true)} className="rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-700">
              Create job
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        {loading && jobId && (
          <section className="flex min-h-[32rem] items-center justify-center rounded-2xl border border-violet-200 bg-white px-6 py-16 text-center" aria-busy="true">
            <div className="max-w-lg">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-100 text-violet-600">
                <svg className="h-8 w-8 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <circle className="opacity-25" cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" />
                  <path className="opacity-90" fill="currentColor" d="M21 12a9 9 0 0 1-9 9v-3a6 6 0 0 0 6-6h3Z" />
                </svg>
              </div>
              <p className="mt-6 text-[11px] font-semibold uppercase tracking-widest text-violet-500">Azure Durable workflow</p>
              <h2 className="mt-2 text-xl font-bold text-slate-900">Scoring your job</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Job <span className="font-mono text-slate-700">{jobId}</span> was submitted successfully. Azure is finding eligible vendors and generating the recommendation.</p>
              <div className="mx-auto mt-6 max-w-sm rounded-xl bg-slate-50 p-4 text-left text-xs text-slate-600">
                <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Job accepted</div>
                <div className="mt-2 flex items-center gap-2"><span className="h-2 w-2 animate-pulse rounded-full bg-violet-500" /> Waiting for recommendation</div>
                <div className="mt-2 flex items-center gap-2 text-slate-400"><span className="h-2 w-2 rounded-full bg-slate-300" /> Vendor decision follows</div>
              </div>
            </div>
          </section>
        )}

        {!loading && error && <ErrorBanner message={error} onRetry={() => jobId && load(jobId)} />}

        {!loading && !error && !context && (
          <section className="flex min-h-[32rem] items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
            <div className="max-w-md">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50 text-2xl text-violet-600">+</div>
              <h2 className="mt-5 text-xl font-bold text-slate-900">Create a dispatch job</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Start with one of the prepared job templates or enter a new job. Recommendations will appear here after Azure finishes scoring.</p>
              <Button className="mt-6" onClick={() => setCreateOpen(true)}>Create job</Button>
            </div>
          </section>
        )}

        {!loading && !error && context && (
          <>
            <JobSummaryCard job={context.job} />

            {context.scoreFactors.ranked.length === 0 ? (
              <NoEligibleVendors scoreFactors={context.scoreFactors} />
            ) : (
              <>
                <section className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="text-sm font-semibold text-slate-800">AI Recommendation</h2>
                    {topCandidate && <AutomationGateStatus topCandidate={topCandidate} topVendor={context.vendors[topCandidate.vendorId]} />}
                  </div>
                  <div className="mt-2">
                    <ScoringMeta scoreFactors={context.scoreFactors} />
                  </div>
                </section>

                {needsReview && topCandidate && <LowConfidenceNotice topCandidate={topCandidate} />}

                {decision && (
                  <ConfirmationBanner
                    response={decision.response}
                    isOverride={decision.isOverride}
                    reasonCode={decision.reasonCode}
                    vendors={context.vendors}
                    onDismiss={() => setDecision(null)}
                  />
                )}

                <AuditTrail jobId={jobId} refreshKey={String(vendorResponse ?? decision?.response.assignedAtUtc ?? "initial")} />

                {decision && (
                  <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <h2 className="text-sm font-semibold text-emerald-950">Vendor response</h2>
                        <p className="mt-1 text-xs text-emerald-800">
                          Simulate the selected vendor accepting or declining the assignment.
                        </p>
                      </div>
                      {vendorResponse === null ? (
                        <div className="flex gap-2">
                          <Button onClick={() => respondToVendor(true)} loading={vendorResponding}>Vendor accepts</Button>
                          <Button onClick={() => respondToVendor(false)} loading={vendorResponding} variant="secondary">Vendor declines</Button>
                        </div>
                      ) : (
                        <span className="rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-emerald-800">
                          {vendorResponse ? "Accepted" : "Declined"}
                        </span>
                      )}
                    </div>
                    {vendorError && <p className="mt-3 text-xs text-rose-700">{vendorError}</p>}
                  </section>
                )}

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
                  <div className="lg:col-span-2">
                    <VendorList
                      ranked={context.scoreFactors.ranked}
                      vendors={context.vendors}
                      selectedVendorId={selectedVendorId}
                      onSelect={setSelectedVendorId}
                    />
                  </div>

                  <div className="space-y-5 lg:col-span-3">
                    <div className="rounded-2xl border border-slate-200 bg-white p-6">
                      {selectedCandidate && (
                        <RationaleDetail candidate={selectedCandidate} vendor={context.vendors[selectedCandidate.vendorId]} />
                      )}
                    </div>

                    {!decision && topCandidate && selectedCandidate && (
                      <DecisionPanel
                        jobId={jobId}
                        recommendedVendorId={topCandidate.vendorId}
                        selectedVendorId={selectedCandidate.vendorId}
                        vendors={context.vendors}
                        onDecided={(response, isOverride, reasonCode) => setDecision({ response, isOverride, reasonCode })}
                      />
                    )}
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </main>
      {createOpen && <CreateJobModal onClose={() => setCreateOpen(false)} onCreated={(createdJobId) => { setCreateOpen(false); setContext(null); setError(null); setLoading(true); setJobId(createdJobId); }} />}
    </div>
  );
}
