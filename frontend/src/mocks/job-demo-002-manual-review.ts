import type { JobContextResponse } from "../types/contracts";
import { hoursFromNow } from "./relativeTime";

/**
 * Scenario: manual review required, mirroring backend/data/jobs.json JOB-DEMO-002 (job
 * payload verbatim) plus a degraded-ML scoring run layered on top:
 *  - High-risk P1 job (riskTier "HIGH", not "LOW") -> RISK_TIER_HIGH fires per the
 *    simplified two-check gate in backend/domain/gates.py, blocking automation
 *    regardless of how well the top candidate scores.
 *  - This scoring run also happened to hit a degraded ML endpoint (mlTrustFactor forced
 *    to 0, scoringMode falls back to RULES_ONLY, confidence stays LOW) -> LOW_CONFIDENCE
 *    fires too, and the LLM narration itself falls back to the deterministic template
 *    (rationale.groundednessCheck: "SKIPPED", fallbackUsed: true) — two independent
 *    fallback ladders from Part 1, exercised in one fixture.
 */
const fixture: JobContextResponse = {
  job: {
    type: "job.created.v1",
    jobId: "JOB-DEMO-002",
    correlationId: "01J8Z9K4M2QW3E5R7T9Y1U3I6P",
    occurredAtUtc: hoursFromNow(-0.5),
    data: {
      customerId: "CUST-000188500",
      accountTier: "ENTERPRISE",
      site: {
        siteId: "SITE-0043200",
        geo: { lat: 41.878, lon: -87.63 },
        addressRef: "pii://address/9f1a22b3",
        timezone: "America/Chicago",
      },
      job: {
        tradeCategory: "HVAC",        priority: "P1",
        requiresCertification: ["EPA_608_UNIVERSAL"],
        requiresEquipment: ["CRANE_LIFT"],
        estimatedLabourHours: 3.5,
        notToExceedUsd: 4500,
        isRecall: false,
      },
      sla: {
        responseDueUtc: hoursFromNow(3.5),
        resolutionDueUtc: hoursFromNow(20),
        sensitivity: "CRITICAL",
        breachPenaltyUsd: 2500,
      },
      risk: {
        riskTier: "HIGH",
        safetyRisk: true,
        revenueAtRiskUsd: 18000,
      },
      dispatch: {
        excludedVendorIds: ["VEN-00987"],
        allowAutoAssign: true,
      },
    },
  },
  vendors: {
    "VEN-00233": {
      vendorId: "VEN-00233",
      displayName: "Coastal Comfort HVAC",
      status: "ACTIVE",
      tier: "STANDARD",
      tenureDays: 205,
      onProbation: false,
      compliance: {
        insuranceValidUntil: "2027-02-01",
        certifications: [{ code: "EPA_608_UNIVERSAL", expiresOn: "2027-01-01" }],
        isCompliant: true,
      },
      capabilities: {
        tradeCategories: ["HVAC"],        equipment: ["CRANE_LIFT"],
        supportsAfterHours: true,
        maxConcurrentJobs: 3,
      },
      coverage: {
        postalCodes: ["60601", "60618"],
        homeBaseGeo: { lat: 41.89, lon: -87.64 },
        maxTravelKm: 30,
      },
      capacity: {
        asOfUtc: "2026-09-18T14:20:00Z",
        openJobs: 1,
        utilizationPct: 0.2,
        acceptingNewWork: true,
      },
      performance: {
        windowDays: 90,
        jobsCompleted: 58,
        slaHitRate: 0.83,
        firstTimeFixRate: 0.79,
        acceptanceRate: 0.86,
        avgResponseMinutes: 24,
        reworkRate: 0.07,
        costIndex: 1.05,
        csat: 4.1,
        dataSufficiency: "SUFFICIENT",
      },
      commercial: { standardHourlyUsd: 110, afterHoursHourlyUsd: 170 },
    },
    "VEN-00198": {
      vendorId: "VEN-00198",
      displayName: "Peachtree Air Systems",
      status: "ACTIVE",
      tier: "STANDARD",
      tenureDays: 690,
      onProbation: false,
      compliance: {
        insuranceValidUntil: "2026-10-10",
        certifications: [{ code: "EPA_608_UNIVERSAL", expiresOn: "2026-10-01" }],
        isCompliant: true,
      },
      capabilities: {
        tradeCategories: ["HVAC"],        equipment: ["CRANE_LIFT"],
        supportsAfterHours: true,
        maxConcurrentJobs: 4,
      },
      coverage: {
        postalCodes: ["60618", "60603"],
        homeBaseGeo: { lat: 41.77, lon: -87.62 },
        maxTravelKm: 35,
      },
      capacity: {
        asOfUtc: "2026-09-18T14:20:00Z",
        openJobs: 3,
        utilizationPct: 0.55,
        acceptingNewWork: true,
      },
      performance: {
        windowDays: 90,
        jobsCompleted: 77,
        slaHitRate: 0.86,
        firstTimeFixRate: 0.8,
        acceptanceRate: 0.74,
        avgResponseMinutes: 26,
        reworkRate: 0.1,
        costIndex: 1.0,
        csat: 4.2,
        dataSufficiency: "SUFFICIENT",
      },
      commercial: { standardHourlyUsd: 100, afterHoursHourlyUsd: 150 },
    },
    "VEN-00260": {
      vendorId: "VEN-00260",
      displayName: "Southern Comfort Mechanical",
      status: "ACTIVE",
      tier: "PROBATIONARY",
      tenureDays: 210,
      onProbation: true,
      compliance: {
        insuranceValidUntil: "2026-09-30",
        certifications: [{ code: "EPA_608_UNIVERSAL", expiresOn: "2026-09-25" }],
        isCompliant: true,
      },
      capabilities: {
        tradeCategories: ["HVAC"],        equipment: ["CRANE_LIFT"],
        supportsAfterHours: false,
        maxConcurrentJobs: 3,
      },
      coverage: {
        postalCodes: ["60603"],
        homeBaseGeo: { lat: 41.76, lon: -87.6 },
        maxTravelKm: 25,
      },
      capacity: {
        asOfUtc: "2026-09-18T14:20:00Z",
        openJobs: 2,
        utilizationPct: 0.48,
        acceptingNewWork: true,
      },
      performance: {
        windowDays: 90,
        jobsCompleted: 33,
        slaHitRate: 0.76,
        firstTimeFixRate: 0.7,
        acceptanceRate: 0.68,
        avgResponseMinutes: 31,
        reworkRate: 0.15,
        costIndex: 0.95,
        csat: 3.9,
        dataSufficiency: "SPARSE",
      },
      commercial: { standardHourlyUsd: 92, afterHoursHourlyUsd: 130 },
    },
  },
  scoreFactors: {
    scoringRunId: "run-99401",
    jobId: "JOB-DEMO-002",
    generatedAtUtc: hoursFromNow(-0.49),
    latencyMs: 640,
    binding: {
      rulesetVersion: "RULES-2026.09.1",
      modelName: "vendor-fit-lgbm",
      modelVersion: "v2.1.0",
      scoringMode: "RULES_ONLY",
      mlTrustFactor: 0,
      degradedReason: "ML_ENDPOINT_TIMEOUT",
    },
    candidateSummary: {
      vendorsInNetwork: 14,
      afterHardFilter: 3,
      exclusions: {
        MISSING_CERTIFICATION: 5,
        OUT_OF_SERVICE_AREA: 4,
        AT_CAPACITY: 2,
      },
    },
    featureSnapshotUri: "blob://retailfixit-audit/snapshots/JOB-DEMO-002/run-99401.json",
    ranked: [
      {
        rank: 1,
        vendorId: "VEN-00233",
        finalScore: 58,
        ruleScore: 58,
        mlScore: null,
        confidence: 0.41,
        confidenceBand: "LOW",
        predictions: {
          pSlaMet: { value: 0.6, ci90: [0.42, 0.75] },
          pFirstTimeFix: { value: 0.62, ci90: [0.44, 0.78] },
          pAcceptWithin15m: { value: 0.75, ci90: [0.6, 0.87] },
          expectedCostUsd: { p50: 3900, p90: 4400 },
        },
        factors: [
          { id: "SLA_HISTORY", source: "RULE", raw: 0.83, contributionPct: 30, evidence: "83.0% on-time across 58 jobs in the last 90 days" },
          { id: "PROXIMITY", source: "RULE", raw: 2.4, contributionPct: 23, evidence: "2.4 km from job site" },
          { id: "CURRENT_LOAD", source: "RULE", raw: 0.2, contributionPct: -25, evidence: "20.0% utilised, 1 open job" },
          { id: "COST_INDEX", source: "RULE", raw: 1.05, contributionPct: -22, evidence: "cost index 1.05 (1.00 = network average)" },
        ],
        counterfactual: "VEN-00198 would rank first if this vendor's final score fell below 55.0.",
        rationale: {
          template:
            "Ranked #1 of 3 eligible. Drivers: 83.0% on-time across 58 jobs in the last 90 days; 2.4 km from job site. Detractors: cost index 1.05 (1.00 = network average); 20.0% utilised, 1 open job.",
          narrative: null,
          source: "TEMPLATE",
          groundednessCheck: "SKIPPED",
          fallbackUsed: true,
        },
        automationEligible: false,
        blockingGates: ["RISK_TIER_HIGH", "LOW_CONFIDENCE"],
      },
      {
        rank: 2,
        vendorId: "VEN-00198",
        finalScore: 55,
        ruleScore: 55,
        mlScore: null,
        confidence: 0.44,
        confidenceBand: "LOW",
        predictions: {
          pSlaMet: { value: 0.63, ci90: [0.46, 0.78] },
          pFirstTimeFix: { value: 0.6, ci90: [0.42, 0.76] },
          pAcceptWithin15m: { value: 0.62, ci90: [0.44, 0.77] },
          expectedCostUsd: { p50: 3700, p90: 4200 },
        },
        factors: [
          { id: "SLA_HISTORY", source: "RULE", raw: 0.86, contributionPct: 34, evidence: "86.0% on-time across 77 jobs in the last 90 days" },
          { id: "PROXIMITY", source: "RULE", raw: 6.1, contributionPct: 16, evidence: "6.1 km from job site" },
          { id: "CURRENT_LOAD", source: "RULE", raw: 0.55, contributionPct: -13, evidence: "55.0% utilised, 3 open jobs" },
          { id: "REWORK_RATE", source: "RULE", raw: 0.1, contributionPct: -15, evidence: "10.0% rework rate over the trailing 90 days" },
        ],
        counterfactual: null,
        rationale: {
          template:
            "Ranked #2 of 3 eligible. Drivers: 86.0% on-time across 77 jobs in the last 90 days; 6.1 km from job site. Detractors: 10.0% rework rate over the trailing 90 days; 55.0% utilised, 3 open jobs.",
          narrative: null,
          source: "TEMPLATE",
          groundednessCheck: "SKIPPED",
          fallbackUsed: true,
        },
        automationEligible: false,
        blockingGates: ["RISK_TIER_HIGH", "LOW_CONFIDENCE"],
      },
      {
        rank: 3,
        vendorId: "VEN-00260",
        finalScore: 47,
        ruleScore: 47,
        mlScore: null,
        confidence: 0.38,
        confidenceBand: "LOW",
        predictions: {
          pSlaMet: { value: 0.55, ci90: [0.37, 0.72] },
          pFirstTimeFix: { value: 0.54, ci90: [0.36, 0.71] },
          pAcceptWithin15m: { value: 0.58, ci90: [0.4, 0.74] },
          expectedCostUsd: { p50: 3550, p90: 4000 },
        },
        factors: [
          { id: "VENDOR_TIER", source: "RULE", raw: null, contributionPct: -28, evidence: "vendor tier: PROBATIONARY" },
          { id: "SLA_HISTORY", source: "RULE", raw: 0.76, contributionPct: 22, evidence: "76.0% on-time across 33 jobs in the last 90 days" },
          { id: "PROXIMITY", source: "RULE", raw: 9.7, contributionPct: 14, evidence: "9.7 km from job site" },
          { id: "AFTER_HOURS", source: "RULE", ruleId: "R-GUARD-011", raw: null, contributionPct: -14, evidence: "Requested window is outside standard hours" },
        ],
        counterfactual: null,
        rationale: {
          template:
            "Ranked #3 of 3 eligible. Drivers: 76.0% on-time across 33 jobs in the last 90 days; 9.7 km from job site. Detractors: vendor tier: PROBATIONARY; Requested window is outside standard hours.",
          narrative: null,
          source: "TEMPLATE",
          groundednessCheck: "SKIPPED",
          fallbackUsed: true,
        },
        automationEligible: false,
        blockingGates: ["RISK_TIER_HIGH", "LOW_CONFIDENCE"],
      },
    ],
  },
};

export default fixture;
