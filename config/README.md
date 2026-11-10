# Local configuration

Copy the template from the repository root:

```sh
cp config/local.env.example .env
```

Edit the ignored root `.env` for local settings. The app loads it relative to the
repository root, independent of where its utility modules live. Default local
simulation needs no API key.

See [setup and configuration](../docs/setup-and-deployment.md) for provider keys,
budgets and production settings. Railway's separate nonsecret template lives in
[`deploy/railway.env.example`](../deploy/railway.env.example).
