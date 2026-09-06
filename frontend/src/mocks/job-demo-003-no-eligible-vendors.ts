import type { JobContextResponse } from "../types/contracts";
import manualReview from "./job-demo-002-manual-review";
import { hoursFromNow } from "./relativeTime";

/**
 * Scenario: eligible HVAC vendors, mirroring backend/data/jobs.json JOB-DEMO-003.
 * This fixture keeps a ranked response available for the frontend sample-job flow.
 */
const fixture: JobContextResponse = {
  job: {
    type: "job.created.v1",
    jobId: "JOB-DEMO-003",
    correlationId: "01J8Z9K4M2QW3E5R7T9Y1U3I7Q",
    occurredAtUtc: hoursFromNow(-1),
    data: {
      customerId: "CUST-000199001",
      accountTier: "STANDARD",
      site: {
        siteId: "SITE-0099001",
        geo: { lat: 41.7, lon: -87.9 },
        addressRef: "pii://address/aa11bb22",
        timezone: "America/Chicago",
      },
      job: {
        tradeCategory: "HVAC",
        priority: "P2",
        requiresCertification: [],
        requiresEquipment: [],
        estimatedLabourHours: 4.0,
        notToExceedUsd: 3000,
        isRecall: false,
      },
      sla: {
        responseDueUtc: hoursFromNow(11),
        resolutionDueUtc: hoursFromNow(23),
        sensitivity: "ELEVATED",
        breachPenaltyUsd: 800,
      },
      risk: {
        riskTier: "MEDIUM",
        safetyRisk: true,
        revenueAtRiskUsd: 4000,
      },
      dispatch: {
        excludedVendorIds: [],
        allowAutoAssign: true,
      },
    },
  },
  vendors: manualReview.vendors,
  scoreFactors: {
    ...manualReview.scoreFactors,
    jobId: "JOB-DEMO-003",
    scoringRunId: "run-003-electrical",
    generatedAtUtc: hoursFromNow(-1),
  },
};

export default fixture;
