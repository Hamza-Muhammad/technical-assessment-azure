/**
 * Canonical data contracts for RetailFixIt Part 2.
 *
 * Aligned directly against the backend's authoritative Pydantic models in
 * `part2-dispatch-ai/backend/contracts/models.py` (field names, nesting, casing, and enum
 * value sets all confirmed there — read directly, not guessed, since the backend agent's
 * work landed in the same repo mid-build). Where `domain/gates.py`, `domain/rationale.py`,
 * or `domain/factors.py` fix a concrete vocabulary (gate codes, factor ids, groundedness
 * states), that vocabulary is cited inline too.
 *
 * Anywhere the backend has genuinely not yet defined a shape (no HTTP layer exists yet —
 * only domain logic, contracts, and an in-memory event bus), it's marked "FE ASSUMPTION"
 * with a short rationale, per the task brief's "note it clearly rather than silently add
 * it" instruction. These are real gaps, not laziness — reconcile with the backend agent
 * before wiring VITE_USE_MOCKS=false against them.
 */

// ---------------------------------------------------------------------------
// Shared / enum-like unions — confirmed against backend/contracts/models.py
// ---------------------------------------------------------------------------

/** backend/data/jobs.json — P1 (most urgent) .. P3. */
export type JobPriority = "P1" | "P2" | "P3";

export type TradeCategory = "HVAC" | "PLUMBING" | "ELECTRICAL" | "REFRIGERATION" | "ELEVATOR";

/** backend/contracts/models.py RiskInfo.riskTier comment. */
export type RiskTier = "LOW" | "MEDIUM" | "HIGH";

/** backend/contracts/models.py SlaInfo.sensitivity comment. */
export type SlaSensitivity = "ROUTINE" | "ELEVATED" | "CRITICAL";

/** backend/contracts/models.py VendorProfile.tier comment. */
export type VendorTier = "PREFERRED" | "STANDARD" | "PROBATIONARY";

/** backend/contracts/models.py VendorProfile.status comment. */
export type VendorStatus = "ACTIVE" | "SUSPENDED" | "INACTIVE";

/** Documented explicitly in part1-summary.md; confirmed in backend/domain/factors.py SUFFICIENCY_LABELS. */
export type DataSufficiency = "COLD_START" | "SPARSE" | "SUFFICIENT";

/** backend/contracts/models.py ScoringMode(str, Enum). */
export type ScoringMode = "RULES_ONLY" | "RULES_PLUS_ML" | "SHADOW";

/** backend/contracts/models.py ConfidenceBand(str, Enum). */
export type ConfidenceBand = "HIGH" | "MEDIUM" | "LOW";


export type OverrideReasonCode =
  | "CUSTOMER_RELATIONSHIP"
  | "LOCAL_KNOWLEDGE"
  | "CAPACITY_DATA_WRONG"
  | "PRIOR_QUALITY_ISSUE"
  | "MODEL_DISAGREE_OTHER";

/**
 * backend/domain/gates.py evaluate_gates() — deliberately simplified to exactly two
 * checks for this demo build (down from Part 1's fuller 7-check design): every gate
 * must pass for automationEligible. Kept as `string` at the type level (open set,
 * don't want a backend-side new gate code to fail TS compilation) but this is the
 * authoritative vocabulary the UI is designed against, not a guess.
 */
export type BlockingGateCode =
  | "RISK_TIER_HIGH"
  | "LOW_CONFIDENCE"
  | (string & {});

// ---------------------------------------------------------------------------
// JobEvent — CloudEvents-shaped envelope (backend/contracts/models.py JobEvent).
// `type` distinguishes lifecycle stage (job.created.v1, job.assigned.v1, ...);
// the actual job payload lives under `data`, not at the top level.
// ---------------------------------------------------------------------------

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface JobEventData {
  customerId: string;
  accountTier: string;
  site: {
    siteId: string;
    geo: GeoPoint;
    /**
     * A PII-redaction token (e.g. "pii://address/2c7e44a9"), NOT a resolved street
     * address — confirmed in backend/data/jobs.json. Consistent with Part 1's PII
     * design ("full site address released to a vendor only after they accept"). The
     * UI must not render this as if it were a human address; `siteId` is the primary
     * location label, `addressRef` is shown only as a small reference token.
     */
    addressRef: string;
    timezone: string;
  };
  job: {
    tradeCategory: TradeCategory;
    priority: JobPriority;
    requiresCertification: string[];
    requiresEquipment: string[];
    estimatedLabourHours: number;
    notToExceedUsd: number;
    isRecall: boolean;
  };
  sla: {
    responseDueUtc: string;
    resolutionDueUtc: string;
    sensitivity: SlaSensitivity;
    breachPenaltyUsd: number;
  };
  risk: {
    riskTier: RiskTier;
    safetyRisk: boolean;
    revenueAtRiskUsd: number;
  };
  dispatch: {
    excludedVendorIds: string[];
    allowAutoAssign: boolean;
  };
}

export interface JobEvent {
  type: string;
  jobId: string;
  correlationId: string;
  occurredAtUtc: string;
  data: JobEventData;
}

// ---------------------------------------------------------------------------
// VendorProfile
// ---------------------------------------------------------------------------

export interface CertificationRef {
  code: string;
  expiresOn: string;
}

export interface VendorProfile {
  vendorId: string;
  displayName: string;
  status: VendorStatus;
  tier: VendorTier;
  tenureDays: number;
  onProbation: boolean;
  compliance: {
    insuranceValidUntil: string;
    certifications: CertificationRef[];
    isCompliant: boolean;
  };
  capabilities: {
    tradeCategories: TradeCategory[];
    equipment: string[];
    supportsAfterHours: boolean;
    maxConcurrentJobs: number;
  };
  coverage: {
    postalCodes: string[];
    homeBaseGeo: GeoPoint;
    maxTravelKm: number;
  };
  capacity: {
    asOfUtc: string;
    openJobs: number;
    utilizationPct: number;
    acceptingNewWork: boolean;
  };
  performance: {
    windowDays: number;
    jobsCompleted: number;
    slaHitRate: number;
    firstTimeFixRate: number;
    acceptanceRate: number;
    avgResponseMinutes: number;
    reworkRate: number;
    costIndex: number;
    csat: number;
    dataSufficiency: DataSufficiency;
  };
  commercial: {
    standardHourlyUsd: number;
    afterHoursHourlyUsd: number;
  };
}

// ---------------------------------------------------------------------------
// ScoreFactors
// ---------------------------------------------------------------------------

export interface PredictionValue {
  value: number;
  ci90?: [number, number] | null;
}

export interface CostPrediction {
  p50: number;
  p90: number;
}

/**
 * backend/domain/factor_builder.py + domain/factors.py FACTOR_DEFS — `id` is one of
 * SLA_HISTORY / PROXIMITY / FIRST_TIME_FIX / COST_INDEX / CURRENT_LOAD / VENDOR_TIER /
 * REWORK_RATE / CUSTOMER_SATISFACTION / RESPONSE_TIME / ACCEPTANCE_RATE /
 * SLA_TIME_PRESSURE / AFTER_HOURS / RECALL_JOB / DATA_SUFFICIENCY (open string at the
 * type level — new factor ids shouldn't fail compilation).
 */
export interface ScoreFactor {
  id: string;
  source: "RULE" | "ML" | string;
  /** Only populated for ML-sourced factors (TreeSHAP value, display-scaled). */
  shap?: number | null;
  /** Only populated for RULE-sourced factors, e.g. "R-GUARD-011". */
  ruleId?: string | null;
  /** Share of total contribution, normalized so |values| sum to 100 — can be negative. */
  contributionPct: number;
  raw?: number | null;
  /** Deterministic, data-grounded human-readable evidence string (never LLM-invented). */
  evidence: string;
}

export interface RationaleBlock {
  /** Always populated — zero-dependency deterministic fallback (domain/rationale.py build_template). */
  template: string;
  /** Only populated when source is "LLM"; null/undefined whenever the template path was used. */
  narrative?: string | null;
  source: "LLM" | "TEMPLATE";
  /** "SKIPPED" when LLM narration is disabled (the deployed default) or wasn't attempted. */
  groundednessCheck: "PASSED" | "FAILED" | "SKIPPED";
  fallbackUsed: boolean;
}

export interface RankedCandidate {
  rank: number;
  vendorId: string;
  finalScore: number;
  ruleScore: number;
  /** null in RULES_ONLY / ML-fallback runs — mlTrustFactor treated as 0, not computed. */
  mlScore?: number | null;
  confidence: number;
  confidenceBand: ConfidenceBand;
  predictions: {
    pSlaMet: PredictionValue;
    pFirstTimeFix: PredictionValue;
    pAcceptWithin15m: PredictionValue;
    expectedCostUsd: CostPrediction;
  };
  factors: ScoreFactor[];
 
  counterfactual?: string | null;
  rationale: RationaleBlock;
  automationEligible: boolean;
  blockingGates: BlockingGateCode[];
}

export interface ScoreFactors {
  scoringRunId: string;
  jobId: string;
  generatedAtUtc: string;
  latencyMs: number;
  binding: {
    rulesetVersion: string;
    modelName?: string | null;
    modelVersion?: string | null;
    scoringMode: ScoringMode;
    mlTrustFactor: number;
    degradedReason?: string | null;
  };
  candidateSummary: {
    vendorsInNetwork: number;
    afterHardFilter: number;
    /** reason-code (e.g. "TRADE_MISMATCH", "NOT_COMPLIANT", "EQUIPMENT_MISSING") -> count of
     * vendors excluded for that reason — confirmed against backend/contracts/examples/*.json. */
    exclusions: Record<string, number>;
  };
  ranked: RankedCandidate[];
  featureSnapshotUri?: string | null;
}

// ---------------------------------------------------------------------------
// Real, running HTTP contract — verified directly against
// `backend/api/http_bp.py` (Azure Functions HTTP triggers, CORS configured in
// `backend/infra/main.bicep` for :5173/:3000),
// `backend/contracts/openapi.json`, and the generated examples in
// `backend/contracts/examples/*.json`. The backend resolved the job/vendor-context
// gap flagged in an earlier pass via option (b): separate GET /jobs/{jobId} and
// GET /vendors endpoints, not embedding — `apiClient.getJobContext` below fetches all
// three (job, recommendation, vendors) in parallel and assembles them client-side.
// ---------------------------------------------------------------------------

/** GET /jobs list-item shape — job envelope fields minus `data`, plus a derived `status`. */
export type JobStatus = "UNSCORED" | "NO_ELIGIBLE_VENDORS" | "PENDING_REVIEW" | "AUTO_ASSIGNED" | "ASSIGNED";

export interface JobListItem {
  jobId: string;
  type: string;
  correlationId: string;
  occurredAtUtc: string;
  status: JobStatus;
}

/**
 * POST /jobs response (backend/api/http_bp.py create_job). `scoringRunId` is always
 * null at creation time now — scoring happens asynchronously (the Durable saga consumes
 * JobCreated and scores it as an activity), not in the same request/response cycle.
 */
export interface JobCreateResponse {
  jobId: string;
  correlationId: string;
  status: JobStatus;
  scoringRunId?: string | null;
}

/**
 * Assembled client-side from three real, separate backend calls — GET /jobs/{jobId},
 * GET /jobs/{jobId}/recommendation, and GET /vendors — run in parallel by
 * `apiClient.getJobContext`. Not a single backend response shape.
 */
export interface JobContextResponse {
  job: JobEvent;
  vendors: Record<string, VendorProfile>;
  scoreFactors: ScoreFactors;
}

/** Real backend model — backend/contracts/models.py AssignmentRequest. */
export interface AssignmentRequest {
  selectedVendorId: string;
  overrideReasonCode?: OverrideReasonCode;
  note?: string;
}

export type AssignmentSource = "AUTO" | "DISPATCHER_ACCEPT" | "DISPATCHER_OVERRIDE";

/**
 * Real response — backend/api/http_bp.py `create_assignment` returns the assignment record
 * verbatim (also what's persisted to `state.assignments` and logged to
 * `decisions.jsonl`). Note there is no `assignmentId`/`status` field — the vendor is
 * named `selectedVendorId` (not `assignedVendorId`), and `assignmentSource` is the
 * three-way AUTO / DISPATCHER_ACCEPT / DISPATCHER_OVERRIDE distinction, not a status enum.
 */
export interface AssignmentResponse {
  jobId: string;
  correlationId: string;
  selectedVendorId: string;
  overrideReasonCode: OverrideReasonCode | null;
  note: string | null;
  assignmentSource: AssignmentSource;
  assignedAtUtc: string;
}

/** One line from backend/audit.py's events.jsonl — the raw event envelope, as published. */
export interface AuditEventLogEntry {
  loggedAtUtc: string;
  correlationId: string;
  jobId: string;
  scoringRunId: string | null;
  event: {
    type: string;
    jobId: string;
    sessionId: string;
    correlationId: string;
    occurredAtUtc: string;
    data: Record<string, unknown>;
    messageId: string;
  };
}

/** One line from backend/audit.py's decisions.jsonl. */
export interface AuditDecisionLogEntry {
  loggedAtUtc: string;
  correlationId: string;
  jobId: string;
  scoringRunId: string | null;
  decision: AssignmentResponse;
}

/**
 * Real response — backend/api/http_bp.py `get_audit`. Richer than a flat entry list: the
 * full job + scoreFactors + current assignment (if any) plus the raw events/decisions
 * JSONL slices for this jobId.
 */
export interface AuditResponse {
  jobId: string;
  job: JobEvent;
  scoreFactors: ScoreFactors | null;
  assignment: AssignmentResponse | null;
  events: AuditEventLogEntry[];
  decisions: AuditDecisionLogEntry[];
}

/** POST /jobs/{jobId}/completion body — closes the loop for build_training_set.py. Not
 * wired to any UI action in this screen (out of scope — see README scope cuts). */
export interface JobCompletionRequest {
  vendorId: string;
  slaMet: boolean;
  firstTimeFix: boolean;
  acceptedWithin15m: boolean;
  actualCostUsd: number;
}

export interface JobCompletionResponse {
  jobId: string;
  recorded: true;
}
