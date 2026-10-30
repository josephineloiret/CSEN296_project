# Python dependencies

| File | Purpose |
| --- | --- |
| `lock.txt` | Pinned runtime and test dependencies used by the launcher, container and CI |
| `runtime.txt` | Runtime dependency ranges |
| `dev.txt` | Runtime ranges plus test dependencies; references `runtime.txt` |

For the reproducible project environment, run from the repository root:

```sh
.venv/bin/python -m pip install -r requirements/lock.txt
```

See [local development](../docs/local-development.md) for setup and test commands.
