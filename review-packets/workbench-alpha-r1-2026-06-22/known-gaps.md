# Known Gaps

## not_in_scope: Cache Implementation

Execution caching was not implemented in R1. The current packet records execution latency and defines a cache/progress plan in `docs/performance-cache-plan.md`. Default boundary: users should expect long-running real host execution for approved and experimental journeys until Integrated Alpha adds cache/progress behavior.

## not_in_scope: Final Visual Polish

R1 intentionally avoids final visual polish. Default boundary: the UI is validated for functional acceptance, replay correctness, and state visibility, not final presentation quality.

## not_in_scope: S3 Feedback And Revision Behavior

No S3 feedback/revision loop was added. Default boundary: Workbench Alpha can run accepted/manual paths and expose validation states, but does not support iterative plan revision.

## requires_full_repo: Reproduction

This is an inspection packet, not a self-contained runnable bundle. Reproducing validation requires the full repository, local canonical data, Python environment, Node dependencies, and browser tooling.

## unknown: npm Low-Severity Advisory

`npm audit` reports one low-severity advisory. It was recorded but not fixed because dependency remediation was outside the required R1 scope.

## not_in_scope: Browser-To-MCP And Second Tactical Family

The browser still talks only to the host application service. It does not call MCP, and no second tactical family or new primitive implementation was added.
