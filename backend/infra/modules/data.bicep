// Deploys into rg-retailfixit-data (persistent - never deleted).
// Azure SQL free-tier server/database + the audit Storage Account.
// Deploy: az deployment group create -g rg-retailfixit-data -f infra/modules/data.bicep
//
// SQL free-tier note: the free-offer region is locked permanently on
// first create for the whole subscription - pick `location` deliberately.
targetScope = 'resourceGroup'

@description('Region for the data resource group. Locked in permanently by the SQL free offer on first create.')
param location string = resourceGroup().location

@description('SQL admin login. Password is generated and stored to Key Vault by a post-deploy step (not embedded in this template).')
param sqlAdminLogin string = 'retailfixitadmin'

@secure()
param sqlAdminPassword string

param projectTag string = 'retailfixit'

var sqlServerName = 'sql-retailfixit-${uniqueString(resourceGroup().id)}'
var sqlDbName = 'retailfixit'
var storageAccountName = 'strfitdata${uniqueString(resourceGroup().id)}'

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: sqlServerName
  location: location
  tags: { project: projectTag }
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
  }
}

// Serverless GP tier, free offer: auto-pauses after 1hr idle. Do not
// leave a client connection open in code/tests - it blocks auto-pause
// and the free-tier hours reset monthly, not accumulate.
resource sqlDb 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: sqlDbName
  location: location
  tags: { project: projectTag }
  sku: {
    name: 'GP_S_Gen5'
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 1
  }
  properties: {
    autoPauseDelay: 60
    minCapacity: json('0.5')
    useFreeLimit: true
    freeLimitExhaustionBehavior: 'AutoPause'
  }
}

// Allow Azure services (the Function App's outbound) through the firewall.
// Hardening note: a real production deployment would use a Private
// Endpoint here instead (see README "What Runs vs. What Is Documented").
resource allowAzureServices 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: { project: projectTag }
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

// ScoreFactors audit documents - immutable, append-only (no delete/update
// role assigned to the app's managed identity; enforced via RBAC role
// assignment in app.bicep, not by a container-level ACL here).
resource scoreFactorsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'score-factors'
  properties: { publicAccess: 'None' }
}

resource rawEventLogContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'raw-event-log'
  properties: { publicAccess: 'None' }
}

resource trainingSnapshotsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'training-snapshots'
  properties: { publicAccess: 'None' }
}

output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDb.name
output storageAccountName string = storageAccount.name
