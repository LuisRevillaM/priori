# ADR 0007 - Priori Access Boundary

Date: 2026-06-19

Status: Superseded by ADR 0008

## Context

The roadmap described M4 as a Priori adapter milestone. That could imply we expect or already have access to Priori's SDK, APIs, private outputs, credentials, or rights-cleared video assets.

We do not currently treat that access as guaranteed.

## Supersession

ADR 0008 removes provider adapter readiness and Priori integration from this project. The project now ends at an independent pre-meeting demo.

## Historical Decision

M4 is renamed to `Provider Adapter Readiness and Conditional Priori Integration`.

The milestone should first define a provider capability contract, adapter conformance tests, and a fixture-backed reference adapter. A real Priori adapter is implemented only if Priori SDK/API/output access exists.

Without Priori access, M4 can still produce:

```text
provider capability schema
adapter input/output contract
fixture-backed reference adapter
conformance tests
documentation for required Priori fields
```

It must not claim a Priori integration without real Priori artifacts.

## Historical Consequences

- The roadmap no longer assumes Priori access.
- Provider-readiness work can proceed without blocked credentials.
- A real Priori adapter remains a conditional branch, not a guaranteed milestone output.
- Production deployment, customer-facing auth, private data handling, and rights-cleared video require explicit owner approval.
