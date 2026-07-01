# Scope

## Packet Scope

This is an inspection-only packet for Workbench Product Audit v1. It packages the audit deliverables created for the deployed Tactical Query Evidence Explorer.

## Audited Source State

- Branch: `codex/integrated-alpha`
- Audited commit: `25f29a146e475ef573dbf59da1901bec4d9c8253`
- URL: https://priori-integrated-alpha.onrender.com

## Explicit Assumptions

- The external reviewer does not have repository access.
- The reviewer can inspect the packet files but cannot rerun the app from this packet alone.
- The audit deliverables are the source of truth for this review packet.

## Out of Scope

- Changing Workbench frontend/backend code.
- Changing prompts, Hermes configuration, recipes, primitives, runtime, or deployment config.
- Providing raw tracking data or replay payloads.
- Providing a standalone reproducible app bundle.

