# RetailFixIt Dispatch Console (Part 2 — Front End)

One screen: a dispatcher opens a job, sees the AI's ranked vendor recommendations with
plain-English rationale, and either accepts the top pick or overrides to a different
vendor with a structured reason. React + TypeScript + Vite + Tailwind CSS v4, no
component-library dependency, no auth, no nav shell.

## Running it

```bash
npm install
npm run dev
```

Opens on `http://localhost:5173` (or the next free port). Ships with `VITE_USE_MOCKS=true`
by default — no backend required to see the full app. `npm run build` produces a static
`dist/` (typechecked via `tsc -b` first); `npm run preview` serves that build locally.

Copy `.env.example` to `.env` to point at a real deployed backend instead of mocks:

```bash
VITE_API_BASE_URL=https://<functionAppName>.azurewebsites.net/api   # from `az deployment group create` output
VITE_USE_MOCKS=false
```

There is no local backend to run against anymore — the backend is Azure Functions
(Flex Consumption), deployed via `backend/infra/main.bicep` + `func azure functionapp
publish --build remote` (see `backend/infra/DEPLOY.md`). Point `VITE_API_BASE_URL` at
the real Function App URL once it's deployed.

## What's in this screen

- **Job summary** (`src/components/JobSummaryCard.tsx`) — trade category, problem code,
  priority/risk/recall/safety badges, SLA countdown, site identifier, not-to-exceed and
  revenue-at-risk. `site.addressRef` is rendered as the PII-redaction token it actually is
  (e.g. `pii://address/2c7e44a9`) rather than a resolved street address — see "Aligned
  against the real backend contract" below.
- **AI Recommendation strip** — scoring-run metadata (model, scoring mode, latency,
  candidates-eligible) plus the automation-gate badge cluster
  (`AutomationGateStatus.tsx`), evaluated against the **top-ranked candidate only**, per
  the brief: `automationEligible` / `blockingGates` and the top vendor's
  `dataSufficiency`. Unobtrusive by design — a badge row, not a panel.
- **Ranked vendor list** (`VendorList.tsx` / `VendorCard.tsx`) — rank, name, final score
  (0-100), and an always-visible inline meter (`ScoreBreakdown.tsx` / `ui/MeterBar.tsx`)
  for rule score vs. ML score vs. confidence band. ML shows "n/a" when `mlScore` is
  `null` (RULES_ONLY / ML-fallback runs). Never hidden behind a click.
- **Rationale detail** (`RationaleDetail.tsx`) — the trust centerpiece. Selecting a
  vendor card shows its rationale (serif type, visually distinct from the rest of the
  UI) — the AI-generated `narrative` when present, falling back to the always-available
  deterministic `template` otherwise (see below), whether the groundedness check
  passed/failed/was skipped, an optional counterfactual line, and the full `factors[]`
  breakdown (signed `contributionPct` + deterministic `evidence` strings), sorted by
  `|contribution|` to match the backend's own ordering.
- **Decision panel** (`DecisionPanel.tsx`) — one action. Defaults to the top pick
  ("Accept recommendation & assign"); selecting any other vendor switches it to
  "Confirm override & assign" and requires a reason code from the closed enum
  (`CUSTOMER_RELATIONSHIP` / `LOCAL_KNOWLEDGE` / `CAPACITY_DATA_WRONG` /
  `PRIOR_QUALITY_ISSUE` / `MODEL_DISAGREE_OTHER`) plus an optional free-text note.
- **Confirmation** (`ConfirmationBanner.tsx`) — on submit, a banner names the assigned
  vendor, who/what assigned it (`assignmentSource`), correlation ID, and (for overrides)
  the reason code, with an expandable audit trail pulled from `GET /jobs/{jobId}/audit`.

### States handled

- **Loading** — skeleton layout (`ScreenSkeleton.tsx`).
- **No eligible vendors** — `ranked: []` renders `NoEligibleVendors.tsx` instead of the
  vendor list/decision panel: explains the hard-filter exclusion counts and represents
  the saga's escalate-to-supervisor path (button present but disabled — no supervisor
  workflow in scope).
- **Low-confidence / degraded recommendation** — when the top candidate's
  `confidenceBand` is `LOW` or `automationEligible` is `false`, `LowConfidenceNotice.tsx`
  surfaces above the list with the specific blocking gates.
- **Successful override / accept** — `ConfirmationBanner.tsx`, not a silent state change.
- **Fetch error** — `ErrorBanner.tsx` with retry.

## Aligned against the real backend contract, not just Part 1 docs

`part2-dispatch-ai/backend/` (built in parallel, same repo) landed its domain logic and
Pydantic contracts (`backend/contracts/models.py`) partway through this build. Rather
than ship the frontend against `part1-summary.md`'s field-name list alone, the types in
`src/types/contracts.ts` and all three mock fixtures were re-aligned against that file
directly, plus `backend/domain/gates.py`, `domain/rationale.py`, `domain/factors.py`, and
`backend/data/{jobs,vendors}.json` — real, not guessed. Concretely, this corrected a
several real divergences from the first pass:

- **`JobEvent` is a CloudEvents-shaped envelope** — `{ type, jobId, correlationId,
  occurredAtUtc, data: {...} }`. The job payload (`site`/`job`/`sla`/`risk`/`dispatch`)
  lives under `data`, not flat on the event.
- **`finalScore`/`ruleScore`/`mlScore` are already 0-100**, not 0-1 (confirmed in
  `backend/domain/rule_score.py` and `blend.py`). `confidence` stays 0-1.
  `mlScore` is `null`, not `0`, on RULES_ONLY / ML-fallback runs.
- **Real enum value sets**: `priority` is `P1`/`P2`/`P3` (not `EMERGENCY`/`URGENT`/...),
  `sla.sensitivity` is `ROUTINE`/`ELEVATED`/`CRITICAL`, `vendor.tier` is
  `PREFERRED`/`STANDARD`/`PROBATIONARY`, `riskTier` has no `CRITICAL` value.
- **`rationale.narrative` is `null` whenever `source: "TEMPLATE"`** — which is the
  *default* path, since `ENABLE_LLM_NARRATION` defaults to `false` in
  `backend/config/scoring_config.json`. The UI falls back to the always-populated
  `template` field; an earlier pass here assumed `narrative` was always a string, which
  would have rendered blank against the real backend's default config.
- **`groundednessCheck` is `"PASSED" | "FAILED" | "SKIPPED"`**, not a boolean.
- **Real `blockingGates` vocabulary** (`backend/domain/gates.py`) — simplified to exactly
  two checks for this demo build (down from Part 1's fuller 7-check design):
  `RISK_TIER_HIGH`, `LOW_CONFIDENCE`.
- **`site.addressRef` is a PII-redaction token** (e.g. `"pii://address/2c7e44a9"`), never
  a resolved street address — confirmed in `backend/data/jobs.json`, consistent with Part
  1's "full address released to a vendor only after acceptance" design.
- **`AssignmentRequest` is a real, already-defined backend model** —
  `{ selectedVendorId, overrideReasonCode?, note? }`. Simpler than a first-pass guess:
  `jobId` travels in the URL, `correlationId`/`scoringRunId` are resolved server-side.

The three mock jobIds (`JOB-DEMO-005`, `JOB-DEMO-002`, `JOB-DEMO-003`) intentionally match
`backend/data/jobs.json`'s seed data and its `_scenario` annotations, so the same three
demo scenarios line up once `VITE_USE_MOCKS=false` points at the real backend, instead of
two disconnected sets of demo data.

**Update — the backend shipped a real Azure Functions HTTP layer** (`backend/api/http_bp.py`,
deployed on Flex Consumption, CORS configured in `backend/infra/main.bicep` for
`:5173`/`:3000`) and resolved the job/vendor-context
gap flagged above via **option (b)**: separate `GET /jobs/{jobId}` and `GET /vendors`
endpoints, not embedding job/vendors into the recommendation response. `apiClient.getJobContext`
was updated accordingly — it now fetches all three in parallel and assembles them
client-side; see "API client" below for the full, verified surface (checked against
`backend/contracts/openapi.json` and the generated examples in `backend/contracts/examples/*.json`,
not hand-typed guesses). Two field-name corrections that came out of that verification pass,
both now fixed:
- `POST /jobs/{jobId}/assignment`'s response field is `assignmentSource`
  (`AUTO`/`DISPATCHER_ACCEPT`/`DISPATCHER_OVERRIDE`), not `status`; the vendor field is
  `selectedVendorId`, not `assignedVendorId`; there is no `assignmentId`.
- `GET /jobs/{jobId}/audit`'s response is `{ jobId, job, scoreFactors, assignment, events[], decisions[] }`
  (the job, its ScoreFactors, the current assignment, and raw `events.jsonl`/`decisions.jsonl`
  slices), not a flat list of generic entries.

## Mock-first, by design

`VITE_USE_MOCKS=true` (default) serves three committed fixtures from `src/mocks/`:

| File | jobId | Scenario |
|---|---|---|
| `job-demo-005-auto-eligible.ts` | `JOB-DEMO-005` | Happy path — 4 eligible vendors, high-confidence top pick, all automation gates pass. |
| `job-demo-002-manual-review.ts` | `JOB-DEMO-002` | High-risk P1 (`RISK_TIER_HIGH` gate) **plus** a degraded ML endpoint layered on top (`mlTrustFactor` forced to 0, confidence stays `LOW` → `LOW_CONFIDENCE` gate also fires), with the LLM narration itself falling back to the deterministic template. Two independent guardrails, one fixture. |
| `job-demo-003-no-eligible-vendors.ts` | `JOB-DEMO-003` | Hard filter eliminates every candidate (`ranked: []`) — no vendor in network has the required trade capability/license. |

SLA timestamps (`occurredAtUtc`/`responseDueUtc`/`resolutionDueUtc`/`generatedAtUtc`) are
computed relative to `Date.now()` at import time (`src/mocks/relativeTime.ts`), not
hardcoded, so the "response due in Xh" countdowns always read as a live, in-flight job
regardless of when the demo is actually run.

`src/mocks/index.ts` registers all three for the "Sample job" switcher in the header,
which stands in for whatever real queue/list would normally hand the dispatcher a jobId.

Switch to the real backend by setting `VITE_USE_MOCKS=false` — every method in
`src/api/client.ts`, including `getJobContext`, now calls a real, verified endpoint; no
further code change needed.

## API client (`src/api/client.ts`)

Configurable base URL via `VITE_API_BASE_URL` (points at the deployed Azure Function
App, e.g. `https://<functionAppName>.azurewebsites.net/api` — see `.env.example`).
Full real HTTP surface, verified against `backend/api/http_bp.py`,
`backend/contracts/openapi.json`, and `backend/contracts/examples/*.json`:

| Method | Endpoint | Used by |
|---|---|---|
| `createJob` | `POST /jobs` | Implemented for contract completeness. **Not called by this screen's primary flow** — per the Part 1 architecture, jobs are created by the Customer-facing Intake API, not the Dispatcher Console, which only opens already-created jobs. |
| `listJobs` | `GET /jobs` | Implemented, not called by this screen (the "Sample job" switcher uses the mock registry) — available for a future job-queue view. |
| `getJob` | `GET /jobs/{jobId}` | Job details for the summary header — one of the three parallel calls in `getJobContext`. |
| `getRecommendation` | `GET /jobs/{jobId}/recommendation` | Returns bare `ScoreFactors` — no embedded job/vendor context (confirmed: the backend resolved that gap with separate endpoints, not embedding). Scoring is now asynchronous (Durable saga activity), so this retries up to 5 times, ~1.5s apart, on a 404 specifically. |
| `listVendors` | `GET /vendors` | Every vendor in the network; `getJobContext` reduces this to a `Record<vendorId, VendorProfile>` client-side to resolve display names for `ranked[]` entries. |
| `submitAssignment` | `POST /jobs/{jobId}/assignment` | Accept-top-pick or override submission. Request body is the real `AssignmentBody`/`AssignmentRequest`; response is the persisted assignment record (`assignmentSource`, `selectedVendorId` — see field-name corrections above). |
| `completeJob` | `POST /jobs/{jobId}/completion` | Implemented for contract completeness, not wired to any UI action (out of scope for this screen — see scope cuts). |
| `getAudit` | `GET /jobs/{jobId}/audit` | Powers the expandable audit trail in the confirmation banner — flattens the real `{job, scoreFactors, assignment, events[], decisions[]}` shape into a simple chronological list for display. |
| `getJobContext` | *(not a single endpoint)* | Fetches `getJob` + `getRecommendation` + `listVendors` in parallel and assembles `{ job, vendors, scoreFactors }` client-side — see `JobContextResponse` in `contracts.ts`. |

All request/response TypeScript types live in `src/types/contracts.ts`, each annotated
inline with the exact backend source file it was verified against.

## Deliberate scope cuts

- No routing/auth/nav shell, no dark mode, no settings — one screen, per the brief.
- `createJob` implemented but not wired to a UI action (see table above).
- "Escalate to supervisor" button in the no-eligible-vendors state is present but
  disabled — no supervisor workflow exists in this build; it represents where the saga's
  escalation path would connect.
- `counterfactual` is rendered as an opaque single line when present (backend only ever
  computes it for rank 1, per `domain/counterfactual.py`'s deliberately minimal design).
- No keyboard arrow-key roving-tabindex on the vendor radiogroup (tab + space/enter works
  via native `<button role="radio">`; full `role="radio"` arrow-key semantics were cut as
  polish, not core to the deliverable).
- Predictions (`pSlaMet`/`pFirstTimeFix`/`pAcceptWithin15m`/`expectedCostUsd`, each with a
  `ci90` confidence interval) are fully typed in `contracts.ts` and present in every mock
  fixture, but not surfaced in the UI — the brief calls for rule/ML/confidence and
  rationale, not raw model probabilities; typed for completeness, not rendered.
- `npm audit` reports one moderate dev-only advisory in `esbuild`
  (GHSA-67mh-4wv8-2f99, dev server only, not present in the production build) — left as
  is rather than pulling in a breaking Vite major for a take-home.
