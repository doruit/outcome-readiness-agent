/*
  Outcome Readiness Agent — Microsoft Foundry Infrastructure
  -----------------------------------------------------------
  Resources created:
    - Microsoft.CognitiveServices/accounts  (Foundry resource, kind=AIServices)
    - Microsoft.CognitiveServices/accounts/projects  (Foundry project)
    - Microsoft.CognitiveServices/accounts/deployments  (gpt-4o model)

  The existing rg-outcome-readiness-agent resource group is used.
  Application Insights was already created separately (appi-outcome-readiness).
*/

param location string = 'swedencentral'

// Reuse the account we already created
param aiFoundryName string = 'aif-outcome-readiness'

param aiProjectName string = 'outcome-readiness-project'

param modelName string = 'gpt-4o'
param modelVersion string = '2024-11-20'
param modelSkuName string = 'GlobalStandard'
param modelCapacity int = 10

// ── Foundry Account (AIServices) ──────────────────────────────────────────
resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiFoundryName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiFoundryName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// ── Foundry Project (child of AIServices account) ─────────────────────────
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiFoundry
  name: aiProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Outcome Readiness Agent'
    description: 'Outcome-based commercial model readiness reviews for Contoso engagements'
  }
}

// ── Model Deployment ──────────────────────────────────────────────────────
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: modelName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────
output foundryEndpoint string = aiFoundry.properties.endpoint
output projectName string = aiProject.name
output modelDeploymentName string = modelDeployment.name

// Project endpoint format for the SDK:
// https://<account>.cognitiveservices.azure.com/api/projects/<project>
output projectEndpoint string = '${aiFoundry.properties.endpoint}api/projects/${aiProject.name}'
