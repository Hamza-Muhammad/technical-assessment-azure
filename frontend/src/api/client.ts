import type {
  AssignmentRequest,
  AssignmentResponse,
  AuditResponse,
  JobCompletionRequest,
  JobCompletionResponse,
  JobContextResponse,
  JobCreateResponse,
  JobEvent,
  JobEventData,
  JobListItem,
  ScoreFactors,
  VendorProfile,
} from "../types/contracts";
import { findMockJob, MOCK_JOBS } from "../mocks";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:7071/api";

function delay<T>(value: T, ms = 450): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

async function httpJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    const error = new Error(`${res.status} ${res.statusText}${body ? ` — ${body}` : ""}`);
    (error as Error & { status?: number }).status = res.status;
    throw error;
  }
  return res.json() as Promise<T>;
}

/**
 * Real, running HTTP contract (Azure Functions HTTP triggers, `backend/api/http_bp.py`,
 * verified against `backend/contracts/openapi.json` + `backend/contracts/examples/*.json`):
 *   POST   /jobs                       -> JobCreateResponse
 *   GET    /jobs                       -> JobListItem[]
 *   GET    /jobs/{jobId}               -> JobEvent
 *   GET    /jobs/{jobId}/recommendation -> ScoreFactors (bare — no embedded job/vendors)
 *   POST   /jobs/{jobId}/assignment    -> AssignmentResponse
 *   POST   /jobs/{jobId}/completion    -> JobCompletionResponse
 *   GET    /jobs/{jobId}/audit         -> AuditResponse
 *   GET    /vendors                    -> VendorProfile[]
 *
 * The backend resolved the earlier "no job/vendor-context endpoint" gap via separate
 * GET /jobs/{jobId} and GET /vendors endpoints (not embedding them in the recommendation
 * response) — `getJobContext` below fetches all three in parallel and assembles them
 * client-side, matching that real shape.
 */
export const apiClient = {
  /**
   * POST /jobs — creates a job and publishes JobCreated; scoring happens asynchronously
   * (the Durable saga consumes it and scores as an activity), so the response's
   * `status` is always "UNSCORED" and `scoringRunId` is always null (backend/api/http_bp.py
   * create_job). Not exercised by the Dispatcher Console's primary flow: per the Part 1
   * architecture, jobs are created by the Customer-facing Intake API, not the dispatcher,
   * which only opens already-created jobs.
   */
  async createJob(body: { jobId?: string; correlationId?: string; occurredAtUtc?: string; data: JobEventData }): Promise<JobCreateResponse> {
    if (USE_MOCKS) {
      const jobId = body.jobId ?? `JOB-${Math.floor(Math.random() * 900000 + 100000)}`;
      return delay({ jobId, correlationId: body.correlationId ?? `corr-${jobId}`, status: "UNSCORED", scoringRunId: null }, 300);
    }
    return httpJson<JobCreateResponse>("/jobs", { method: "POST", body: JSON.stringify(body) });
  },

  /** GET /jobs — list of known jobs with a derived status. Not wired to any UI action in
   * this screen (the "Sample job" switcher uses the committed mock registry instead) —
   * available for a future "open a job from a queue" screen. */
  async listJobs(): Promise<JobListItem[]> {
    if (USE_MOCKS) {
      return delay(
        MOCK_JOBS.map((m) => ({
          jobId: m.jobId,
          type: m.data.job.type,
          correlationId: m.data.job.correlationId,
          occurredAtUtc: m.data.job.occurredAtUtc,
          status: (m.data.scoreFactors.ranked.length === 0 ? "NO_ELIGIBLE_VENDORS" : "PENDING_REVIEW") as JobListItem["status"],
        })),
        300,
      );
    }
    return httpJson<JobListItem[]>("/jobs");
  },

  /** GET /jobs/{jobId} — the full JobEvent. */
  async getJob(jobId: string): Promise<JobEvent> {
    if (USE_MOCKS) {
      const mock = findMockJob(jobId);
      if (!mock) throw new Error(`No mock job found for jobId "${jobId}"`);
      return delay(mock.data.job, 250);
    }
    return httpJson<JobEvent>(`/jobs/${jobId}`);
  },

  /**
   * GET /jobs/{jobId}/recommendation — the ranked ScoreFactors for a job (bare, no
   * embedded context). Scoring now happens asynchronously (the Durable saga consumes
   * JobCreated and scores it as an activity after the job is created), so the first few
   * reads after creation will legitimately 404 for a few seconds — retried up to 5 times,
   * 1.5s apart, on a 404 specifically (not retried on other error codes).
   */
  async getRecommendation(jobId: string): Promise<ScoreFactors> {
    if (USE_MOCKS) {
      const mock = findMockJob(jobId);
      if (!mock) throw new Error(`No mock recommendation found for jobId "${jobId}"`);
      return delay(mock.data.scoreFactors, 550);
    }
    for (let attempt = 0; ; attempt++) {
      try {
        return await httpJson<ScoreFactors>(`/jobs/${jobId}/recommendation`);
      } catch (err) {
        const status = (err as Error & { status?: number }).status;
        if (status !== 404 || attempt >= 19) throw err;
        await delay(undefined, 1500);
      }
    }
  },

  /** Raises the Durable saga's VendorResponse external event. */
  async submitVendorResponse(jobId: string, accepted: boolean): Promise<void> {
    if (USE_MOCKS) {
      await delay(undefined, 350);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/vendor-response`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ accepted }),
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      const error = new Error(`${response.status} ${response.statusText}${body ? ` — ${body}` : ""}`);
      (error as Error & { status?: number }).status = response.status;
      throw error;
    }
  },

  /** GET /vendors — every vendor in the network (not scoped to one job's candidates). */
  async listVendors(): Promise<VendorProfile[]> {
    if (USE_MOCKS) {
      return delay(
        MOCK_JOBS.flatMap((m) => Object.values(m.data.vendors)),
        250,
      );
    }
    return httpJson<VendorProfile[]>("/vendors");
  },

  /**
   * POST /jobs/{jobId}/assignment — accept the top pick or submit a structured override.
   * Request body matches the real backend/contracts/models.py `AssignmentRequest`
   * (selectedVendorId + optional overrideReasonCode/note only — jobId is in the URL,
   * correlationId is resolved server-side). Response is the persisted assignment record
   * itself: `{ jobId, correlationId, selectedVendorId, overrideReasonCode, note,
   * assignmentSource, assignedAtUtc }` — note `assignmentSource`
   * (AUTO/DISPATCHER_ACCEPT/DISPATCHER_OVERRIDE), not a `status` field, and
   * `selectedVendorId`, not `assignedVendorId`.
   */
  async submitAssignment(jobId: string, payload: AssignmentRequest): Promise<AssignmentResponse> {
    if (USE_MOCKS) {
      const mock = findMockJob(jobId);
      const topVendorId = mock?.data.scoreFactors.ranked[0]?.vendorId;
      return delay(
        {
          jobId,
          correlationId: mock?.data.job.correlationId ?? `corr-${jobId}`,
          selectedVendorId: payload.selectedVendorId,
          overrideReasonCode: payload.overrideReasonCode ?? null,
          note: payload.note ?? null,
          assignmentSource: payload.selectedVendorId === topVendorId ? "DISPATCHER_ACCEPT" : "DISPATCHER_OVERRIDE",
          assignedAtUtc: new Date().toISOString(),
        },
        550,
      );
    }
    return httpJson<AssignmentResponse>(`/jobs/${jobId}/assignment`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * POST /jobs/{jobId}/completion — records a job outcome for the retraining loop
   * (ml/build_training_set.py). Not wired to any UI action in this screen (out of scope
   * — see README), implemented for contract completeness.
   */
  async completeJob(jobId: string, payload: JobCompletionRequest): Promise<JobCompletionResponse> {
    if (USE_MOCKS) {
      return delay({ jobId, recorded: true }, 300);
    }
    return httpJson<JobCompletionResponse>(`/jobs/${jobId}/completion`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * GET /jobs/{jobId}/audit — real shape is richer than a flat entry list: the job,
   * its ScoreFactors, the current assignment (if any), and raw events.jsonl/decisions.jsonl
   * slices for this jobId (backend/api/http_bp.py get_audit).
   */
  async getAudit(jobId: string): Promise<AuditResponse> {
    if (USE_MOCKS) {
      const mock = findMockJob(jobId);
      if (!mock) throw new Error(`No mock job found for jobId "${jobId}"`);
      const { job, scoreFactors } = mock.data;
      return delay(
        {
          jobId,
          job,
          scoreFactors,
          assignment: null,
          events: [
            {
              loggedAtUtc: job.occurredAtUtc,
              correlationId: job.correlationId,
              jobId,
              scoringRunId: null,
              event: {
                type: "job.created.v1",
                jobId,
                sessionId: jobId,
                correlationId: job.correlationId,
                occurredAtUtc: job.occurredAtUtc,
                data: job.data as unknown as Record<string, unknown>,
                messageId: `MSG-${jobId}-created`,
              },
            },
            {
              loggedAtUtc: scoreFactors.generatedAtUtc,
              correlationId: job.correlationId,
              jobId,
              scoringRunId: scoreFactors.scoringRunId,
              event: {
                type: "job.recommendation_generated.v1",
                jobId,
                sessionId: jobId,
                correlationId: job.correlationId,
                occurredAtUtc: scoreFactors.generatedAtUtc,
                data: { scoreFactors } as unknown as Record<string, unknown>,
                messageId: `MSG-${jobId}-recommendation`,
              },
            },
          ],
          decisions: [],
        },
        350,
      );
    }
    return httpJson<AuditResponse>(`/jobs/${jobId}/audit`);
  },

  /**
   * Assembled client-side from three real, separate endpoints — GET /jobs/{jobId},
   * GET /jobs/{jobId}/recommendation, GET /vendors — fetched in parallel. Not a single
   * backend response; see `JobContextResponse` in contracts.ts.
   */
  async getJobContext(jobId: string): Promise<JobContextResponse> {
    if (USE_MOCKS) {
      const mock = findMockJob(jobId);
      if (!mock) throw new Error(`No mock job found for jobId "${jobId}"`);
      return delay(mock.data, 550);
    }
    const [job, scoreFactors, allVendors] = await Promise.all([
      apiClient.getJob(jobId),
      apiClient.getRecommendation(jobId),
      apiClient.listVendors(),
    ]);
    const vendors: Record<string, VendorProfile> = {};
    for (const v of allVendors) vendors[v.vendorId] = v;
    return { job, scoreFactors, vendors };
  },
};

export const config = { USE_MOCKS, API_BASE_URL };
