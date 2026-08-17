---
name: change-impact-analysis
description: "Analyzes blast radius before a significant change. Use for architecture, shared libraries, schemas, auth, events, public APIs, data flows, cross-service behavior, or any modification where hidden consumers and operational effects matter."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: delivery
---

# Change Impact Analysis

## Purpose

Identify what can break, who depends on it, and what safeguards are required before implementation.

## Impact dimensions

Inspect applicable dimensions:

- Callers, consumers, integrations, and generated clients.
- Public and internal APIs, events, schemas, and versioning.
- Persistence, migrations, backfills, retention, and data ownership.
- Authentication, authorization, secrets, tenancy, and audit.
- UI states, accessibility, localization, and user expectations.
- Caching, retries, idempotency, concurrency, and ordering.
- Performance, capacity, rate limits, and cost.
- Configuration, feature flags, deployment order, and rollback.
- Observability, alerts, dashboards, and support procedures.
- Tests, fixtures, examples, SDKs, and documentation.
- Compliance, privacy, licensing, and vendor constraints.

## Method

1. Trace current producers and consumers using code search and runtime configuration.
2. Inspect contract definitions and test fixtures.
3. Check Git history or issue context for compatibility constraints.
4. Separate direct impact from plausible second-order impact.
5. Rate severity and likelihood.
6. Define prevention, detection, containment, and rollback for material risks.
7. Identify required sequencing across repositories or services.

## Output

Produce a compact impact map:

- Affected area.
- Evidence.
- Failure mode.
- Severity and likelihood.
- Required mitigation or proof.
- Owner or dependency when known.

Lead with the highest-risk findings. Do not create a generic checklist detached from the actual change.

## Rules

- “Internal” does not mean “no consumers.”
- Treat data and auth changes as high risk until disproven.
- Do not confuse file count with blast radius.
- Mark uncertain impact as an investigation item rather than a fact.
