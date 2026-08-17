# Focused threat prompts

Use only where relevant:

- Can the caller choose or forge identity, tenant, role, resource owner, or tool name?
- Does any client-side check stand in for server enforcement?
- Can untrusted content influence shell, SQL, file path, URL fetch, template, prompt, or privileged tool input?
- Are secrets or personal data copied into logs, telemetry, cache, generated files, screenshots, or error responses?
- Can retries, replay, concurrency, or partial failure duplicate a privileged action?
- Can a dependency or repository-provided hook execute code before trust is established?
- Can data be deleted from primary storage but survive indefinitely in indexes, exports, or backups?
