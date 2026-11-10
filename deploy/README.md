# Deployment files

Use the [Railway runbook](../docs/railway-deployment.md) for deploy commands and
runtime requirements. Build the application from the repository root.

| File | Purpose |
| --- | --- |
| `Dockerfile` | Container build; use `docker build -f deploy/Dockerfile .` from the root |
| `Dockerfile.dockerignore` | Build-context exclusions for this Dockerfile |
| `entrypoint.py` | Volume ownership, privilege drop and single-worker startup |
| `railway.env.example` | Nonsecret service-variable template; set API keys separately |
| `railway-project.json` | Project and service identifiers |
| `railway-service-settings.json` | Service configuration snapshot |
| `railway-service.graphql` | Service configuration query |
| `verify_public.py` | Credential-free HTTPS, health and access-boundary checks |

Use `deploy/Dockerfile` with the repository root as the build context. For
Railway, set `RAILWAY_DOCKERFILE_PATH=deploy/Dockerfile` in service variables. Source
configuration snapshots do not assert the current deployment's health.
