# Deploying to Azure (UK South)

This describes how to run the platform on Azure Container Apps with PostgreSQL, Redis and Key Vault, all in UK South. **The Bicep in `infra/azure` has never been compiled or deployed.** It was written without the Azure CLI. Treat the first deployment as a rehearsal in a throwaway resource group, and expect to fix small errors.

## What gets created

| Resource | Purpose |
|---|---|
| Container Apps environment, Log Analytics | Hosting and logs |
| `api`, `worker`, `web` container apps | The three processes. The worker is fixed at one replica so the hourly scheduler never runs twice |
| `migrate` job | Applies database migrations, run manually before each release |
| Azure Database for PostgreSQL flexible server 16 | Data. The `vector` extension is allow-listed |
| Azure Cache for Redis | Rate limits, job queue |
| Key Vault (RBAC, purge protection) | Secrets, read by a user-assigned managed identity |
| Container Registry | Images, pulled by the same identity |

## Before you start

1. Decide on an identity provider (Auth0, Clerk or Entra External ID) and have its issuer, audience and JWKS URL. The API refuses to start in production without them.
2. Create a Stripe account and prices only if you want billing. Leave `billingEnabled` false until you do.
3. Get the OpenAI and Anthropic keys (see `docs/adr/0002-llm-gateway.md` for the model routes in `apps/api/app/modules/llm_gateway/routes.yaml`).
4. Install the Azure CLI and Bicep, and sign in.

## Steps

1. **Build and check.** `az bicep build --file infra/azure/main.bicep` and fix anything it reports.
2. **Resource group.** `az group create -n mentor-prod -l uksouth`
3. **Edit** `infra/azure/main.prod.bicepparam` with your identity provider and domain. Then deploy the platform:
   ```
   export POSTGRES_ADMIN_PASSWORD='...'
   az deployment group what-if -g mentor-prod -f infra/azure/main.bicep -p infra/azure/main.prod.bicepparam
   az deployment group create  -g mentor-prod -f infra/azure/main.bicep -p infra/azure/main.prod.bicepparam
   ```
   The apps will not start yet because their secrets do not exist. That is expected.
4. **Database roles.** Edit the passwords in `infra/postgres/production-roles.sql` and run it as the server admin against the `mentor` database.
5. **Secrets.** In the Key Vault, create: `database-url` (`postgresql+asyncpg://mentor_app:...@<host>:5432/mentor?ssl=require`), `migration-database-url` (the same with the `mentor` role), `redis-url` (`rediss://:<key>@<host>:6380/0`), `sensitive-data-key` (a Fernet key, see `.env.example`; **losing it makes sensitive memories unreadable, so back it up**), `anthropic-api-key`, `openai-api-key`. For billing add the Stripe values and set the matching environment variables on the api app.
6. **Images.** Build and push `mentor-api` (from `infra/docker/python.Dockerfile`) and `mentor-web` (from `infra/docker/web.Dockerfile`, with `NEXT_PUBLIC_API_URL` set to the API's public URL at build time) to the registry, then redeploy with `-p imageTag=<tag>`.
7. **Migrate.** `az containerapp job start -g mentor-prod -n mentor-prod-migrate`, and wait for it to succeed.
8. **Check.** Open the web URL, sign in, finish onboarding, send a message. Check `/readyz` on the API.

## Things to do before real users

- Put the database and Redis behind a virtual network and private endpoints. The template allows "Azure services" through the database firewall, which is convenient and too open for production.
- Add a custom domain and managed certificate to the web and API apps, set `PUBLIC_WEB_URL` and `CORS_ORIGINS` to match, and rebuild the web image with the final API URL.
- Set up alerts on the API's error rate and latency, and on the database's storage and CPU.
- Decide how long to keep logs and backups, and write it into the privacy policy. Backups are 14 days; geo-redundant backup is off to keep data in the UK.
- Run the full evaluation (`make eval-full`) against the real models and have a qualified person review the safety wording, the mentor packs and the starter content.
- Stripe: create the two products, set the webhook endpoint to `https://<api>/v1/billing/webhook`, and send a test event from the Stripe dashboard.
- Rehearse restoring the database from a backup.

## Rolling back

Container Apps keeps previous revisions. Re-point traffic to the last good revision for the api, worker and web. Migrations are not automatically reversible; take a database backup immediately before running the migrate job.
