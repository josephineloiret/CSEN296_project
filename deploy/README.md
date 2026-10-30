# Deployment files

Use the [Railway runbook](../docs/railway-deployment.md) for deploy commands and
runtime requirements. Build the application from the repository root.

| File | Purpose |
| --- | --- |
| `railway.env.example` | Nonsecret service-variable template; set API keys separately |
| `railway-project.json` | Project and service identifiers |
| `railway-service-settings.json` | Service configuration snapshot |
| `railway-service.graphql` | Service configuration query |
| `verify_public.py` | Credential-free HTTPS, health and access-boundary checks |

The root `Dockerfile` and `entrypoint.py` build and start the container. Source
configuration snapshots do not assert the current deployment's health.
