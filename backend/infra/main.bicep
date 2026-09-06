// Deploys into rg-retailfixit-app (disposable). Function App (Flex
// Consumption, Python), Service Bus Standard (topic + sessions + DLQ),
// Key Vault, Application Insights, Managed Identity (system-assigned on
// the Function App), an AML workspace (model registry only - no
// managed online endpoint, see infra/modules/aml-online-endpoint.bicep),
// and an Azure OpenAI account + gpt-4o-mini deployment.
//
// Deploy: az deployment group create -g rg-retailfixit-app -f infra/main.bicep
//   -p sqlServerFqdn=<from data.bicep output> sqlDatabaseName=<...>
targetScope = 'resourceGroup'

@description('Region. East US 2 / Sweden Central have the widest gpt-4o-mini quota')
param location string = resourceGroup().location

param projectTag string = 'retailfixit'

@description('Outputs from modules/data.bicep - wired in as app settings, not a Bicep cross-RG reference.')
param sqlServerFqdn string = ''
param sqlDatabaseName string = ''

@description('Set false until Azure OpenAI quota is confirmed available (see README fallback ladder) - keeps this template deployable even with 0 TPM quota.')
param deployAzureOpenAi bool = false

var suffix = uniqueString(resourceGroup().id)
var storageAccountName = 'strfitapp${suffix}'
var deploymentContainerName = 'app-package'
var functionAppName = 'func-retailfixit-${suffix}'
var flexPlanName = 'plan-retailfixit-flex-${suffix}'
var serviceBusNamespaceName = 'sb-retailfixit-${suffix}'
var keyVaultName = 'kv-rfit-${take(suffix, 15)}'
var logAnalyticsName = 'log-retailfixit-${suffix}'
var appInsightsName = 'appi-retailfixit-${suffix}'
var amlWorkspaceName = 'aml-retailfixit-${suffix}'
var amlStorageAccountName = 'strfitaml${suffix}'
var openAiAccountName = 'aoai-retailfixit-${suffix}'

// ---------------------------------------------------------------------
// Storage (Function App deployment package + AzureWebJobsStorage +
// the Durable Functions default storage backend)
// ---------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: { project: projectTag }
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: deploymentContainerName
  properties: { publicAccess: 'None' }
}

// state/ - job/scoreFactors/assignment JSON blobs (store.py's blob
// backend); audit/ - append blobs for scoring_runs/events/decisions
// (audit.py's blob branch). 
resource stateContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'state'
  properties: { publicAccess: 'None' }
}

resource auditContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'audit'
  properties: { publicAccess: 'None' }
}

// ---------------------------------------------------------------------
// Observability
// ---------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: { project: projectTag }
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: { project: projectTag }
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------------------------------------------------------------------
// Key Vault - PII column-encryption key + any secrets the app needs
// (SQL connection string, referenced from Function App settings via
// @Microsoft.KeyVault(...) - never a raw connection string in config)
// ---------------------------------------------------------------------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: { project: projectTag }
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

// ---------------------------------------------------------------------
// Service Bus Standard - topic job-lifecycle, sessions enabled,
// one subscription per consumer (events/topology.py), each with a SQL
// filter on `type` and a max delivery count before Service Bus
// auto-dead-letters (built-in $deadletterqueue sub-queue per subscription).
// ---------------------------------------------------------------------
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2023-01-01-preview' = {
  name: serviceBusNamespaceName
  location: location
  tags: { project: projectTag }
  sku: { name: 'Standard', tier: 'Standard' }
}

resource jobLifecycleTopic 'Microsoft.ServiceBus/namespaces/topics@2023-01-01-preview' = {
  parent: serviceBusNamespace
  name: 'job-lifecycle'
  properties: {
    requiresDuplicateDetection: true
    duplicateDetectionHistoryTimeWindow: 'PT10M'
  }
}

var subscriptionDefs = [
  { name: 'orchestrator-start', filterType: 'job.created.v1' }
  { name: 'scoring-function', filterType: 'job.scoring_requested.v1' }
  { name: 'orchestrator-recommendation', filterType: 'job.recommendation_generated.v1' }
  { name: 'vendor-notify', filterType: 'job.assigned.v1' }
  { name: 'outcome-capture', filterType: 'job.completed.v1' }
]

resource subscriptions 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2023-01-01-preview' = [for sub in subscriptionDefs: {
  parent: jobLifecycleTopic
  name: sub.name
  properties: {
    requiresSession: true
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    defaultMessageTimeToLive: 'P1D'
  }
}]

resource subscriptionFilters 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2023-01-01-preview' = [for (sub, i) in subscriptionDefs: {
  name: '${sub.name}-filter'
  parent: subscriptions[i]
  properties: {
    filterType: 'SqlFilter'
    sqlFilter: { sqlExpression: 'type = \'${sub.filterType}\'' }
  }
}]

// ---------------------------------------------------------------------
// Function App - Flex Consumption, Python, HTTP API + Durable saga
// (orchestrator/saga_bp.py). alwaysReady=[] keeps the free grant;
// maximumInstanceCount capped as a spend guardrail.
// ---------------------------------------------------------------------
resource flexPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: flexPlanName
  location: location
  tags: { project: projectTag }
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  properties: { reserved: true }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  tags: { project: projectTag }
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: flexPlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}${deploymentContainerName}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 10
        instanceMemoryMB: 4096
        alwaysReady: []
      }
      runtime: { name: 'python', version: '3.11' }
    }
    siteConfig: {
      cors: {
        allowedOrigins: [
          'http://localhost:5173'
          'http://localhost:3000'
          'https://portal.azure.com'
        ]
        supportCredentials: false
      }
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storageAccount.name }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'SERVICE_BUS_NAMESPACE', value: '${serviceBusNamespace.name}.servicebus.windows.net' }
        { name: 'ServiceBusConnection__fullyQualifiedNamespace', value: '${serviceBusNamespace.name}.servicebus.windows.net' }
        { name: 'SQL_SERVER_FQDN', value: sqlServerFqdn }
        { name: 'SQL_DATABASE_NAME', value: sqlDatabaseName }
        { name: 'ENABLE_LLM_NARRATION', value: string(deployAzureOpenAi) }
        { name: 'AZURE_OPENAI_ENDPOINT', value: deployAzureOpenAi ? openAiAccount!.properties.endpoint : '' }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: 'gpt-4o-mini' }
        { name: 'VENDOR_ACCEPT_TIMEOUT_SECONDS', value: '900' }
        { name: 'DISPATCHER_REVIEW_TIMEOUT_SECONDS', value: '300' }
        { name: 'MAX_RETRY_ATTEMPTS', value: '2' }
        { name: 'STATE_STORE_IMPL', value: 'blob' }
        { name: 'STORAGE_ACCOUNT_NAME', value: storageAccount.name }
        { name: 'STATE_CONTAINER', value: 'state' }
        { name: 'AUDIT_CONTAINER', value: 'audit' }
      ]
    }
  }
}

// RBAC, not connection strings: the Function App's identity gets exactly
// the roles it needs, nothing more.
resource storageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, 'StorageBlobDataOwner')
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b') // Storage Blob Data Owner
  }
}

resource storageQueueRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, 'StorageQueueDataContributor')
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88') // Storage Queue Data Contributor
  }
}

resource storageTableRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, 'StorageTableDataContributor')
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3') // Storage Table Data Contributor
  }
}

resource serviceBusRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(serviceBusNamespace.id, functionApp.id, 'ServiceBusDataOwner')
  scope: serviceBusNamespace
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '090c5cfd-751d-490a-894a-3ce6f1109419') // Azure Service Bus Data Owner
  }
}

resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, functionApp.id, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
  }
}

// ---------------------------------------------------------------------
// Azure ML workspace - model registry only (register LightGBM v1/v2 as
// versioned MLflow models). No compute cluster, no online endpoint here.
// ---------------------------------------------------------------------
resource amlStorageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: amlStorageAccountName
  location: location
  tags: { project: projectTag }
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

resource amlWorkspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: amlWorkspaceName
  location: location
  tags: { project: projectTag }
  identity: { type: 'SystemAssigned' }
  properties: {
    friendlyName: 'RetailFixIt Vendor Uplift'
    storageAccount: amlStorageAccount.id
    keyVault: keyVault.id
    applicationInsights: appInsights.id
    // No `Microsoft.MachineLearningServices/workspaces/onlineEndpoints`
    // resource in this template on purpose - see
    // infra/modules/aml-online-endpoint.bicep for why, with the cost math.
  }
}

// ---------------------------------------------------------------------
// Azure OpenAI - gpt-4o-mini, Global Standard, optional narration only.
// deployAzureOpenAi=false keeps this template deployable even before
// 
// ---------------------------------------------------------------------
resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = if (deployAzureOpenAi) {
  name: openAiAccountName
  location: location
  tags: { project: projectTag }
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: openAiAccountName
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4oMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (deployAzureOpenAi) {
  parent: openAiAccount
  name: 'gpt-4o-mini'
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4o-mini', version: '2024-07-18' }
  }
}

output functionAppName string = functionApp.name
output functionAppPrincipalId string = functionApp.identity.principalId
output serviceBusNamespaceFqdn string = '${serviceBusNamespace.name}.servicebus.windows.net'
output keyVaultName string = keyVault.name
output amlWorkspaceName string = amlWorkspace.name
