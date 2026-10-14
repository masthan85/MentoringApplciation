// Azure infrastructure for the Mentor platform, UK South.
//
// NOT VALIDATED: this was written without the Azure CLI or the Bicep compiler available, so it has
// never been compiled or deployed. Run `az bicep build --file main.bicep` and
// `az deployment group what-if` first, and read docs/deployment.md.
//
//   az group create -n mentor-prod -l uksouth
//   az deployment group create -g mentor-prod -f main.bicep -p main.prod.bicepparam

targetScope = 'resourceGroup'

@description('Short environment name, used in resource names.')
@allowed(['staging', 'prod'])
param environment string = 'prod'

param location string = 'uksouth'

@description('Name of the container registry that holds the images (created here).')
param registryName string = 'mentor${environment}${uniqueString(resourceGroup().id)}'

@description('Image tag to deploy for api, worker and web.')
param imageTag string = 'latest'

@description('PostgreSQL administrator name. The app uses its own roles; see docs/deployment.md.')
param postgresAdminLogin string = 'mentoradmin'

@secure()
@description('PostgreSQL administrator password. Pass it at deploy time; it is also stored in Key Vault.')
param postgresAdminPassword string

@description('Public URL of the web app, for CORS and email links. Set after the first deploy if you use the generated hostname.')
param publicWebUrl string = ''

@description('OIDC issuer, audience and JWKS URL of the identity provider (Auth0, Clerk or Entra External ID).')
param authIssuer string
param authAudience string
param authJwksUrl string

@description('Turn on Stripe billing. Needs the Stripe secrets in Key Vault.')
param billingEnabled bool = false

var prefix = 'mentor-${environment}'
var tags = {
  app: 'mentor'
  environment: environment
}

// ---- observability ---------------------------------------------------------------------

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ---- identity and secrets --------------------------------------------------------------

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id'
  location: location
  tags: tags
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('${prefix}-kv-${uniqueString(resourceGroup().id)}', 24)
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
  }
}

// Key Vault Secrets User for the app identity.
resource vaultReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, 'secrets-user')
  scope: vault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource pgPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'postgres-admin-password'
  properties: { value: postgresAdminPassword }
}

// ---- data ------------------------------------------------------------------------------

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: '${prefix}-pg-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  sku: {
    name: environment == 'prod' ? 'Standard_D2ds_v5' : 'Standard_B2s'
    tier: environment == 'prod' ? 'GeneralPurpose' : 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 64 }
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Disabled' // keep data in the UK; turn on only if a UK paired region is acceptable
    }
    highAvailability: { mode: 'Disabled' }
    authConfig: { passwordAuth: 'Enabled', activeDirectoryAuth: 'Disabled' }
  }
}

resource pgExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: postgres
  name: 'azure.extensions'
  properties: { value: 'VECTOR', source: 'user-override' }
}

resource pgDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgres
  name: 'mentor'
  dependsOn: [pgExtensions]
}

// Allow Azure services (the Container Apps environment) to connect. Tighten with a VNet before
// handling real user data; see docs/deployment.md.
resource pgAzureAccess 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: '${prefix}-redis-${uniqueString(resourceGroup().id)}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'Basic', family: 'C', capacity: 0 }
    minimumTlsVersion: '1.2'
    enableNonSslPort: false
  }
}

// ---- images and hosting ----------------------------------------------------------------

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'acr-pull')
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// Secret values are read from Key Vault by the app identity. Create these secrets before the
// first deployment of the apps (see docs/deployment.md): database-url, migration-database-url,
// sensitive-data-key, anthropic-api-key, openai-api-key, and (billing) stripe-* values.
var kvUri = vault.properties.vaultUri
var secretRefs = [
  { name: 'database-url', keyVaultUrl: '${kvUri}secrets/database-url', identity: identity.id }
  { name: 'migration-database-url', keyVaultUrl: '${kvUri}secrets/migration-database-url', identity: identity.id }
  { name: 'sensitive-data-key', keyVaultUrl: '${kvUri}secrets/sensitive-data-key', identity: identity.id }
  { name: 'anthropic-api-key', keyVaultUrl: '${kvUri}secrets/anthropic-api-key', identity: identity.id }
  { name: 'openai-api-key', keyVaultUrl: '${kvUri}secrets/openai-api-key', identity: identity.id }
  { name: 'redis-url', keyVaultUrl: '${kvUri}secrets/redis-url', identity: identity.id }
]

var registryConfig = [
  { server: registry.properties.loginServer, identity: identity.id }
]

var commonEnv = [
  { name: 'ENV', value: environment == 'prod' ? 'production' : 'staging' }
  { name: 'LOG_LEVEL', value: 'INFO' }
  { name: 'AUTH_MODE', value: 'oidc' }
  { name: 'AUTH_ISSUER', value: authIssuer }
  { name: 'AUTH_AUDIENCE', value: authAudience }
  { name: 'AUTH_JWKS_URL', value: authJwksUrl }
  { name: 'JOBS_MODE', value: 'arq' }
  { name: 'PUBLIC_WEB_URL', value: publicWebUrl }
  { name: 'BILLING_ENABLED', value: string(billingEnabled) }
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'REDIS_URL', secretRef: 'redis-url' }
  { name: 'SENSITIVE_DATA_KEY', secretRef: 'sensitive-data-key' }
  { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' }
  { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
]

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-api'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
      registries: registryConfig
      secrets: secretRefs
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${registry.properties.loginServer}/mentor-api:${imageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(commonEnv, [
            { name: 'CORS_ORIGINS', value: '["${publicWebUrl}"]' }
          ])
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 8000 }, periodSeconds: 20 }
            { type: 'Readiness', httpGet: { path: '/readyz', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 4, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '40' } } }] }
    }
  }
  dependsOn: [vaultReader, acrPull]
}

resource worker 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-worker'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      registries: registryConfig
      secrets: secretRefs
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${registry.properties.loginServer}/mentor-api:${imageTag}'
          command: ['sh', '-c', 'cd /srv/apps/worker && arq worker.main.WorkerSettings']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: commonEnv
        }
      ]
      // One worker: the scheduler job runs hourly and must not run twice at once.
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
  dependsOn: [vaultReader, acrPull]
}

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-web'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: { external: true, targetPort: 3000, transport: 'auto', allowInsecure: false }
      registries: registryConfig
    }
    template: {
      containers: [
        {
          name: 'web'
          image: '${registry.properties.loginServer}/mentor-web:${imageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'API_INTERNAL_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: 3000 }, periodSeconds: 20 }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [acrPull]
}

// A one-off job that applies database migrations; run it before each release.
resource migrate 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-migrate'
  location: location
  tags: tags
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: registryConfig
      secrets: secretRefs
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: '${registry.properties.loginServer}/mentor-api:${imageTag}'
          command: ['alembic', 'upgrade', 'head']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'ENV', value: environment == 'prod' ? 'production' : 'staging' }
            { name: 'MIGRATION_DATABASE_URL', secretRef: 'migration-database-url' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'SENSITIVE_DATA_KEY', secretRef: 'sensitive-data-key' }
            { name: 'AUTH_MODE', value: 'oidc' }
            { name: 'AUTH_ISSUER', value: authIssuer }
            { name: 'AUTH_AUDIENCE', value: authAudience }
            { name: 'AUTH_JWKS_URL', value: authJwksUrl }
          ]
        }
      ]
    }
  }
  dependsOn: [vaultReader, acrPull]
}

output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output webUrl string = 'https://${web.properties.configuration.ingress.fqdn}'
output registryLoginServer string = registry.properties.loginServer
output keyVaultName string = vault.name
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output redisHost string = redis.properties.hostName
