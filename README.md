# RetailFixIt Vendor Recommendation Service

##

## System Overview

```text
React Admin UI
    |
    v
POST /api/jobs
    |
    v
Azure Function HTTP trigger
    |
    v
Azure Service Bus: JobCreated
    |
    v
orchestrator-start subscription
    |
    v
Durable Functions client and orchestration
    |
    +--> scoring activity
    |       |
    |       +--> eligibility rules
    |       +--> rule score
    |       +--> LightGBM uplift
    |       +--> TreeSHAP explanation
    |       +--> ranked ScoreFactors
    |
    +--> automation gate
    |       +--> automatic assignment
    |       +--> dispatcher review
    |
    +--> vendor accept/decline external event
    |
    v
JobAssigned / JobCompleted events
```

The Durable orchestrator calls scoring as a Durable activity. It also publishes the scoring-requested and recommendation-generated events so the broader event topology remains visible. Durable state, retries, timers, and external events are not duplicated through an additional scoring Service Bus worker.

## AI Approach

The service uses a hybrid approach:

1. Hard eligibility rules remove vendors that are inactive, non-compliant, on probation, outside coverage, unavailable, at capacity, excluded by the customer, or missing the required certification/equipment.
2. The deterministic rule score uses SLA performance, proximity, first-time-fix rate, cost, available capacity, and vendor tier.
3. A LightGBM binary classifier provides an uplift score representing estimated success probability.
4. The rule and ML scores are blended using the configuration value `mlTrustFactor`.
5. The final candidates are sorted and the top five are returned.
6. Automation gates decide whether the top candidate can be auto-assigned or requires dispatcher review.

Trade category is a controlled value shared by job and vendor contracts:

```text
HVAC, PLUMBING, ELECTRICAL, REFRIGERATION, ELEVATOR
```

The current demo eligibility match uses trade category, certifications, equipment, coverage, compliance, capacity and status. 


The ML model is trained on synthetic data. 

## Explainability and Trust

Every recommendation includes:

- final score
- rule score
- ML score
- confidence and confidence band
- ranked factors
- TreeSHAP contributions when ML is available
- deterministic evidence strings

- automation eligibility and blocking gates
- human-readable rationale

The rationale is generated deterministically from scored data. Optional Azure OpenAI narration can rewrite the rationale, but it does not rank, filter, or override vendors. Groundedness checks reject generated text containing unsupported numbers and fall back to the deterministic rationale.



If ML loading or inference fails, the pipeline degrades to `RULES_ONLY` and still returns a valid ranked and explained result when eligible vendors exist.

## Event Integration

Canonical lifecycle events are published on the `job-lifecycle` Service Bus topic:

```text
job.created.v1
job.scoring_requested.v1
job.recommendation_generated.v1
job.assigned.v1
job.completed.v1
```

Messages use `jobId` as the Service Bus session ID. The Durable client consumes `JobCreated`, starts an orchestration with `instanceId = jobId`, and uses Durable timers and external events for dispatcher and vendor decisions.

## Frontend

The React admin console provides:

- empty initial state with a Create Job action
- full job creation modal using the canonical job contract
- five reusable demo templates
- editable job ID for repeat Durable runs
- asynchronous scoring progress state
- recommendation polling
- vendor ranking and rationale display
- dispatcher accept or manual override
- override reason codes and notes
- vendor accept/decline simulation
- visible audit trail



.

## Model Versioning and Deployment

Models are stored by version:

```text
backend/models/vendor_uplift/1.0.0/
backend/models/vendor_uplift/1.1.0/
```

Aliases are managed in:

```text
backend/config/registry.json
```

The loader validates the feature schema hash before loading a model. Production and shadow versions can be changed through the alias registry without changing scoring code.

Infrastructure is defined in:

```text
backend/infra/main.bicep
backend/infra/modules/data.bicep

```

The deployed low-cost path uses the model in-process inside Azure Functions. The AML managed online endpoint is documented as a production deployment option but is not deployed in this demo.
## Model Deployment Approach: Current vs. Production Path



Current (this exercise): The LightGBM model is loaded in-process inside the Azure Functions app, directly from the versioned artifact under backend/models/vendor_uplift/1.0.*/. Scoring calls model.predict() and TreeSHAP's TreeExplainer locally, with zero network hop. This keeps cost at zero-when-idle (matching the Functions Consumption/Flex billing model) and avoids the latency of a remote inferencei



Production path (docntedyean Azure Machine Learning managed online endpoint, intentionally left undeployed because managed online endpoints keep a compute instance running continuously and don't scale to zero that is a real, non-trivial cost even when imo. In a production deployment, this endpoint would host the model instead of bundling it with the Function pp, and the Function App would call it over HTTPS rather than loading the model in-process.is gives for independent model lifecycle managemeandt — a new model version can be deployed to the endpoint and traffic-shifted without redeploying the Function App at all.

Promotion between model versions on the endpoint would follow a blue/green pattrthat is to n: deploy the new model version to a second deployment slot behind the same endponand t, shift a small percentage of traffic to it (canary), monitor guardrail metrics (SLA-outcome calibration, override rate) for a defined winow, then shift 100% of traffic once it clears the  .this complete exercise is done ll as an endpoint traffic-split configuration change, not a code redeploy. This mirrors the shadow → canary → promote lifecy
get.
.











## Logging and Overrides

Application Insights receives structured scoring messages including:

- scoring start and completion
- eligibility counts and exclusion reasons
- model version and artifact fingerprint
- vendor scoring stages and timings
- model load or inference failures
- selected top vendor and automation gate result

Blob audit logs record:

- lifecycle events
- scoring runs
- automatic assignments
- dispatcher accepts and overrides
- override reason codes and notes

## Feedback and Retraining


Two feedback signals matter here:

Job completion outcomes (SLA met, first-time-fix, actual cost)i.e— the ground truth for "did the recommended vendor actually succeed."
Dispatcher overrides (when a human picks someone other than the AI's top pick, with a reason code)is a faaster signal than waiting for outcomes, since a rising rate of a specific override reason can flag a model or data problem before enough completions accumulate to prove it statistically.

In this system: when a job reaches JobCompleted or a dispatcher logs an override, that event is appended to the audit trail alongside the exact feature snapshot that existed at scornggtime.these completeions   jois back to their original scoring run on (jobId, vendorId),— using the point-in-time feature snapshot, never recomputed from current vendor stat, so today's vendor performance can't leak into how an old prediction gets judged. This produces a labeled row (success = slaMet AND firstTimeFix) ready fortrainingn.

A new model trained this way must beat the live model on held-out data, then pass shadow and canary stage, before being promoted .
## Limitations and Next Steps

- Training data is synthetc ;and  production calibration requires historical completed-job data.
- The live system should use stronger authentication and authorization than the demo's anonymous HTTP routes.Azure Api Management(APIM) can be implemented along RBAC for users. 
- A real deployment would add private endpoints, stronger network isolation, secret rotation, and operational dashboards.
- The AML online endpoint is documented but intentionally not deployed for cost control.
.
