# Next Steps

1. Send or upload this packet to the external review agent.
2. Use `EXTERNAL_REVIEW_PROMPT.md` as the prompt.
3. Require a decision of `APPROVE`, `APPROVE_WITH_REQUIRED_CHANGES`, or `REJECT`.
4. If the decision is `APPROVE`, begin M1.2 planning/execution against the existing roadmap.
5. If the decision is `APPROVE_WITH_REQUIRED_CHANGES`, classify each required change as either before M1.2 or before a later gate. Complete all before-M1.2 fixes before starting M1.2.
6. If the decision is `REJECT`, stop M1.2 and revise M1.1 architecture until the reviewer can approve.

Controller note: this is a significant milestone boundary. The controller should return to external review after the next comparable boundary, likely after M1.2 workshop/Hermes proof gates pass and before starting the polished UI milestone.
