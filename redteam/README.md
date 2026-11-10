# Synthetic attack campaign

Run from the repository root:

```sh
.venv/bin/python redteam/run_campaign.py --out redteam/results/campaign-local.json
```

The default mode uses local simulation, temporary databases and synthetic
fixtures. Scenarios cover a normal refund, direct injection, poisoned documents,
expired-purchase overrides, revoked authority and replay. Inspect the scenario
results and trusted ledger outcomes in the generated JSON.

Generated results are ignored by Git. The campaign does not target the hosted
service or use production customer data.

Live mode requires explicit `--live`, provider configuration and an API key in
the environment; it shares a $0.15 budget across scenarios. See
[configuration](../docs/setup-and-deployment.md) before making paid calls.
The isolated in-app control checks are described in the
[user guide](../docs/user-guide.md).
