import React from "react";

// Set to the GitHub blob base for the pushed branch IF the repo is public to the
// reader (e.g. "https://github.com/<org>/<repo>/blob/codex/afl08-passport-loop").
// Leave null to render plain file paths instead of links — never ship a dead link.
const REPO_BASE: string | null = null;

const SOURCES = [
  { label: "Controlled-pass verification", path: "delivery/m2a-high-bypass-completed-pass/M2A_S1A_CONTROLLED_PASS.md" },
  { label: "High-bypass verification", path: "delivery/m2a-high-bypass-completed-pass/M2A_S1C_HIGH_BYPASS_RESULTS.md" },
  { label: "High-bypass typed plan", path: "config/query-plans/high_bypass_completed_pass.experimental.v1.json" },
  { label: "Typed query-plan library (the tactical language)", path: "config/query-plans/" }
];

const LAYERS = [
  "Raw event + tracking data (IDSSE / DFL)",
  "Canonical match state",
  "Primitive / relation catalog",
  "Typed query plan",
  "Compiler · binder · search",
  "Deterministic runtime",
  "PASS / FAIL / UNKNOWN evidence",
  "Replay + coach-facing wording"
];

export function CaseStudy() {
  return (
    <main className="cs">
      <style>{CSS}</style>

      <article className="cs-col">
        <p className="cs-eyebrow">Priori · Engineering note</p>
        <h1>A soccer language compiler: approach, library, and what testing it revealed</h1>
        <p className="cs-lede">
          A compiler for football concepts: describe a situation, compile it into
          evidence-backed primitives, and find the real moments in tracking data where
          that situation occurred.
        </p>

        <section className="cs-diagram" aria-label="Architecture">
          {LAYERS.map((l, i) => (
            <React.Fragment key={l}>
              <div className="cs-node">{l}</div>
              {i < LAYERS.length - 1 && <div className="cs-arrow">↓</div>}
            </React.Fragment>
          ))}
          <div className="cs-invariant">
            Invariant across every layer: <strong>product language cannot exceed evidence strength.</strong>
          </div>
        </section>

        <h2>What we’re building</h2>
        <p>
          The goal is a compiler for football concepts. Someone describes a situation — a pass that
          breaks a line, a switch of play, a team building out from the back — and the system finds
          the real moments in tracking data where that situation occurred. The input is public
          IDSSE/DFL data: per-frame positions for every player and the ball, plus an event feed.
        </p>
        <p>
          The hard part is not finding football-looking events. It is being precise about what the
          system is allowed to claim about them. A “completed pass” in an event feed is a label.
          Whether the receiver controlled it, whether the team kept it, and whether it led anywhere
          are separate facts that need separate evidence. The system treats each as a distinct claim,
          and the language shown to a user is never allowed to be stronger than the evidence behind it.
        </p>

        <h2>The approach</h2>
        <p>
          Every measurement is a primitive: a deterministic function over the tracking data that
          returns a typed result plus the evidence for it. A primitive returns PASS, FAIL, or UNKNOWN.
          UNKNOWN means the data was insufficient to decide, not that the answer is no. Each primitive
          also has a claim boundary — an explicit statement of what its result does and does not mean:
          geometry, for instance, but not intent, quality, or causation.
        </p>
        <p>
          Primitives compose. A coach-facing concept is a typed plan over several primitives, with
          thresholds and a defined set of evidence fields it may expose. A request either compiles to
          an executable plan or returns an honest gap. Nothing is a hand-written highlight detector.
        </p>

        <h2>What the library contains</h2>
        <p>The catalog currently has about forty primitives and relations. Grouped by what they describe:</p>
        <ul>
          <li><strong>Build-up:</strong> possession segments, pass chains, structured zones, controlled line breaks.</li>
          <li><strong>Ball movement:</strong> switch of play, carries, one-touch relays, lateral shift, progressive corridors.</li>
          <li><strong>Progression:</strong> forward progression and final-third entry, opponents bypassed.</li>
          <li><strong>Defending and pressing:</strong> team press, pressure on the carrier, marking, cover shadow, defensive lines, compactness, local numerical advantage.</li>
          <li><strong>Off the ball:</strong> runs and run types, support arrival, time to arrival, lane occupancy, space generation.</li>
          <li><strong>Set pieces:</strong> set-piece structure and restart type.</li>
        </ul>
        <p>
          These compute geometric and kinematic facts. A primitive existing in the catalog is not the
          same as its coach-facing meaning being proven; each one still has to be validated on its own.
        </p>

        <h2>Putting it to test: high-bypass passes</h2>
        <p>
          We took one concept all the way through: a high-bypass pass — a completed, controlled pass
          that moves the ball forward and takes several opponents out of the play. As a typed plan:
        </p>
        <pre>{`controlled_pass_episode
+ opponents_bypassed_by_action
+ forward_progression ≥ 8 m
→ high_bypass_completed_pass`}</pre>
        <p>
          It was a useful test because it touches the whole stack: event feed, tracking, geometry,
          control, possession, and the wording a coach finally sees.
        </p>

        <h2>Findings</h2>
        <p>
          At the substrate level the controlled-pass primitive does what it should. On the verified
          scope, match <code>J03WOY</code>, it evaluated 639 candidate events:
        </p>
        <pre>{`453 PASS
135 FAIL
 51 UNKNOWN`}</pre>
        <p>
          The non-PASS cases carry specific reasons, among them <code>another_player_controlled_first</code>{" "}
          (35), <code>possession_definitively_broke</code> (67), <code>release_contradicted</code>{" "}
          (33), and <code>release_not_confirmed</code> (84). The system records why a candidate failed
          instead of dropping it silently.
        </p>
        <p>
          The same data shows the limit. Among verified controlled passes, the median time from release
          to reception is 0.84 seconds and the median forward progression is 0.53 metres. A controlled
          pass is often a brief touch that barely advances. That is a sound primitive, but it does not
          support words like “successful” or “kept it.”
        </p>
        <p>
          The first high-bypass surface ignored that limit and presented these moments as successful
          attacking actions. When the replay was extended past the moment of reception, the receiver
          often lost the ball within a couple of seconds. The geometry was right; the word “successful”
          was not earned.
        </p>
        <p>
          The first attempt to fix this used the provider’s possession flag to confirm the team kept the
          ball. It passed the same moments that still looked like losses on replay, because that flag
          credits a team through contested and transitional touches. It agreed with the original mistake
          instead of catching it.
        </p>
        <p>
          A second issue surfaced once control was handled properly. Of the five moments that passed a
          stricter control check, two came from restarts — a free kick and a throw-in. They were valid
          high-bypass passes and valid controlled receptions, but not open-play examples.
        </p>

        <h2>Changes made</h2>
        <p>Two layers were added, each fencing a specific overclaim.</p>
        <p>
          First, a clean-control check. A coach-facing “controlled reception” now requires more than a
          provider flag or a brief touch: the ball stays close to the receiver, the receiver is clearly
          closer to it than any opponent, the ball moves with the receiver, control is sustained, and
          the moment is dropped if an opponent gains clean control. Of twenty raw high-bypass passes,
          five passed.
        </p>
        <p>
          Second, event-context filtering. Event type and restart status are now carried through to the
          result, and the surface defaults to open play. The two restart cases stay available to inspect
          rather than being hidden.
        </p>
        <p>
          Both changes have the same shape. A primitive was true; a stronger claim was attached to it
          that the evidence did not support; the fix was to supply the evidence that claim required, or
          to stop making it. Each time one claim was tightened, the next mismatch became visible:
          geometry, then control, then phase of play.
        </p>

        <h2>Where this leaves the approach</h2>
        <p>
          The substrate is broad and the claims are kept narrow. The library already spans build-up,
          ball movement, progression, pressing, off-ball movement, and set pieces. What the high-bypass
          work established is the rule the rest of the library has to follow: a coach-facing claim is
          allowed only when the composition beneath it proves that exact claim. The system gets better
          by making each remaining overclaim easy to find and easy to fence, not by adding cleverness on
          top.
        </p>

        <h2>Sources</h2>
        <ul className="cs-sources">
          {SOURCES.map((s) => (
            <li key={s.path}>
              {REPO_BASE ? <a href={`${REPO_BASE}/${s.path}`} target="_blank" rel="noreferrer">{s.label}</a> : s.label}
              <code>{s.path}</code>
            </li>
          ))}
        </ul>
      </article>
    </main>
  );
}

const CSS = `
.cs{background:#faf9f5;color:#1e2320;min-height:100vh;padding:72px 24px 120px;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.cs-col{max-width:680px;margin:0 auto}
.cs-eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:12px;font-weight:650;color:#5d7a68;margin:0 0 14px}
.cs h1{font-size:clamp(30px,5vw,42px);line-height:1.12;letter-spacing:-.02em;margin:0 0 18px;color:#1f2923}
.cs-lede{font-size:19px;line-height:1.55;color:#303831;margin:0 0 40px}
.cs h2{font-size:21px;letter-spacing:-.01em;margin:48px 0 14px;color:#1f2923}
.cs p{margin:0 0 18px}
.cs ul{margin:0 0 18px;padding-left:22px}.cs li{margin:0 0 6px}
.cs code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;background:#edefe8;padding:2px 6px;border-radius:5px;color:#28332b}
.cs pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;line-height:1.5;background:#f1f3ec;border:1px solid #e0e4da;border-radius:8px;padding:16px 18px;overflow-x:auto;margin:0 0 22px;color:#28332b}
.cs blockquote{margin:0 0 22px;padding:4px 0 4px 18px;border-left:3px solid #8fac9a;color:#303831;font-size:18px}
.cs-pull{font-size:22px;line-height:1.4;font-weight:600;color:#1f2923;margin:30px 0;letter-spacing:-.01em}
.cs-invariant-q{font-size:20px;font-weight:600;border-left-color:#c9a24a;color:#1f2923}
.cs-two{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 22px}
@media(max-width:560px){.cs-two{grid-template-columns:1fr}}
.cs-cap{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#5d7a68;font-weight:650;margin:0 0 8px}
.cs-two pre{margin:0;height:100%}
.cs-diagram{margin:0 0 44px;display:flex;flex-direction:column;align-items:center;text-align:center}
.cs-node{width:100%;max-width:420px;background:#fff;border:1px solid #d8ddd2;border-radius:8px;padding:11px 14px;font-size:14px;font-weight:550;color:#28332b;box-shadow:0 1px 2px rgba(40,51,43,.04)}
.cs-arrow{color:#8fac9a;font-size:14px;line-height:1;margin:5px 0}
.cs-invariant{margin-top:18px;font-size:13px;color:#5d7a68;max-width:460px}
.cs-sources{list-style:none;padding:0}
.cs-sources li{display:flex;flex-direction:column;gap:3px;margin:0 0 12px}
.cs-sources a{color:#2f6b4f;text-decoration:none;font-weight:550}.cs-sources a:hover{text-decoration:underline}
.cs-sources code{align-self:flex-start;font-size:12px;background:none;color:#6a716a;padding:0}
`;
