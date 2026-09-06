# Deploying RetailFixIt Part 2



## 0. One-time setup

```bash
az login
az account set --subscription "<your subscription id>"

az group create -n rg-retailfixit-data -l eastus2 --tags project=retailfixit
az group create -n rg-retailfixit-app  -l eastus2 --tags project=retailfixit
```


## 1. Data resource group (persistent - never delete) - OPTIONAL, skippable

`data.bicep` provisions the Azure SQL free-tier server/database
(system-of-record in Part 1's design) and its RLS policy sketch. **Part
2 deliberately doesn't wire SQL connectivity into the app at all** -
state/audit persist to Blob Storage instead (`store.py`, `audit.py` -
see the README's "Azure SQL" note). Nothing in the deployed app reads
`SQL_SERVER_FQDN`/`SQL_DATABASE_NAME` beyond passing them through as
app settings, so this whole step can be skipped for a minimal deploy -
`main.bicep` accepts empty strings for both parameters. Run it only if
you want the SQL resource itself to exist for its own sake (e.g. to
inspect the RLS policy in the portal):

```bash
az deployment group validate -g rg-retailfixit-data -f infra/modules/data.bicep \
  -p sqlAdminPassword='<generate a strong password>'

az deployment group create -g rg-retailfixit-data -f infra/modules/data.bicep \
  -p sqlAdminPassword='<same password>'
```

Capture the outputs (`sqlServerFqdn`, `sqlDatabaseName`) if you do run
it - `main.bicep` takes them as optional parameters in step 2.

**Do not leave a client connected to the database** - the serverless
free tier auto-pauses after 60 minutes idle, and an open connection
blocks that pause, which is the only thing keeping this tier free.

## 2. App resource group (disposable)

If step 1 was skipped, pass empty strings for both SQL parameters -
nothing in the app reads them beyond passing them through as app settings:

```bash
az deployment group validate -g rg-retailfixit-app -f infra/main.bicep \
  -p sqlServerFqdn='' sqlDatabaseName='' deployAzureOpenAi=false

az deployment group create -g rg-retailfixit-app -f infra/main.bicep \
  -p sqlServerFqdn='' sqlDatabaseName='' deployAzureOpenAi=false
```

(Substitute the real `sqlServerFqdn`/`sqlDatabaseName` outputs from step
1 if you did run it.)



## 3. Deploy the code

Flex Consumption + Python Durable Functions is fussiest about **remote
build** - a local zip deploy without it is the most common cause of
orchestrations stuck in `Pending` (the function list never indexes
`function_app.py`). `host.json`, `requirements.txt`, and `function_app.py`
all live at `backend/` root (the cwd this command already uses) -
`function_app.py` is a thin entry point that just registers the
`api/http_bp.py` and `orchestrator/saga_bp.py` blueprints; Azure
Functions Python v2 only ever imports that one root file directly.

```bash
cd part2-dispatch-ai/backend
func azure functionapp publish <functionAppName from step 2 output> --build remote
```

After publishing, **verify in the portal** (Function App > Functions)
that all 21 of the following are listed before wiring up a demo:

- `job_created_client`, `job_orchestrator`, and the six activities
  (`publish_scoring_requested_activity`, `score_job_activity`,
  `enqueue_manual_review_activity`, `assign_vendor_activity`,
  `escalate_activity`, `complete_orchestration_activity`)
- the external-event route: `submit_vendor_response` (the saga's other
  external event, `DispatcherDecision`, is raised from
  `create_assignment` below - no separate route for it)
- the HTTP API routes from `api/http_bp.py`: `create_job`, `list_jobs`,
  `get_job`, `get_recommendation`, `create_assignment`, `complete_job`,
  `get_audit`, `list_vendors`, `replay_job`, `seed_fixture_jobs`,
  `dispatch_job_to_saga`, `get_orchestration_status`

## 3.5. Seed the demo fixtures

`POST /api/admin/seed` is the one-call demo trigger: it reads
`data/jobs.json` straight off disk (not the state store, which is empty
on a fresh deployment) and publishes `JobCreated` for every fixture job
onto the real Service Bus topic - the exact same path a live `POST
/jobs` call takes. Call it once after deploying:

```bash
curl -X POST https://<functionAppName>.azurewebsites.net/api/admin/seed \
  -H "x-functions-key: <a function-level key from the portal>"
```

Scoring happens asynchronously after that (the Durable saga consumes
each `JobCreated` and scores it as an activity) - `GET
/jobs/{jobId}/recommendation` may briefly 404 immediately after seeding
(the frontend's API client retries on exactly that).

## 3.6. CORS verification (frontend integration)

`infra/main.bicep` sets `siteConfig.cors` to allow
`http://localhost:5173`/`:3000` (the React dev server) and
`https://portal.azure.com` (so the Portal's own Test/Run blade works).
Verify it took effect:

```bash
curl -i -X OPTIONS https://<functionAppName>.azurewebsites.net/api/jobs \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET"
# expect Access-Control-Allow-Origin: http://localhost:5173 in the response
```

**If CORS fails** - Flex Consumption's CORS support has some reported
reliability issues:

```bash
az functionapp cors add -g rg-retailfixit-app -n <functionAppName> \
  --allowed-origins http://localhost:5173
```

Or route around it entirely with the Vite dev proxy: uncomment the
`server.proxy` block in `frontend/vite.config.ts` and set
`VITE_API_BASE_URL=/api` in `frontend/.env.local`.

## 4. The AML online endpoint module is NOT part of this deployment

`infra/modules/aml-online-endpoint.bicep` is real, syntactically valid
Bicep, kept for the blue/green rollout narrative and the cost
arithmetic in its header comment - but it is deliberately never applied.
The only command that should ever be run against it is:

```bash
az deployment group validate -g rg-retailfixit-app -f infra/modules/aml-online-endpoint.bicep \
  -p workspaceName=<amlWorkspaceName from step 2 output>
```

Running `az deployment group create` against this file would provision
a continuously-billed managed compute instance - see the README's
"What Runs vs. What Is Documented" table for why that's out of scope
at this budget.

## 5. Tear-down (optional)

Real running cost at this scale is dominated by Service Bus Standard
(~$0.33/day); Functions, SQL (free tier), and AML registry are
consumption-based or free. Given that, this repo doesn't invest in
automated teardown - the IaC itself is the graded artifact, not the
cost savings from deleting it. If you do want to tear down:

```bash
az group delete -n rg-retailfixit-app --yes    # safe - fully reproducible from infra/main.bicep
# rg-retailfixit-data: only delete if you're fully done - this loses
# the seeded SQL data AND the free-tier region lock, permanently.
```
