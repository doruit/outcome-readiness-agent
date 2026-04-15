# Security Policy

## Sensitive files — never commit these

| File | Contents |
|---|---|
| `.env` | Foundry endpoint, model deployment name, App Insights connection string |
| `runs.db` | May contain engagement names and SoW summaries |

Both are in `.gitignore`. Before pushing, verify nothing sensitive is staged:

```bash
git status
git diff --cached
```

---

## Environment variables

All secrets are managed via `.env` (local only) and should be rotated via Azure portal if compromised:

| Variable | How to rotate |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | No secret — it's an endpoint URL, but scope access via Azure RBAC |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Azure portal → Application Insights → regenerate instrumentation key |

Access to the Foundry project and Application Insights is governed by **Azure RBAC** via `DefaultAzureCredential`. No passwords or API keys are used directly — authentication relies on your `az login` session or a managed identity.

---

## Reporting a vulnerability

Please do not open a public GitHub issue for security concerns. Contact the repository owner directly.
