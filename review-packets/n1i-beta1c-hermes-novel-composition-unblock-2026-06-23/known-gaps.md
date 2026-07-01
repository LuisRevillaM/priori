# Known Gaps

## requires_full_repo: Inspection Packet Only

What is missing: The zip does not include the full repo, virtualenv, Node dependencies, or data/runtime cache needed to rerun all gates.

Why it matters: Reviewers can inspect source and artifacts, but cannot reproduce every command from the packet alone.

Default boundary: Treat this as an inspection packet, not a standalone reproducible package.

Next action: Rerun commands in the full repository if independent execution is required.

## requires_credentials: Render/Hermes Origin Replay

What is missing: The packet does not include Render shell access, Hermes runtime credentials, model credentials, or paid-model access.

Why it matters: The faithful origin replay is the strongest external proof, but cannot be repeated by a reviewer from the zip.

Default boundary: Use committed origin bundle, render logs, and N1I report as evidence; do not claim the packet independently reruns deploy-origin compilation.

Next action: If required, run the protected deploy runner again in the controlled environment and export a new bundle.

## not_in_scope: Beta 1C Implementation

What is missing: Beta 1C is not implemented in this packet.

Why it matters: Approval here only unblocks exposure work; it does not prove the final UI route works.

Default boundary: Beta 1C should still ship with its own product E2E proof: Ask Hermes -> interpretation -> confirm -> cache miss -> result -> replay with `HERMES_NOVEL_COMPOSITION` provenance.

Next action: Implement Beta 1C after review approval, then produce a smaller UI exposure packet or smoke proof.

## unknown: Future Hermes Behavior

What is missing: The packet proves one origin-attested successful hero run, not arbitrary future novel composition reliability.

Why it matters: A future model session may clarify, refuse, or draft a different plan.

Default boundary: Present the product claim as a demonstrated capability with honest provenance, not as guaranteed arbitrary authoring.

Next action: Run a final independent frontier evaluation after Beta 1C exposure.

## blocked hygiene: Known N1C Generated Artifact Dirtiness

What is missing: The working tree has known generated-file dirtiness in tracked N1C artifacts when certain verifiers rerun.

Why it matters: Dirty generated artifacts can confuse review if mixed into the packet.

Default boundary: This packet exports committed files from `HEAD` instead of copying the working tree. The status logs are preserved under `commands/`.

Next action: Separately convert N1C generated artifacts to a read-compare gate or stop tracking regenerating outputs.
