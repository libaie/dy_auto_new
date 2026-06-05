# AGENTS.md

<!-- BEGIN CODEX EVERCORE MEMORY -->
## Codex EverCore Memory

This project has a local EverCore memory helper:

```powershell
.\tools\evercore-memory.ps1 health -BaseUrl "http://localhost:1995"
.\tools\evercore-memory.ps1 search "query text" -BaseUrl "http://localhost:1995" -GroupId "dy_auto"
.\tools\evercore-memory.ps1 save "short durable summary" -BaseUrl "http://localhost:1995" -GroupId "dy_auto"
.\tools\evercore-memory.ps1 flush -BaseUrl "http://localhost:1995" -GroupId "dy_auto"  # only after provider keys are configured
```

Use it conservatively:

- At the start of a non-trivial task, search memory only when prior context could matter.
- At the end of setup, debugging, or implementation work, save a concise summary containing durable decisions, commands, and fixes.
- Do not save secrets, API keys, credentials, private tokens, or large logs.
- Keep summaries short and specific to this project.
- This project uses fixed EverCore memory group `dy_auto`.
<!-- END CODEX EVERCORE MEMORY -->
