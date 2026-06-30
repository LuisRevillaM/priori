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
        <h1>When the compiler caught its own overclaim</h1>
        <p className="cs-lede">
          A coach-facing system can’t just find football-looking events. It has to know
          exactly what it is claiming — and be built so the product language can never
          run ahead of the evidence underneath it.
        </p>

        {/* Architecture model */}
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

        <h2>The question</h2>
        <p>That principle became concrete while building the high-bypass pass surface. The football idea was simple:</p>
        <blockquote>Find completed passes that move the ball forward and bypass several opponents.</blockquote>
        <p>In our system, that becomes a typed composition:</p>
        <pre>{`controlled_pass_episode
+ opponents_bypassed_by_action
+ forward_progression threshold
→ high_bypass_completed_pass`}</pre>
        <p>The geometry was real. The pass progressed forward; the ball moved beyond multiple defenders; the query returned evidence-backed moments. But the product claim was still too strong.</p>

        <h2>What the primitive actually proved</h2>
        <p>The controlled-pass verifier already shows why the distinction matters. On the verified <code>J03WOY</code> scope, it evaluated 639 candidate events and produced:</p>
        <pre>{`453 PASS
135 FAIL
 51 UNKNOWN`}</pre>
        <p>The system does not collapse uncertainty into false. If it can’t prove the pass, it says <code>UNKNOWN</code>. And the non-PASS cases carry football-meaningful reasons, not generic errors:</p>
        <pre>{`another_player_controlled_first: 35
possession_definitively_broke:   67
release_contradicted:            33
release_not_confirmed:           84
unique_release_transition_not_found: 49
missing_tracking:                 2`}</pre>
        <p>But the same report shows why a controlled pass is still not a successful attacking action. Among verified controlled passes:</p>
        <pre>{`release-to-reception   p50: 0.84 s
forward progression    p50: 0.53 m
forward progression    p90: 11.01 m`}</pre>
        <p>A controlled pass can be a brief touch that barely progresses. That’s a valid primitive — but not enough to support words like “successful,” “valuable,” or “kept it.”</p>

        <h2>The false positive</h2>
        <p>The first high-bypass replay surface treated these moments as <em>successful</em> attacking actions. That word carried more than the primitive proved.</p>
        <div className="cs-two">
          <div>
            <p className="cs-cap">The primitive proved</p>
            <pre>{`A provider pass event existed.
Tracking confirmed a release and a
controlled-reception candidate.
The ball progressed forward.
Opponents were bypassed geometrically.`}</pre>
          </div>
          <div>
            <p className="cs-cap">What a coach hears</p>
            <pre>{`The receiver properly controlled it.
The attacking team kept possession.
The action stayed useful after
reception.`}</pre>
          </div>
        </div>
        <p>When we rendered the follow-through and <em>watched</em>, the issue was obvious: some moments were geometrically correct but football-wrong as “successful.” The receiver touched or briefly controlled the ball, then the team lost it almost immediately. The system hadn’t lied about the geometry. The product language had outrun the evidence.</p>

        <h2>The fix</h2>
        <p>Not to discard the primitive — to add the missing claim layer: <strong>clean control after reception.</strong> A coach-facing “successful reception” now requires more than provider possession or a brief touch:</p>
        <ul>
          <li>the ball stays close to the receiver,</li>
          <li>the receiver is clearly closer than any opponent,</li>
          <li>the ball moves <em>with</em> the receiver,</li>
          <li>control is sustained for a meaningful window,</li>
          <li>opponent clean control excludes the moment.</li>
        </ul>
        <p>Only then can the surface present it as a clean-control high-bypass pass.</p>

        <h2>The lesson</h2>
        <p className="cs-pull">The primitive is not “pass.” The primitive is the exact claim we are willing to make about the pass.</p>
        <pre>{`provider marked it complete
→ physical release detected
→ receiver touched it
→ receiver controlled it
→ team retained clean control
→ the action had a valuable outcome`}</pre>
        <p>Each layer needs its own evidence. The product can only use language backed by the full composition underneath it.</p>

        <h2>Why this matters</h2>
        <blockquote className="cs-invariant-q">Product language cannot exceed evidence strength.</blockquote>
        <p>The system shouldn’t bluff with football vocabulary. If it can prove a geometric bypass, it shows that. If it can prove clean control, it says that. If it can’t prove intent, quality, causation, or optimality, it must not imply them.</p>
        <p>The high-bypass verifier follows that discipline itself. Its boundary states that it verifies high-bypass rows for a scoped match, does not expose results to Hermes, does not claim all-corpus execution, and does not claim replay/UI validation. That self-fencing is the point.</p>
        <p>The most important boundary line is that <strong>“replay UI integration and human visual review remain future slices.”</strong> That is exactly the check that later exposed the product-level false positives. The verifier did not imply completeness; it named the next unproven surface. When we ran that visual review, it found the overclaim the report had not yet claimed to rule out.</p>
        <p>The merit of the high-bypass work is not that it found a handful of clips. It’s that when the clips were wrong, the system gave us the handles to see why, tighten the definition, and prevent the same overclaim from reaching the product again.</p>

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
