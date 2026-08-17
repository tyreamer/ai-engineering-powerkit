# Material-assumption test

A missing choice is material when a wrong choice could change one or more of:

- Architecture or service boundaries
- Public API, schema, persistence, or migration behavior
- Authentication, authorization, secrets, privacy, or retention
- User-visible behavior or a major UX direction
- External vendor, paid service, licensing, or operational cost
- Backward compatibility, deployment, rollback, or irreversible data changes
- The requested feature's actual scope

When the impact is local, reversible, conventional, and consistent with repository evidence, prefer a safe default.
