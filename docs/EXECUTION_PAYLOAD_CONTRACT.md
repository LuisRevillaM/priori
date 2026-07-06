# Execution Payload Contract

SEAM-1 names the execution payload chain so consumers do not infer evidence
location from an empty object.

## Host call chain

1. `submit_query_plan` accepts a `TacticalQueryDocument` and writes a draft-plan
   handle.
2. `validate_query_plan` binds the draft plan, checks host safety, and writes a
   bound-plan handle. It does not execute the plan.
3. `host_confirm_bound_plan` writes the host-owned execution authorization for a
   specific bound-plan hash.
4. `execute_query_plan` runs the deterministic runtime and returns a bounded
   ranked response. The complete stored execution record is written under the
   execution handle and is the source of truth for inspection.

## Evidence locations

`ExecuteQueryPlanResponse.results` is a ranked, result-limited response. A row
contains `requested_evidence` only when evidence values are projected for that
returned row. If no row-level requested evidence is projected, the response row
must contain `evidence_contract` instead of `requested_evidence: {}`.

The full stored execution record contains:

- `rows`: unranked stored result rows with projected `requested_evidence`.
- `execution.results[*].evidence`: runtime result evidence as emitted by the
  deterministic executor.
- `execution.provenance.requested_evidence_sources`: per-period summaries of
  requested source outputs. Rate interval consumers use these summaries for
  full declared partitions, not the ranked response order.
- `predicate_traces`: predicate-level traces for result inspection.

`inspect_result` returns the stored row, predicate traces for that row, and the
row's `requested_evidence`. Replay windows are fetched separately by
`retrieve_replay_window`.

## Film Room Counts

`moment_total_count` is the number of distinct Film Room moment rows assembled
for replay/overlay display from the evidence available to the response. It is
not the rate denominator and is not a population count.

Rate population and interval counts come from the declared rate partition:
`a_count`, `b_count`, `c_count`, `d1_count`, `d2_count`, and `e_count`, with
the denominator label derived from `denominator_status_field`. For the
counterattack flagship, `denominator_status_field=stage_1_status`, so the
label is `per regain start`.
