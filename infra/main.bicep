/*
  Outcome Readiness Agents — Foundry + Container Apps infrastructure
  ------------------------------------------------------------------
  Resources:
    • Microsoft.CognitiveServices/accounts      (Foundry — AIServices)
    • .../accounts/projects                     (Foundry project)
    • .../accounts/deployments                  (gpt-4o model)
    • Microsoft.ContainerRegistry/registries    (ACR — image source)
    • Microsoft.ManagedIdentity/userAssignedIdentities (workload identity)
    • Role assignments: ACR Pull, Cognitive Services User, Azure AI Developer
    • Microsoft.Storage/storageAccounts + fileServices/shares (SQLite persistence)
    • Microsoft.OperationalInsights/workspaces  (Log Analytics)
    • Microsoft.App/managedEnvironments         (Container Apps env)
    • Microsoft.App/containerApps               (dashboard + both agents, 1 image)

  Existing App Insights `appi-outcome-readiness` is referenced (not created).
*/

param location string = resourceGroup().location

// ── Foundry
param aiFoundryName string      = 'aif-outcome-readiness'
param aiProjectName string      = 'outcome-readiness-project'
param modelName string          = 'gpt-4o'
param modelVersion string       = '2024-11-20'
param modelSkuName string       = 'GlobalStandard'
param modelCapacity int         = 10

// ── App
param appName string            = 'outcome-readiness'
param imageTag string           = 'latest'

// Phase switch:
//   false → deploy only ACR + UAMI + role assignments + storage + log + env
//           (use before the image has been pushed for the first time)
//   true  → also deploy the Container App (requires the image to exist in ACR)
param deployApp bool            = true

// Existing App Insights (already deployed separately)
param appInsightsName string    = 'appi-outcome-readiness'

// Derived unique names
var suffix              = take(uniqueString(resourceGroup().id), 6)
var acrName             = 'acr${replace(appName, '-', '')}${suffix}'
var storageName         = 'st${replace(appName, '-', '')}${suffix}'
var logWorkspaceName    = 'log-${appName}'
var envName             = 'cae-${appName}'
var uamiName            = 'uami-${appName}'
var containerAppName    = 'ca-${appName}'
var fileShareName       = 'runsdb'
var storageLinkName     = 'runsdb-share'

// ── Existing App Insights (read-only reference) ───────────────────────────
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// ── Foundry Account (AIServices) ──────────────────────────────────────────
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiFoundryName
  location: location
  identity: { type: 'SystemAssigned' }
  sku: { name: 'S0' }
  kind: 'AIServices'
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiFoundryName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiFoundry
  name: aiProjectName
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    displayName: 'Outcome Readiness Agent'
    description: 'Outcome-based commercial model readiness reviews for Contoso engagements'
  }
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: modelName
  sku: { name: modelSkuName, capacity: modelCapacity }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// ── User-Assigned Managed Identity (workload) ─────────────────────────────
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
}

// ── Azure Container Registry ─────────────────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
  }
}

// AcrPull so the Container App can pull images using its UAMI
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uami.id, 'AcrPull')
  scope: acr
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

// Cognitive Services User on the Foundry account
resource cogSvcUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundry.id, uami.id, 'CognitiveServicesUser')
  scope: aiFoundry
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
  }
}

// Azure AI Developer on the Foundry account (project/agent operations)
resource aiDeveloperRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiFoundry.id, uami.id, 'AzureAIDeveloper')
  scope: aiFoundry
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee')
  }
}

// ── Storage Account + File Share (SQLite persistence) ────────────────────
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileService
  name: fileShareName
  properties: {
    accessTier: 'TransactionOptimized'
    shareQuota: 5
  }
}

// ── Log Analytics ────────────────────────────────────────────────────────
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ── Container Apps Environment ───────────────────────────────────────────
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logWorkspace.properties.customerId
        sharedKey: logWorkspace.listKeys().primarySharedKey
      }
    }
  }
}

// Attach the Azure Files share to the environment
resource caeStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: storageLinkName
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: fileShareName
      accessMode: 'ReadWrite'
    }
  }
  dependsOn: [ fileShare ]
}

// ── Container App (dashboard + scan agent + intake agent in one image) ───
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = if (deployApp) {
  name: containerAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 5050
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: uami.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: '${acr.properties.loginServer}/${appName}:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            { name: 'PORT',                                value: '5050' }
            { name: 'HOST',                                value: '0.0.0.0' }
            { name: 'SCAN_AGENT_PORT',                     value: '8088' }
            { name: 'INTAKE_AGENT_PORT',                   value: '8087' }
            { name: 'DB_PATH',                             value: '/data/runs.db' }
            { name: 'AGENT_NAME',                          value: 'outcome-readiness-agent' }
            { name: 'INTAKE_AGENT_NAME',                   value: 'intake-agent' }
            { name: 'MAX_HOURS_SAVED',                     value: '8.0' }
            { name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME',       value: modelName }
            { name: 'FOUNDRY_PROJECT_ENDPOINT',            value: '${aiFoundry.properties.endpoint}api/projects/${aiProject.name}' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'AZURE_CLIENT_ID',                     value: uami.properties.clientId }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    acrPullRole
    cogSvcUserRole
    aiDeveloperRole
    modelDeployment
  ]
}

// ── Outputs ──────────────────────────────────────────────────────────────
output foundryEndpoint      string = aiFoundry.properties.endpoint
output projectName          string = aiProject.name
output modelDeploymentName  string = modelDeployment.name
output projectEndpoint      string = '${aiFoundry.properties.endpoint}api/projects/${aiProject.name}'

output acrLoginServer       string = acr.properties.loginServer
output acrName              string = acr.name
output uamiClientId         string = uami.properties.clientId

output containerAppName     string = deployApp ? containerApp.name : ''
output containerAppFqdn     string = deployApp ? containerApp!.properties.configuration.ingress.fqdn : ''
output containerAppUrl      string = deployApp ? 'https://${containerApp!.properties.configuration.ingress.fqdn}' : ''
