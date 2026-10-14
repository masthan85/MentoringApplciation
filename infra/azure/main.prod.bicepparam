using './main.bicep'

param environment = 'prod'
param location = 'uksouth'
param postgresAdminPassword = readEnvironmentVariable('POSTGRES_ADMIN_PASSWORD')
param authIssuer = 'https://your-tenant.eu.auth0.com/'
param authAudience = 'https://api.your-domain.example'
param authJwksUrl = 'https://your-tenant.eu.auth0.com/.well-known/jwks.json'
param publicWebUrl = 'https://app.your-domain.example'
param billingEnabled = false
