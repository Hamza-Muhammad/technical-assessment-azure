import type { JobContextResponse } from "../types/contracts";
import autoEligible from "./job-demo-005-auto-eligible";
import manualReview from "./job-demo-002-manual-review";
import noEligibleVendors from "./job-demo-003-no-eligible-vendors";

export interface MockJobListing {
  jobId: string;
  label: string;
  description: string;
  data: JobContextResponse;
}

/**
 * Registry of demo jobs, standing in for whatever upstream queue/list hands the
 * dispatcher a jobId to open. jobIds intentionally match
 * `part2-dispatch-ai/backend/data/jobs.json`'s JOB-DEMO-* seed data (and its `_scenario`
 * annotations) so the same three scenarios line up once VITE_USE_MOCKS=false points at
 * the real backend, instead of two disconnected sets of demo data.
 */
export const MOCK_JOBS: MockJobListing[] = [
  {
    jobId: autoEligible.job.jobId,
    label: "JOB-DEMO-005 — Refrigeration, recall",
    description: "Happy path: high-confidence top pick, all automation gates pass.",
    data: autoEligible,
  },
  {
    jobId: manualReview.job.jobId,
    label: "JOB-DEMO-002 — HVAC, P1 emergency",
    description: "High risk/SLA-critical/safety gates + degraded ML endpoint: routed to manual review.",
    data: manualReview,
  },
  {
    jobId: noEligibleVendors.job.jobId,
    label: "JOB-DEMO-003 — HVAC, P2",
    description: "Eligible HVAC vendors: recommendation and dispatcher-review path.",
    data: noEligibleVendors,
  },
];

export function findMockJob(jobId: string): MockJobListing | undefined {
  return MOCK_JOBS.find((j) => j.jobId === jobId);
}
