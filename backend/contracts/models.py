"""
Canonical data contracts for RetailFixIt Part 2.

Field names match part1-architecture.md / part1-summary.md exactly:
JobEvent, VendorProfile, ScoreFactors, with binding / candidateSummary /
ranked[] / factors[]. These Pydantic models double as the published
contracts consumed by the frontend and emitted onto the event bus -
do not rename fields here without updating contracts/examples/*.json.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# ---------------------------------------------------------------------------
# JobEvent
# ---------------------------------------------------------------------------

class GeoPoint(ORMBase):
    lat: float
    lon: float


class TradeCategory(str, Enum):
    HVAC = "HVAC"
    PLUMBING = "PLUMBING"
    ELECTRICAL = "ELECTRICAL"
    REFRIGERATION = "REFRIGERATION"
    ELEVATOR = "ELEVATOR"


class SiteInfo(ORMBase):
    siteId: str
    geo: GeoPoint
    addressRef: str
    timezone: str


class JobDetails(ORMBase):
    tradeCategory: TradeCategory
    priority: str  # P1 | P2 | P3
    requiresCertification: list[str] = []
    requiresEquipment: list[str] = []
    estimatedLabourHours: float
    notToExceedUsd: float
    isRecall: bool = False


class SlaInfo(ORMBase):
    responseDueUtc: str
    resolutionDueUtc: str
    sensitivity: str  # ROUTINE | ELEVATED | CRITICAL
    breachPenaltyUsd: float = 0.0


class RiskInfo(ORMBase):
    riskTier: str  # LOW | MEDIUM | HIGH
    safetyRisk: bool = False
    revenueAtRiskUsd: float = 0.0


class DispatchInfo(ORMBase):
    excludedVendorIds: list[str] = []
    allowAutoAssign: bool = True


class JobEventData(ORMBase):
    customerId: str
    accountTier: str
    site: SiteInfo
    job: JobDetails
    sla: SlaInfo
    risk: RiskInfo
    dispatch: DispatchInfo


class JobEvent(ORMBase):
    """CloudEvents-shaped envelope. `type` distinguishes lifecycle stage
    (job.created.v1, job.assigned.v1, job.completed.v1, ...)."""
    type: str = "job.created.v1"
    jobId: str
    correlationId: str
    occurredAtUtc: str
    data: JobEventData


# ---------------------------------------------------------------------------
# VendorProfile
# ---------------------------------------------------------------------------

class CertificationRef(ORMBase):
    code: str
    expiresOn: str


class ComplianceInfo(ORMBase):
    insuranceValidUntil: str
    certifications: list[CertificationRef] = []
    isCompliant: bool


class CapabilitiesInfo(ORMBase):
    tradeCategories: list[TradeCategory]
    equipment: list[str] = []
    supportsAfterHours: bool = False
    maxConcurrentJobs: int


class CoverageInfo(ORMBase):
    postalCodes: list[str]
    homeBaseGeo: GeoPoint
    maxTravelKm: float


class CapacityInfo(ORMBase):
    asOfUtc: str
    openJobs: int
    utilizationPct: float
    acceptingNewWork: bool


class PerformanceInfo(ORMBase):
    windowDays: int
    jobsCompleted: int
    slaHitRate: float
    firstTimeFixRate: float
    acceptanceRate: float
    avgResponseMinutes: float
    reworkRate: float
    costIndex: float
    csat: float
    dataSufficiency: str  # COLD_START | SPARSE | SUFFICIENT


class CommercialInfo(ORMBase):
    standardHourlyUsd: float
    afterHoursHourlyUsd: float


class VendorProfile(ORMBase):
    vendorId: str
    displayName: str
    status: str  # ACTIVE | SUSPENDED | INACTIVE
    tier: str  # PREFERRED | STANDARD | PROBATIONARY
    tenureDays: int
    onProbation: bool = False
    compliance: ComplianceInfo
    capabilities: CapabilitiesInfo
    coverage: CoverageInfo
    capacity: CapacityInfo
    performance: PerformanceInfo
    commercial: CommercialInfo


# ---------------------------------------------------------------------------
# ScoreFactors
# ---------------------------------------------------------------------------

class ScoringMode(str, Enum):
    RULES_ONLY = "RULES_ONLY"
    RULES_PLUS_ML = "RULES_PLUS_ML"
    SHADOW = "SHADOW"


class ConfidenceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class OverrideReasonCode(str, Enum):
    CUSTOMER_RELATIONSHIP = "CUSTOMER_RELATIONSHIP"
    LOCAL_KNOWLEDGE = "LOCAL_KNOWLEDGE"
    CAPACITY_DATA_WRONG = "CAPACITY_DATA_WRONG"
    PRIOR_QUALITY_ISSUE = "PRIOR_QUALITY_ISSUE"
    MODEL_DISAGREE_OTHER = "MODEL_DISAGREE_OTHER"


class AssignmentSource(str, Enum):
    AUTO = "AUTO"
    DISPATCHER_ACCEPT = "DISPATCHER_ACCEPT"
    DISPATCHER_OVERRIDE = "DISPATCHER_OVERRIDE"


class Binding(ORMBase):
    rulesetVersion: str
    modelName: Optional[str] = None
    modelVersion: Optional[str] = None
    scoringMode: str
    mlTrustFactor: float
    degradedReason: Optional[str] = None


class CandidateSummary(ORMBase):
    vendorsInNetwork: int
    afterHardFilter: int
    exclusions: dict[str, int] = {}


class PredictionValue(ORMBase):
    value: float
    ci90: Optional[list[float]] = None


class CostPrediction(ORMBase):
    p50: float
    p90: float


class Predictions(ORMBase):
    pSlaMet: PredictionValue
    pFirstTimeFix: PredictionValue
    pAcceptWithin15m: PredictionValue
    expectedCostUsd: CostPrediction


class Factor(ORMBase):
    id: str
    source: str  # ML | RULE
    shap: Optional[float] = None
    ruleId: Optional[str] = None
    contributionPct: float
    raw: Optional[float] = None
    evidence: str


class Rationale(ORMBase):
    template: str
    narrative: Optional[str] = None
    source: str  # TEMPLATE | LLM
    groundednessCheck: Optional[str] = None  # PASSED | FAILED | SKIPPED
    fallbackUsed: bool = False


class RankedVendor(ORMBase):
    rank: int
    vendorId: str
    finalScore: float
    ruleScore: float
    mlScore: Optional[float] = None
    confidence: float
    confidenceBand: str
    predictions: Predictions
    factors: list[Factor]
    counterfactual: Optional[str] = None
    rationale: Rationale
    automationEligible: bool
    blockingGates: list[str] = []


class ScoreFactors(ORMBase):
    scoringRunId: str
    jobId: str
    generatedAtUtc: str
    latencyMs: float
    binding: Binding
    candidateSummary: CandidateSummary
    ranked: list[RankedVendor]
    featureSnapshotUri: Optional[str] = None


# ---------------------------------------------------------------------------
# Event envelopes for the job-lifecycle topic
# ---------------------------------------------------------------------------

class EventEnvelope(ORMBase):

    type: str
    jobId: str
    sessionId: str
    correlationId: str
    occurredAtUtc: str
    data: dict[str, Any]


class AssignmentRequest(ORMBase):
    selectedVendorId: str
    overrideReasonCode: Optional[OverrideReasonCode] = None
    note: Optional[str] = None


class JobCreateRequest(ORMBase):
    """POST /jobs request body. jobId/correlationId/occurredAtUtc are
    auto-generated by the server when omitted."""
    jobId: Optional[str] = None
    correlationId: Optional[str] = None
    occurredAtUtc: Optional[str] = None
    data: JobEventData


class JobCompletionRequest(ORMBase):
    """POST /jobs/{jobId}/completion request body - closes the loop for
    ml/build_training_set.py."""
    vendorId: str
    slaMet: bool
    firstTimeFix: bool
    acceptedWithin15m: bool
    actualCostUsd: float


# ---------------------------------------------------------------------------
# HTTP response models - named purely so contracts/build_openapi.py can emit
# real $refs instead of empty schemas; these mirror the plain dicts
# api/http_bp.py and orchestrator/saga_bp.py actually return.
# ---------------------------------------------------------------------------

class JobCreateResponse(ORMBase):
    jobId: str
    correlationId: str
    status: str
    scoringRunId: Optional[str] = None


class JobListItem(ORMBase):
    jobId: str
    type: str
    correlationId: str
    occurredAtUtc: str
    status: str


class AssignmentResponse(ORMBase):
    jobId: str
    correlationId: str
    selectedVendorId: str
    overrideReasonCode: Optional[OverrideReasonCode] = None
    note: Optional[str] = None
    assignmentSource: AssignmentSource
    assignedAtUtc: str


class JobCompletionResponse(ORMBase):
    jobId: str
    recorded: bool


class AuditResponse(ORMBase):
    jobId: str
    job: JobEvent
    scoreFactors: Optional[ScoreFactors] = None
    assignment: Optional[AssignmentResponse] = None
    events: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []


class SeedResult(ORMBase):
    jobId: str
    dispatched: bool


class SeedResponse(ORMBase):
    seeded: list[SeedResult]


class DispatchResponse(ORMBase):
    jobId: str
    dispatched: bool


class VendorResponseBody(ORMBase):
    """POST /jobs/{jobId}/vendor-response request body - raises the saga's
    VendorResponse external event."""
    accepted: bool


class OrchestrationStatusResponse(ORMBase):
    jobId: str
    runtimeStatus: str
    customStatus: Optional[Any] = None
    createdTime: Optional[str] = None
    lastUpdatedTime: Optional[str] = None
    output: Optional[Any] = None
