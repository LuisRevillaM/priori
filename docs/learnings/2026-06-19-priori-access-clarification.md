# Learning - Priori Access Clarification

Date: 2026-06-19

## Fact

The roadmap wording implied future access to Priori SDKs, APIs, private outputs, or rights-cleared assets.

## Decision

Do not assume Priori access. This note was later superseded by the independent-demo scope: do not plan conditional Priori integration inside this project at all.

Historical note: this file briefly proposed provider adapter readiness if Priori access was absent. ADR 0008 supersedes that. Provider adapter readiness is out of scope for this project.

## Follow-Up

- Do not ask workers to implement Priori-specific code in this project.
- If integration ever becomes desirable, start a separate project with a new charter and ADR.
