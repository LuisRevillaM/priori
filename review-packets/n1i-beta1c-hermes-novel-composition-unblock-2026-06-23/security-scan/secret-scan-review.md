# Secret Scan Review

The broad secret-pattern scan produced matches. I reviewed the hits. They are source-code references to environment variable names, test IDs such as `path-ask-hermes`, and safety-test marker strings such as `OPENAI_API_KEY` / `sk-`.

No literal credential value, private key, API key, bearer token, or raw `.env` file is included in this packet.

Primary reviewed hits:

- `src/tqe/workshop/app_service.py` references `DEMO_ACCESS_TOKEN` and `N1E_RUN_TOKEN` via `os.environ.get(...)`; values are not present.
- `src/tqe/workshop/knowledge_pack.py` contains forbidden-marker strings used by safety checks.
- Workbench test IDs contain `ask-hermes`, which matched the loose `sk-` pattern inside `ask-hermes`; this is not a secret.
