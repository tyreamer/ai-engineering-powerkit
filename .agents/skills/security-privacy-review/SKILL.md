---
name: security-privacy-review
description: "Reviews code or plans for authentication, authorization, secrets, data exposure, tenancy, retention, injection, supply-chain, and abuse risks. Use whenever a change touches identities, permissions, external input, sensitive data, persistence, integrations, or privileged tools."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: quality
---

# Security and Privacy Review

## Purpose

Find concrete security and privacy failures early without substituting a generic checklist for threat modeling.

## Start with boundaries

Identify:

- Assets and sensitive data.
- Actors and trust levels.
- Entry points and untrusted input.
- Authentication and authorization decisions.
- Service, tenant, and user boundaries.
- Storage, logs, caches, exports, and retention.
- External tools, dependencies, webhooks, and callbacks.
- Privileged actions and destructive operations.

## Review areas

Inspect applicable risks:

- Broken object- or function-level authorization.
- Confused deputy and caller-supplied identity or role context.
- Missing server-side validation.
- Injection into shell, SQL, templates, prompts, paths, or URLs.
- Secret exposure in source, logs, errors, build output, or client bundles.
- Cross-tenant data leakage and cache-key mistakes.
- Unsafe deserialization, file handling, redirects, or SSRF.
- Replay, idempotency, CSRF, webhook verification, and race conditions.
- Excessive collection, unclear purpose, retention, deletion, and backup behavior.
- Dependency provenance, install scripts, and compromised tooling.
- Model/tool prompt injection and untrusted content crossing into privileged actions.
- Missing audit, rate limiting, abuse controls, and incident visibility.

## Method

1. Trace the real authorization and data path.
2. Build plausible abuse cases.
3. Verify controls in the enforcement layer, not only UI.
4. Review failure behavior and logs.
5. Rank findings by exploitability and impact.
6. Recommend the smallest effective remediation and proof.
7. Mark regulatory conclusions as requiring qualified review when applicable.

## Output

For each finding:

- Severity.
- Asset and threat.
- Evidence.
- Exploit or failure path.
- Remediation.
- Verification.

Do not report hypothetical scanner noise as a confirmed vulnerability.
