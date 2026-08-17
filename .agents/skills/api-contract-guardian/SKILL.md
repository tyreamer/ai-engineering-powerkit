---
name: api-contract-guardian
description: "Protects API, event, schema, and SDK compatibility. Use when changing request or response fields, semantics, status codes, events, generated clients, validation, versioning, or behavior consumed outside the immediate module."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: quality
---

# API Contract Guardian

## Purpose

Treat contracts as behavior shared with consumers, not merely types that compile.

## Contract surface

Inspect:

- Request and response shape.
- Field meaning, nullability, defaults, and units.
- Status codes and error body semantics.
- Validation and coercion.
- Ordering, pagination, filtering, and idempotency.
- Event names, keys, delivery guarantees, and replay.
- Schema registry or generated clients.
- Version negotiation and deprecation.
- Documentation, examples, fixtures, and consumer tests.

## Method

1. Locate the source of truth for the contract.
2. Find known consumers and generated artifacts.
3. Compare current and proposed semantics.
4. Classify changes as compatible, conditionally compatible, or breaking.
5. Design an expansion or versioning strategy for breaking changes.
6. Add contract tests and mixed-version cases.
7. Update documentation and deprecation signals.
8. Verify deployment order.

## Compatibility traps

- Making an optional field required.
- Changing a default without changing the schema.
- Reusing a field name with a new meaning.
- Changing error codes or retry semantics.
- Narrowing accepted inputs.
- Removing enum values.
- Changing numeric units or precision.
- Assuming consumers ignore unknown fields.
- Updating producers before readers can accept the new shape.

## Output

State:

- Contract change.
- Consumers and evidence.
- Compatibility classification.
- Migration/versioning plan.
- Required tests.
- Deployment order and rollback.
