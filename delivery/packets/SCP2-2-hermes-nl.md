# Work Packet SCP2-2: Hermes — natural language to meaning expression

**Era**: SCP-2 bridge, model side (ADR 0015 governs; principles 23-25
are the law of this packet)
**Branch**: `packet/scp2-2` off the frontier
**Executor ground rules**: unchanged (stage-committed report at
`delivery/packets/SCP2-2-REPORT.md`; full-suite table on the committed
tree; commit locally, never push; deviation law: STOP, flag, request
ratification).

**Fences**: unchanged (ledger director's-only; atlas; sealed evidence;
no freezes/re-pins) plus one new: the blind-eval pin committed at
`config/scp2-2-blind-eval.sha256` — the executor must NOT possess,
reconstruct, or guess the pinned case set; it is the director's
acceptance instrument.

## Headline risk

The model must not be able to smuggle semantics past the contract.
Hermes's ONLY output surface is a meaning expression (or a typed
refusal); nothing model-generated reaches the machine side except
through `MeaningExpressionV0` validation and the vocabulary gate. The
failure mode: prompt text, few-shot examples, or postprocessing that
injects constraint kinds, field names, or claims the pack does not
declare — the model-side equivalent of SCP2-1 round 1's ungated side
channel.

## Scope

### 1. The Hermes compiler surface
Build on the existing invocation infrastructure
(`src/tqe/workshop/hermes_invocation.py` + workshop service), NOT a
new client stack. New module (e.g.
`src/tqe/semantic_compiler/hermes_nl.py`):
`compile_nl_request(text, context) -> HermesOutcome` where
HermesOutcome is exactly one of:
- `expression`: a validated MeaningExpressionV0 (passed through
  load + first_vocabulary_refusal — a refusal here becomes outcome
  (c), never a crash);
- `clarification_required`: the ambiguity NAMED as a dimension with
  2+ concrete readings the user can choose between (each reading
  itself expressible — no fake choices);
- `understood_but_not_expressible`: smallest missing capability,
  truthful gap code (R-AH law applies);
- `unsupported_modality`.
There is no fifth outcome. Model transcript (prompt hash, raw
completion) is recorded as evidence alongside every outcome —
provenance for every compile.

### 2. The system prompt is a contract projection
Hermes's instructions are GENERATED from the knowledge pack (the same
pack the gate validates against), not hand-written vocabulary lists:
concepts, the eight grammar operators with parameter schemas,
constraint kinds, gap codes, claim boundaries. Hand-authored prose may
frame HOW to reason; WHAT exists comes from the pack at build time.
The prompt-projection generator is committed and deterministic; the
report states the pack hash it projected from.

### 3. Multi-turn clarification
A clarification_required outcome carries state: the user's answer
(selecting a reading or supplying the missing parameter) resumes
compilation WITHOUT re-asking. Conversation state is typed (the
pending readings), not free-text memory. One test walks the full turn:
ambiguous ask → named dimension + readings → answer → valid
expression.

### 4. The executor's own eval harness + dev case set
`scripts/scp2_2/eval_harness.py`: takes a case-set JSON (schema
mirroring SCL-NL0: request text(s), expected outcome class, for
same-meaning pairs the invariance criterion, for refusals the expected
gap code/dimension), runs Hermes, emits a verdict table
(per-case PASS/FAIL + transcript refs). The executor authors a DEV
case set (~15 cases, committed) covering: same-meaning invariance
pairs, changed-meaning detection, each refusal class, a multi-turn
clarification, novel multi-operator composition (sequence + rate),
known-concept asks. Dev results in the report, every failure
attributed. Invariance criterion: two phrasings are invariant when
their expressions synthesize targets with EQUAL document_hash (the
strong form; if that is too strict on legitimate parameter-order
variance, flag with evidence and propose the equivalence relation —
do not silently weaken).

### 5. The blind set stays blind
`config/scp2-2-blind-eval.sha256` pins the director's held-out case
set. Acceptance = the director runs the pinned set through YOUR
committed harness unmodified. Design for an unseen distribution:
robustness (odd phrasings, football slang, deliberate vagueness) is
the point, not memorizing the dev set.

## Model access
Use the existing configured model path in the workshop service. If
API access is unavailable in the sandbox, STOP and report — the
director provisions; do not stub the model and report it as working.
Long/model-bound runs: flag them; the director schedules detached.

## Tests (mutation standard)
Outcome-type exhaustiveness (no fifth shape constructible); the gate
runs on every expression outcome (mutate: bypass the gate → named
test fails); prompt projection derives from the pack (mutate a pack
copy → projection changes; hand-edit sentinel absent); multi-turn
resume; harness verdict correctness on a tiny fixture set with known
answers.

## Deliverables
hermes_nl module + prompt projection generator; eval harness + dev
case set + dev results; multi-turn support; tests; stage-committed
report with full-suite table. Nothing pushed.
