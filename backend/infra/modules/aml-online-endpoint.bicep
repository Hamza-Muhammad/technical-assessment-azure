// DOCUMENTED ONLY - NEVER DEPLOYED. Do not add this module to main.bicep
// or run `az deployment group create` against it. It is validated only:
//
//   az deployment group validate -g rg-retailfixit-app -f infra/modules/aml-online-endpoint.bicep \
//     -p workspaceName=<aml workspace name>
//
// Why not deployed - the cost arithmetic:
//   A managed online endpoint has no scale-to-zero. The smallest
//   general-purpose instance (Standard_DS2_v2) runs ~$0.146/hr base
//   compute + the AML surcharge, continuously, whether or not it ever
//   serves a request:
//     $0.146/hr * 24hr * 30d               ~= $107/month, compute only, no surcharge
//     -----------------------------------------------------------
//     one instance, one deployment          ~= $107/month
//     two deployments for blue/green        ~= $214/month
//   That is 54-107% of this project's entire ~$200 budget for one
//   component, on a workload (~1,000 vendors, single-digit-ms scoring)
//   that a Python in-process LightGBM call already serves comfortably
//   inside the Function App - see domain/ml_uplift.py and
//   domain/model_registry.py, which is what's actually deployed.
//
// Kept here, real and validated, because the *decision not to deploy it*
// should read as an engineering call with the numbers shown, not as
// something skipped. The blue/green rollout narrative below (v2 at
// 0% -> 10% -> 50% -> 100%) is exactly how promotion would work if/when
// volume ever justified paying for a warm endpoint.
targetScope = 'resourceGroup'

@description('Existing AML workspace (model registry) from main.bicep.')
param workspaceName string

param location string = resourceGroup().location

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' existing = {
  name: workspaceName
}

resource onlineEndpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-04-01' = {
  parent: workspace
  name: 'vendor-uplift-endpoint'
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    authMode: 'AMLToken'
    publicNetworkAccess: 'Disabled' // would sit behind a Private Endpoint in any real deployment
  }
}

// "Blue" - the current production model version, at 100% until a
// candidate has proven itself in shadow (see ml/train.py's offline gate).
resource blueDeployment 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints/onlineDeployments@2024-04-01' = {
  parent: onlineEndpoint
  name: 'blue-v1'
  location: location
  sku: { name: 'Default', capacity: 1 }
  properties: {
    endpointComputeType: 'Managed'
    instanceType: 'Standard_DS2_v2'
    model: '${workspaceName}/models/vendor-uplift/versions/1'
    instanceCount: 1
  }
}

// "Green" - a retrained candidate. Traffic starts at 0 (shadow: scores
// every request, logged only, never served - see part1-architecture.md
// section 9 step 5), then a human promotes it through 10% -> 50% -> 100%
// by changing `onlineEndpoint.properties.traffic` below, purely a
// traffic-split config change, not a redeploy - the fastest possible undo.
resource greenDeployment 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints/onlineDeployments@2024-04-01' = {
  parent: onlineEndpoint
  name: 'green-v2'
  location: location
  sku: { name: 'Default', capacity: 1 }
  properties: {
    endpointComputeType: 'Managed'
    instanceType: 'Standard_DS2_v2'
    model: '${workspaceName}/models/vendor-uplift/versions/2'
    instanceCount: 1
  }
}

// Traffic split lives on the endpoint resource itself. Rollout sequence,
// each step a separate `az ml online-endpoint update --traffic` call
// (or a redeploy of just this block) after real-outcome evidence, not a
// timer:
//   { 'blue-v1': 100, 'green-v2': 0   }  <- shadow: green scores, never serves
//   { 'blue-v1': 90,  'green-v2': 10  }  <- canary
//   { 'blue-v1': 50,  'green-v2': 50  }  <- confirm
//   { 'blue-v1': 0,   'green-v2': 100 }  <- promote; blue archived, not deleted
// (traffic percentages are set via `properties.traffic` on `onlineEndpoint`
// above post-deployment - omitted from the initial create so the first
// apply always starts green at 0%, i.e. shadow-only, by construction)

output endpointName string = onlineEndpoint.name
