# Work Packet SMOKE-1: honest errors on the ask path

**Source**: the owner's first smoke-test ask. Three defects, one theme:
failures lying about their identity.

**Branch**: `packet/smoke-1` off the frontier. Ground rules unchanged
(stage-commit, never push, R-AZ, full-suite table, deviation law).

## The defects

1. **The blanket except** (app_service.py ~5140): `except (KeyError,
   ValueError, ValidationError)` wraps the ENTIRE endpoint dispatch —
   every internal pipeline failure is reported as
   REQUEST_SCHEMA_INVALID ("Request payload does not match the API
   contract") and the traceback is swallowed unlogged. The owner's ask
   compiled successfully in Hermes and crashed downstream; the UI
   blamed his request.
2. **Model output truncation**: the same ask re-run produced a Hermes
   completion cut mid-JSON at ~15KB (HermesNLModelOutputError:
   "Expecting ',' delimiter: char 14964") — long expressions clip at
   an output limit and the repair loop does not recover truncation.
3. **No failure identity for the user**: schema-blame, model
   truncation, and downstream crashes all render identically; the
   user cannot tell "rephrase" from "retry" from "report a bug".

## The fixes

1. Scope the schema handler to REQUEST PARSING only (payload decode +
   model_validate of the request). Everything after dispatch gets:
   full traceback LOGGED server-side with a correlation id, and a
   typed INTERNAL_ERROR response carrying that id — never schema
   blame. (This is R-AZ's spirit in the error layer: failures must be
   attributable.)
2. Truncation: raise the interpret call's output-token ceiling for
   SCP2-2 compiles; detect truncated JSON explicitly (unterminated
   parse at end-of-output) and route it to the repair loop as a
   CONTINUATION re-prompt or, failing that, a typed
   MODEL_OUTPUT_TRUNCATED refusal telling the user to retry — never a
   schema error, never a silent crash.
3. UI: three distinct error renderings — "couldn't understand the
   request" (schema, with what was expected), "the model's answer got
   cut off — retry" (truncation/transient), "something broke on our
   side" (internal, with correlation id). Film Room error states per
   the design charter's tone: plain, honest, actionable.
4. Root-cause the owner's original downstream crash: with fix 1's
   logging in place, re-run the owner's exact question until the
   downstream failure reproduces, and fix what it exposes (report the
   traceback and the fix as a named item). If it does not reproduce
   in 5 attempts, say so honestly and leave the logging as the trap.

## Tests
Mutation standard on the handler scoping (an internal KeyError beyond
dispatch must NOT produce REQUEST_SCHEMA_INVALID — named test);
truncated-JSON fixture routes to continuation/typed refusal; the
three UI error states rendered from their typed codes.

## Deliverables
Fixes + tests + report with the root-cause item + full-suite table.
Nothing pushed.
