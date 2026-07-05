# SCP2-2 Report: Hermes NL To Meaning Expression

Branch: `packet/scp2-2`

Frontier base: `a412a56` (`codex/afl08-passport-loop`)

## Protocol Status

| Item | Status | Evidence |
| --- | --- | --- |
| ADR 0015 reread | DONE | Principles 23-25 govern this packet. |
| Packet read | DONE | `delivery/packets/SCP2-2-hermes-nl.md` |
| Branch | DONE | `packet/scp2-2` from `a412a56` |
| Blind set | FENCED | Only `config/scp2-2-blind-eval.sha256` read; no blind cases possessed or reconstructed. |
| Model access | AVAILABLE | Real Hermes smoke passed with explicit Anthropic provider/model. |
| Push | NOT_DONE | Local commits only. |

## Implementation Plan

| Slice | Status | Notes |
| --- | --- | --- |
| Prompt projection | IN_PROGRESS | Generate deterministic system prompt from `generated/tactical-knowledge-pack.json`; no hand-written vocabulary list. |
| Outcome contract | PENDING | Only `expression`, `clarification_required`, `understood_but_not_expressible`, `unsupported_modality`. |
| Multi-turn state | PENDING | Typed pending clarification readings; answer resumes without free-text memory. |
| Eval harness/dev set | PENDING | Committed DEV set, director blind set remains hash-pinned only. |
| Tests/mutations | PENDING | Exhaustiveness, vocabulary gate, projection derivation, multi-turn, harness verdicts. |

## Model Access Check

Default Hermes config was not usable: provider `OpenRouter` had no key and no
default model, so `hermes -z ...` produced no final response. Explicit provider
access succeeded:

```text
HERMES_YOLO_MODE=1 HERMES_ACCEPT_HOOKS=1 perl -e 'alarm shift; exec @ARGV' 90 hermes --safe-mode --ignore-rules --provider anthropic --model claude-sonnet-4-5 -z 'Return exactly this JSON and nothing else: {"ok":true}'
```

Result:

```text
{"ok":true}
```

## Verification

Pending implementation.
