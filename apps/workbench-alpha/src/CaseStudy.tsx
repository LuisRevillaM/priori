import React from "react";
import { CoachMomentPitch, type CoachMomentPayload } from "./MomentZero";
import { layoutPitch, pitchPointToPixel } from "./pitchGeometry";
import type { ReplayPayload } from "./types";

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

const REPLAY_PACKET_PATH = "/case-study-high-bypass-replays.json";
const TEAM_PRESS_PACKET_PATH = "/case-study-team-press-replays.json";
const COVER_SHADOW_PACKET_PATH = "/case-study-cover-shadow-replays.json";
const CARRY_PACKET_PATH = "/case-study-carry-replays.json";

type ReplayPacket = {
  replays: Array<{
    index: number;
    payload: unknown;
  }>;
};

type TeamPressPayload = {
  schema_version: "coach_moment.team_press.v0";
  moment: {
    match_id: string;
    period: string;
    team_role?: string | null;
    anchor_frame_id: number;
    carrier_id: string;
    team_press_status: string;
    pressure_actor_ids: string[];
    pressure_actor_count: number;
    nearby_defender_count: number;
    observed_defender_count: number;
    pressure_angle_spread_degrees: number;
    maximum_press_distance_m: number;
    minimum_pressing_defenders: number;
    minimum_angle_spread_degrees: number;
    coverage_status: string;
    pressure_actor_evidence: Array<{
      player_id: string;
      distance_m: number;
      bearing_degrees: number;
      closing_speed_mps: number;
      approach_angle_degrees: number;
      defender_point: { x_m: number; y_m: number };
      previous_defender_point?: { x_m: number; y_m: number };
    }>;
    carrier_point: { x_m: number; y_m: number };
    claim_boundary: string;
  };
  replay: ReplayPayload;
  visual_contract: Record<string, unknown>;
};

type CoverShadowPayload = {
  schema_version: "coach_moment.cover_shadow.v0";
  moment: {
    match_id: string;
    period: string;
    team_role?: string | null;
    anchor_frame_id: number;
    cover_shadow_status: string;
    passing_lane_denial_status: string;
    target_entity_id: string;
    ball_point: { x_m: number; y_m: number };
    target_point: { x_m: number; y_m: number };
    lane_length_m: number;
    observed_defender_count: number;
    minimum_observed_defenders: number;
    maximum_lane_distance_m: number;
    minimum_projection_fraction: number;
    screening_defender_id: string;
    screening_defender_distance_to_lane_m: number;
    screening_defender_projection_fraction: number;
    screening_defender_point: { x_m: number; y_m: number };
    screening_projection_point: { x_m: number; y_m: number };
    claim_boundary: string;
  };
  replay: ReplayPayload;
  visual_contract: Record<string, unknown>;
};

type CarryPayload = {
  schema_version: "coach_moment.carry_episode.v0";
  moment: {
    result_id: string;
    match_id: string;
    period: string;
    team_role?: string | null;
    anchor_frame_id: number;
    carry_episode_id: string;
    carrier_id: string;
    carry_status: string;
    carry_reason: string;
    carry_start_frame_id: number;
    carry_end_frame_id: number;
    carry_duration_seconds: number;
    start_point: { x_m: number; y_m: number };
    end_point: { x_m: number; y_m: number };
    displacement_m: number;
    carry_forward_progression_m: number;
    possession_continuity_status: string;
    control_continuity_status: string;
    controlled_frame_ratio: number;
    comoving_frame_ratio: number;
    control_distance_m: number;
    nearest_teammate_margin_m: number;
    maximum_ball_player_speed_delta_mps: number;
    minimum_displacement_m: number;
    maximum_carry_seconds: number;
    claim_boundary: string;
  };
  replay: ReplayPayload;
  visual_contract: Record<string, unknown>;
};

export function CaseStudy() {
  const [replays, setReplays] = React.useState<Record<number, CoachMomentPayload>>({});
  const [teamPressReplays, setTeamPressReplays] = React.useState<Record<number, TeamPressPayload>>({});
  const [coverShadowReplays, setCoverShadowReplays] = React.useState<Record<number, CoverShadowPayload>>({});
  const [carryReplays, setCarryReplays] = React.useState<Record<number, CarryPayload>>({});

  React.useEffect(() => {
    let cancelled = false;
    fetch(REPLAY_PACKET_PATH)
      .then((response) => {
        if (!response.ok) throw new Error(`Replay packet unavailable: ${response.status}`);
        return response.json() as Promise<ReplayPacket>;
      })
      .then((packet) => {
        if (cancelled) return;
        setReplays(
          Object.fromEntries(packet.replays.map((item) => [item.index, item.payload as CoachMomentPayload]))
        );
      })
      .catch(() => {
        if (!cancelled) setReplays({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    fetch(TEAM_PRESS_PACKET_PATH)
      .then((response) => {
        if (!response.ok) throw new Error(`Team-press replay packet unavailable: ${response.status}`);
        return response.json() as Promise<ReplayPacket>;
      })
      .then((packet) => {
        if (cancelled) return;
        setTeamPressReplays(
          Object.fromEntries(packet.replays.map((item) => [item.index, item.payload as TeamPressPayload]))
        );
      })
      .catch(() => {
        if (!cancelled) setTeamPressReplays({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    fetch(COVER_SHADOW_PACKET_PATH)
      .then((response) => {
        if (!response.ok) throw new Error(`Cover-shadow replay packet unavailable: ${response.status}`);
        return response.json() as Promise<ReplayPacket>;
      })
      .then((packet) => {
        if (cancelled) return;
        setCoverShadowReplays(
          Object.fromEntries(packet.replays.map((item) => [item.index, item.payload as CoverShadowPayload]))
        );
      })
      .catch(() => {
        if (!cancelled) setCoverShadowReplays({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    fetch(CARRY_PACKET_PATH)
      .then((response) => {
        if (!response.ok) throw new Error(`Carry replay packet unavailable: ${response.status}`);
        return response.json() as Promise<ReplayPacket>;
      })
      .then((packet) => {
        if (cancelled) return;
        setCarryReplays(
          Object.fromEntries(packet.replays.map((item) => [item.index, item.payload as CarryPayload]))
        );
      })
      .catch(() => {
        if (!cancelled) setCarryReplays({});
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
          Many primitives sit close to one observable condition. Some are spatial: defenders around a
          carrier, or a defender on a ball-to-target lane. Some are kinematic: a player speeding up,
          slowing down, or arriving at a point. Those observations are useful, but a primitive existing
          in the catalog is a building block, not a coach insight.
        </p>
        <p>
          A coach-facing situation is compound. It can require geometry, relationships between players,
          event context, control, and the words the surface is allowed to use. The difference between a
          primitive and a claim is the spine of this test.
        </p>
        <h3 className="cs-example-title">Geometric primitive: observed pressure on the carrier</h3>
        <div className="cs-example-context" aria-label="Team-press example context">
          <div>
            <span>Look for</span>
            <strong>The carrier, nearby defenders, and the seven-metre radius at one measured frame.</strong>
          </div>
          <div>
            <span>Proves</span>
            <strong>The highlighted defenders are close, closing, and spread around the carrier.</strong>
          </div>
          <div>
            <span>Does not claim</span>
            <strong>A coordinated press, trap, intent, quality, or tactical cause.</strong>
          </div>
        </div>
        <PrimitiveMiniReplay
          className="cs-replay-team-press"
          payload={teamPressReplays[0]}
          overlay="team_press"
          ariaLabel="Observed team-press geometry on a football pitch"
          verdict="Team-press geometry PASS · substrate example"
          facts={(payload) => <TeamPressFacts payload={payload} />}
          caption="Observed pressure on the carrier: the highlighted defenders satisfy the distance, closing, and angle-spread gates. This is substrate-verified geometry, not a product-validated press interpretation."
        />
        <h3 className="cs-example-title">Geometric primitive: cover shadow on a lane</h3>
        <div className="cs-example-context" aria-label="Cover-shadow example context">
          <div>
            <span>Look for</span>
            <strong>The ball-to-target lane and the defender sitting inside its threshold band.</strong>
          </div>
          <div>
            <span>Proves</span>
            <strong>A defender screens that lane under fixed distance and projection thresholds.</strong>
          </div>
          <div>
            <span>Does not claim</span>
            <strong>Defender intent, pass probability, pitch-control value, interception, or quality.</strong>
          </div>
        </div>
        <PrimitiveMiniReplay
          className="cs-replay-cover-shadow"
          payload={coverShadowReplays[0]}
          overlay="cover_shadow"
          ariaLabel="Observed cover-shadow lane geometry on a football pitch"
          verdict="Cover-shadow geometry PASS · substrate example"
          facts={(payload) => <CoverShadowFacts payload={payload} />}
          caption="Observed lane screening: one defender sits within the measured ball-target lane band. This is geometry only, not a claim that the pass was impossible or deliberately denied."
        />
        <h3 className="cs-example-title">On-ball primitive: observed carry</h3>
        <div className="cs-example-context" aria-label="Carry example context">
          <div>
            <span>Look for</span>
            <strong>The highlighted carrier and the ball-control path from reception to release.</strong>
          </div>
          <div>
            <span>Proves</span>
            <strong>Same-player movement under control across a measured carry interval.</strong>
          </div>
          <div>
            <span>Does not claim</span>
            <strong>Dribbling skill, defender bypass, pressure breaking, intent, decision quality, or value.</strong>
          </div>
        </div>
        <PrimitiveMiniReplay
          className="cs-replay-carry"
          payload={carryReplays[0]}
          overlay="carry"
          ariaLabel="Observed carry movement on a football pitch"
          verdict="Carry PASS · substrate example"
          facts={(payload) => <CarryFacts payload={payload} />}
          caption="Observed carry: the same player moves with the ball under the declared control thresholds. This is movement-under-control only, not a claim that the carry beat defenders or was valuable."
        />

        <h2>Putting it to test: high-bypass passes</h2>
        <p>
          High-bypass is different. It is not a single primitive. It compounds a pass event, opponent
          positions, forward progression, reception control, restart context, and the words the surface
          is allowed to imply about outcome. The geometry can be true while the coach-facing word is
          still too strong.
        </p>
        <h3 className="cs-example-title">Composed concept: high-bypass pass</h3>
        <div className="cs-example-context" aria-label="High-bypass example context">
          <div>
            <span>Look for</span>
            <strong>A pass that travels beyond multiple defending players.</strong>
          </div>
          <div>
            <span>Proves</span>
            <strong>Pass geometry, bypass count, and then whether clean control settled.</strong>
          </div>
          <div>
            <span>Does not claim</span>
            <strong>Success or value unless the stricter control gate also passes.</strong>
          </div>
        </div>
        <p>
          We took one concept all the way through: a high-bypass pass — a completed, controlled pass
          that moves the ball forward and takes several opponents out of the play. As a typed plan:
        </p>
        <pre>{`controlled_pass_episode
+ opponents_bypassed_by_action
+ forward_progression ≥ 8 m
→ high_bypass_completed_pass`}</pre>
        <MiniReplay
          payload={replays[0]}
          verdict="Open-play clean-control PASS · catalog index 0"
          caption="What the surface should keep: an open-play high-bypass where clean control is held after reception."
        />
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
          attacking actions. When the replay was extended past the moment of reception, the reception
          often never settled into clean control. The ball could stay loose or contested without either
          side holding it cleanly. The geometry was right; the word “successful” was not earned.
        </p>
        <MiniReplay
          payload={replays[5]}
          verdict="Clean-control FAIL · catalog index 5"
          caption="The first surface would have treated this as successful. The failure is narrower: clean control never settles long enough to back that word."
        />
        <p>
          The first attempt to fix this used the provider’s possession flag to confirm the team kept the
          ball. It passed the same unsettled moments, because that flag
          credits a team through contested and transitional touches. It agreed with the original mistake
          instead of catching it.
        </p>
        <p>
          A second issue surfaced once control was handled properly. Of the five moments that passed a
          stricter control check, two came from restarts — a free kick and a throw-in. They were valid
          high-bypass passes and valid controlled receptions, but not open-play examples.
        </p>
        <MiniReplay
          payload={replays[1]}
          verdict="Clean-control PASS · restart · catalog index 1"
          caption="A valid high-bypass and a genuine controlled reception, but from a free kick rather than open play."
        />

        <h2>What changed, and where</h2>
        <p>
          It is worth being exact about where these fixes live, because the location is the point. None
          of them changed the core compiler. The primitives were already truthful. The overclaims
          happened at the boundary between the substrate and the coach-facing product, and that is where
          the fences were added.
        </p>
        <p>
          <strong>Clean-control check — generation layer.</strong> The check,{" "}
          <code>clean_control_retention_sequence</code>, is not a core catalog primitive. It runs over
          the compiler’s output, in the layer that prepares moments for the surface, and keeps only the
          passes where control was genuinely held. Of twenty raw high-bypass passes, five passed.
          Because it is currently a gate rather than a registered primitive, the natural next step is to
          promote it into the catalog so other concepts can reuse it.
        </p>
        <p>
          <strong>Event-context filter — runtime fields, surface default.</strong> The restart typing
          already existed in the core runtime, <code>set_piece_restart_type</code>. The change carried{" "}
          <code>event_type</code>, <code>restart_type</code>, and <code>open_play_status</code> through
          to the moment payload and defaulted the surface to open play. This was mostly plumbing
          knowledge the runtime already had out to where a coach sees it, plus a filter — not new
          detection.
        </p>
        <p>
          <strong>Claim-backing gate — coach API layer.</strong> The coach service,{" "}
          <code>app_service.py</code>, now holds a map of which composition each coach-facing claim
          requires, and refuses to emit a claim unless that composition is present and passing. It fails
          closed. “Controlled reception” requires the clean-control check; “open-play example” requires
          open-play status.
        </p>
        <p>
          The shared property: the core compiler stayed the same, and the product layer stopped saying
          more than the compiler had proven.
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

      </article>
    </main>
  );
}

function MiniReplay({
  payload,
  verdict,
  caption
}: {
  payload: CoachMomentPayload | undefined;
  verdict: string;
  caption: string;
}) {
  return (
    <figure className="cs-replay">
      <div className="cs-replay-frame">
        {payload ? <CoachMomentPitch payload={payload} overlayMode="clean" /> : <div className="cs-replay-loading">Loading replay</div>}
      </div>
      <figcaption>
        <span>{verdict}</span>
        {payload ? <ReplayFacts payload={payload} /> : null}
        {caption}
      </figcaption>
    </figure>
  );
}

type PrimitiveOverlayKind = "team_press" | "cover_shadow" | "carry";
type PrimitivePayload = TeamPressPayload | CoverShadowPayload | CarryPayload;

function PrimitiveMiniReplay<T extends PrimitivePayload>({
  payload,
  overlay,
  className,
  ariaLabel,
  verdict,
  facts,
  caption
}: {
  payload: T | undefined;
  overlay: PrimitiveOverlayKind;
  className: string;
  ariaLabel: string;
  verdict: string;
  facts: (payload: T) => React.ReactNode;
  caption: string;
}) {
  return (
    <figure className={`cs-replay ${className}`}>
      <div className="cs-replay-frame">
        {payload ? (
          <PrimitivePitch payload={payload} overlay={overlay} ariaLabel={ariaLabel} />
        ) : (
          <div className="cs-replay-loading">Loading replay</div>
        )}
      </div>
      <figcaption>
        <span>{verdict}</span>
        {payload ? facts(payload) : null}
        {caption}
      </figcaption>
    </figure>
  );
}

function PrimitivePitch({
  payload,
  overlay,
  ariaLabel
}: {
  payload: PrimitivePayload;
  overlay: PrimitiveOverlayKind;
  ariaLabel: string;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const shellRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const shell = shellRef.current;
    if (!canvas || !shell) return;

    let animationFrame = 0;
    let startedAt: number | null = null;
    const draw = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp;
      const progress = ((timestamp - startedAt) % 6800) / 6800;
      renderPrimitive(canvas, shell, payload, overlay, progress);
      animationFrame = window.requestAnimationFrame(draw);
    };
    animationFrame = window.requestAnimationFrame(draw);
    return () => {
      window.cancelAnimationFrame(animationFrame);
    };
  }, [payload, overlay]);

  return (
    <div className="momentCanvasShell" ref={shellRef}>
      <canvas ref={canvasRef} aria-label={ariaLabel} />
    </div>
  );
}

function TeamPressFacts({ payload }: { payload: TeamPressPayload }) {
  const moment = payload.moment;
  return (
    <dl className="cs-replay-facts" aria-label="Team-press evidence facts">
      <div>
        <dt>Match</dt>
        <dd>{moment.match_id}</dd>
      </div>
      <div>
        <dt>Half</dt>
        <dd>{periodLabel(moment.period)}</dd>
      </div>
      <div>
        <dt>Status</dt>
        <dd>{moment.team_press_status}</dd>
      </div>
      <div>
        <dt>Actors</dt>
        <dd>{moment.pressure_actor_count} / {moment.minimum_pressing_defenders} min</dd>
      </div>
      <div>
        <dt>Radius</dt>
        <dd>{moment.maximum_press_distance_m.toFixed(1)}m</dd>
      </div>
      <div>
        <dt>Spread</dt>
        <dd>{moment.pressure_angle_spread_degrees.toFixed(1)}° / {moment.minimum_angle_spread_degrees.toFixed(0)}° min</dd>
      </div>
      <div>
        <dt>Tracked</dt>
        <dd>{moment.observed_defender_count} defenders</dd>
      </div>
    </dl>
  );
}

function CoverShadowFacts({ payload }: { payload: CoverShadowPayload }) {
  const moment = payload.moment;
  return (
    <dl className="cs-replay-facts" aria-label="Cover-shadow evidence facts">
      <div>
        <dt>Match</dt>
        <dd>{moment.match_id}</dd>
      </div>
      <div>
        <dt>Half</dt>
        <dd>{periodLabel(moment.period)}</dd>
      </div>
      <div>
        <dt>Status</dt>
        <dd>{moment.cover_shadow_status}</dd>
      </div>
      <div>
        <dt>Lane</dt>
        <dd>{moment.lane_length_m.toFixed(1)}m</dd>
      </div>
      <div>
        <dt>Distance</dt>
        <dd>{moment.screening_defender_distance_to_lane_m.toFixed(2)}m / {moment.maximum_lane_distance_m.toFixed(1)}m</dd>
      </div>
      <div>
        <dt>Tracked</dt>
        <dd>{moment.observed_defender_count} defenders</dd>
      </div>
    </dl>
  );
}

function CarryFacts({ payload }: { payload: CarryPayload }) {
  const moment = payload.moment;
  return (
    <dl className="cs-replay-facts" aria-label="Carry evidence facts">
      <div>
        <dt>Match</dt>
        <dd>{moment.match_id}</dd>
      </div>
      <div>
        <dt>Half</dt>
        <dd>{periodLabel(moment.period)}</dd>
      </div>
      <div>
        <dt>Status</dt>
        <dd>{moment.carry_status}</dd>
      </div>
      <div>
        <dt>Duration</dt>
        <dd>{moment.carry_duration_seconds.toFixed(2)}s</dd>
      </div>
      <div>
        <dt>Displace</dt>
        <dd>{moment.displacement_m.toFixed(1)}m</dd>
      </div>
      <div>
        <dt>Forward</dt>
        <dd>{moment.carry_forward_progression_m.toFixed(1)}m</dd>
      </div>
      <div>
        <dt>Control</dt>
        <dd>{Math.round(moment.controlled_frame_ratio * 100)}%</dd>
      </div>
      <div>
        <dt>Comoving</dt>
        <dd>{Math.round(moment.comoving_frame_ratio * 100)}%</dd>
      </div>
    </dl>
  );
}

function ReplayFacts({ payload }: { payload: CoachMomentPayload }) {
  const moment = asRecord(payload.moment);
  const clean = asRecord(moment.clean_control_retention);
  const receiver = seconds(clean.receiver_clean_control_max_seconds);
  const team = seconds(clean.team_clean_control_max_seconds);
  const receiverMin = seconds(clean.minimum_receiver_control_seconds);
  const teamMin = seconds(clean.minimum_team_control_seconds);
  const opponent = seconds(clean.opponent_clean_control_max_seconds);
  const phase = String(moment.open_play_status ?? "unknown");
  const restart = typeof moment.restart_type === "string" ? moment.restart_type.replaceAll("_", " ") : null;
  const status = String(clean.status ?? "UNKNOWN");
  return (
    <dl className="cs-replay-facts" aria-label="Replay control facts">
      <div>
        <dt>Match</dt>
        <dd>{String(moment.match_id ?? "unknown")}</dd>
      </div>
      <div>
        <dt>Half</dt>
        <dd>{periodLabel(moment.period)}</dd>
      </div>
      <div>
        <dt>Control</dt>
        <dd>{status}</dd>
      </div>
      <div>
        <dt>Receiver</dt>
        <dd>{receiver} / {receiverMin} min</dd>
      </div>
      <div>
        <dt>Team</dt>
        <dd>{team} / {teamMin} min</dd>
      </div>
      <div>
        <dt>Opponent</dt>
        <dd>{opponent}</dd>
      </div>
      <div>
        <dt>Phase</dt>
        <dd>{phase === "restart" && restart ? restart : phase.replaceAll("_", " ")}</dd>
      </div>
    </dl>
  );
}

function renderPrimitive(
  canvas: HTMLCanvasElement,
  shell: HTMLDivElement,
  payload: PrimitivePayload,
  overlay: PrimitiveOverlayKind,
  progress: number
) {
  const replay = payload.replay;
  const moment = payload.moment;
  const layout = layoutPitch(replay.pitch, Math.max(360, shell.clientWidth));
  const width = layout.canvasWidth;
  const height = layout.canvasHeight;
  const ratio = window.devicePixelRatio || 1;
  const physicalWidth = Math.round(width * ratio);
  const physicalHeight = Math.round(height * ratio);
  if (canvas.width !== physicalWidth || canvas.height !== physicalHeight) {
    canvas.width = physicalWidth;
    canvas.height = physicalHeight;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const frame = primitiveFrameForProgress(replay, moment.anchor_frame_id, progress);
  if (!frame) return;
  const anchorFrame = replay.frames.find((item) => item.frame_id === moment.anchor_frame_id) ?? frame;
  const evidenceAlpha = primitiveEvidenceAlpha(progress);
  drawCaseStudyPitch(ctx, layout);
  if (overlay === "team_press") {
    drawPrimitiveContextPlayers(ctx, replay, frame, payload.moment.team_role ?? null, layout);
    drawTeamPressGeometry(ctx, replay, payload.moment as TeamPressPayload["moment"], anchorFrame, layout, evidenceAlpha);
    drawTeamPressEvidencePlayers(ctx, replay, payload.moment as TeamPressPayload["moment"], anchorFrame, layout, evidenceAlpha);
  } else if (overlay === "cover_shadow") {
    drawPrimitiveContextPlayers(ctx, replay, frame, payload.moment.team_role ?? null, layout);
    drawCoverShadowGeometry(ctx, replay, payload.moment as CoverShadowPayload["moment"], layout, evidenceAlpha);
    drawCoverShadowEvidencePlayers(ctx, replay, payload.moment as CoverShadowPayload["moment"], layout, evidenceAlpha);
  } else {
    drawPrimitiveContextPlayers(ctx, replay, frame, payload.moment.team_role ?? null, layout);
    drawCarryGeometry(ctx, replay, payload.moment as CarryPayload["moment"], layout, evidenceAlpha);
    drawCarryEvidencePlayer(ctx, replay, payload.moment as CarryPayload["moment"], anchorFrame, layout, evidenceAlpha);
  }
  drawCaseStudyBall(ctx, replay, frame, layout);
}

function drawCaseStudyPitch(ctx: CanvasRenderingContext2D, layout: ReturnType<typeof layoutPitch>) {
  ctx.fillStyle = "#102a20";
  ctx.fillRect(0, 0, layout.canvasWidth, layout.canvasHeight);
  const x = layout.marginX;
  const y = layout.marginY;
  const w = layout.fieldWidth;
  const h = layout.fieldHeight;
  ctx.save();
  ctx.strokeStyle = "rgba(240,239,225,.24)";
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);
  ctx.strokeStyle = "rgba(240,239,225,.13)";
  ctx.beginPath();
  ctx.moveTo(x + w / 2, y);
  ctx.lineTo(x + w / 2, y + h);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x + w / 2, y + h / 2, 9.15 * layout.scalePxPerM, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawPrimitiveContextPlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  frame: ReplayPayload["frames"][number],
  focusTeamRole: string | null,
  layout: ReturnType<typeof layoutPitch>
) {
  for (const entity of frame.entities) {
    if (entity.entity_type === "ball") continue;
    const point = pitchPointToPixel(Number(entity.x_m), Number(entity.y_m), replay.pitch, layout);
    const isFocusTeam = focusTeamRole != null && entity.team_role === focusTeamRole;
    ctx.beginPath();
    ctx.fillStyle = isFocusTeam ? "rgba(247,242,218,.52)" : "rgba(215,101,76,.30)";
    ctx.strokeStyle = isFocusTeam ? "rgba(255,251,226,.60)" : "rgba(255,185,160,.58)";
    ctx.lineWidth = isFocusTeam ? 0.9 : 1.15;
    ctx.arc(point.x, point.y, isFocusTeam ? 3.25 : 3.15, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
}

function drawTeamPressEvidencePlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: TeamPressPayload["moment"],
  frame: ReplayPayload["frames"][number],
  layout: ReturnType<typeof layoutPitch>,
  evidenceAlpha: number
) {
  if (evidenceAlpha <= 0.01) return;
  const carrier = frame.entities.find((entity) => entity.entity_id === moment.carrier_id);
  if (carrier) {
    const point = pitchPointToPixel(Number(carrier.x_m), Number(carrier.y_m), replay.pitch, layout);
    ctx.save();
    ctx.globalAlpha = evidenceAlpha;
    ctx.beginPath();
    ctx.fillStyle = "#fff1bd";
    ctx.strokeStyle = "rgba(20,27,19,.72)";
    ctx.lineWidth = 1.8;
    ctx.arc(point.x, point.y, 7.0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.fillStyle = "#1e3f31";
    ctx.arc(point.x, point.y, 2.0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  for (const actorId of moment.pressure_actor_ids) {
    const actor = frame.entities.find((entity) => entity.entity_id === actorId);
    if (!actor) continue;
    const point = pitchPointToPixel(Number(actor.x_m), Number(actor.y_m), replay.pitch, layout);
    ctx.save();
    ctx.globalAlpha = evidenceAlpha;
    ctx.beginPath();
    ctx.fillStyle = "rgba(215,101,76,.30)";
    ctx.strokeStyle = "rgba(255,185,160,.96)";
    ctx.lineWidth = 2.3;
    ctx.arc(point.x, point.y, 6.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.fillStyle = "#ee947c";
    ctx.arc(point.x, point.y, 1.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

function drawTeamPressGeometry(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: TeamPressPayload["moment"],
  frame: ReplayPayload["frames"][number],
  layout: ReturnType<typeof layoutPitch>,
  evidenceAlpha: number
) {
  const carrier = frame.entities.find((entity) => entity.entity_id === moment.carrier_id);
  if (!carrier) return;
  const carrierPoint = pitchPointToPixel(Number(carrier.x_m), Number(carrier.y_m), replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = 0.18 + 0.54 * evidenceAlpha;
  ctx.strokeStyle = "rgba(255,241,189,.88)";
  ctx.lineWidth = 2.0;
  ctx.beginPath();
  ctx.arc(carrierPoint.x, carrierPoint.y, moment.maximum_press_distance_m * layout.scalePxPerM, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

function drawCoverShadowEvidencePlayers(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: CoverShadowPayload["moment"],
  layout: ReturnType<typeof layoutPitch>,
  evidenceAlpha: number
) {
  if (evidenceAlpha <= 0.01) return;
  const target = pitchPointToPixel(Number(moment.target_point.x_m), Number(moment.target_point.y_m), replay.pitch, layout);
  const defender = pitchPointToPixel(
    Number(moment.screening_defender_point.x_m),
    Number(moment.screening_defender_point.y_m),
    replay.pitch,
    layout
  );

  ctx.save();
  ctx.globalAlpha = evidenceAlpha;
  ctx.beginPath();
  ctx.fillStyle = "#fff1bd";
  ctx.strokeStyle = "rgba(20,27,19,.72)";
  ctx.lineWidth = 1.65;
  ctx.arc(target.x, target.y, 6.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.fillStyle = "rgba(215,101,76,.34)";
  ctx.strokeStyle = "rgba(255,185,160,.98)";
  ctx.lineWidth = 2.25;
  ctx.arc(defender.x, defender.y, 6.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.fillStyle = "#ee947c";
  ctx.arc(defender.x, defender.y, 2.0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawCoverShadowGeometry(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: CoverShadowPayload["moment"],
  layout: ReturnType<typeof layoutPitch>,
  evidenceAlpha: number
) {
  const ball = pitchPointToPixel(Number(moment.ball_point.x_m), Number(moment.ball_point.y_m), replay.pitch, layout);
  const target = pitchPointToPixel(Number(moment.target_point.x_m), Number(moment.target_point.y_m), replay.pitch, layout);
  const projection = pitchPointToPixel(
    Number(moment.screening_projection_point.x_m),
    Number(moment.screening_projection_point.y_m),
    replay.pitch,
    layout
  );
  const defender = pitchPointToPixel(
    Number(moment.screening_defender_point.x_m),
    Number(moment.screening_defender_point.y_m),
    replay.pitch,
    layout
  );
  const dx = target.x - ball.x;
  const dy = target.y - ball.y;
  const length = Math.hypot(dx, dy);
  if (length <= 0) return;
  const nx = -dy / length;
  const ny = dx / length;
  const band = moment.maximum_lane_distance_m * layout.scalePxPerM;
  const baseAlpha = 0.20 + 0.52 * evidenceAlpha;

  ctx.save();
  ctx.globalAlpha = 0.16 + 0.18 * evidenceAlpha;
  ctx.fillStyle = "#fff1bd";
  ctx.beginPath();
  ctx.moveTo(ball.x + nx * band, ball.y + ny * band);
  ctx.lineTo(target.x + nx * band, target.y + ny * band);
  ctx.lineTo(target.x - nx * band, target.y - ny * band);
  ctx.lineTo(ball.x - nx * band, ball.y - ny * band);
  ctx.closePath();
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.globalAlpha = baseAlpha;
  ctx.strokeStyle = "rgba(255,241,189,.94)";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  ctx.moveTo(ball.x, ball.y);
  ctx.lineTo(target.x, target.y);
  ctx.stroke();
  if (evidenceAlpha > 0.01) {
    ctx.fillStyle = "#f2cf73";
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, 3.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.strokeStyle = "rgba(255,185,160,.70)";
  ctx.lineWidth = 1.25;
  ctx.globalAlpha = evidenceAlpha;
  ctx.beginPath();
  ctx.moveTo(defender.x, defender.y);
  ctx.lineTo(projection.x, projection.y);
  ctx.stroke();
  ctx.fillStyle = "rgba(255,185,160,.86)";
  ctx.beginPath();
  ctx.arc(projection.x, projection.y, 2.4, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawCarryGeometry(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: CarryPayload["moment"],
  layout: ReturnType<typeof layoutPitch>,
  evidenceAlpha: number
) {
  const trailFrames = replay.frames.filter(
    (frame) => frame.frame_id >= moment.carry_start_frame_id && frame.frame_id <= moment.carry_end_frame_id
  );
  const points = trailFrames
    .map((frame) => frame.entities.find((entity) => entity.entity_id === moment.carrier_id))
    .filter((entity): entity is ReplayPayload["frames"][number]["entities"][number] => Boolean(entity))
    .map((entity) => pitchPointToPixel(Number(entity.x_m), Number(entity.y_m), replay.pitch, layout));
  if (points.length < 2) return;

  ctx.save();
  ctx.globalAlpha = 0.24 + 0.56 * evidenceAlpha;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = "rgba(255,241,189,.88)";
  ctx.lineWidth = 3.0;
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (const point of points.slice(1)) {
    ctx.lineTo(point.x, point.y);
  }
  ctx.stroke();

  const start = points[Math.max(0, points.length - 9)];
  const end = points[points.length - 1];
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const length = Math.hypot(dx, dy);
  if (length > 1.5) {
    const ux = dx / length;
    const uy = dy / length;
    const size = 7;
    ctx.fillStyle = "rgba(255,241,189,.92)";
    ctx.beginPath();
    ctx.moveTo(end.x + ux * 3, end.y + uy * 3);
    ctx.lineTo(end.x - ux * size - uy * size * 0.55, end.y - uy * size + ux * size * 0.55);
    ctx.lineTo(end.x - ux * size + uy * size * 0.55, end.y - uy * size - ux * size * 0.55);
    ctx.closePath();
    ctx.fill();
  }

  ctx.fillStyle = "rgba(255,241,189,.28)";
  ctx.beginPath();
  ctx.arc(points[0].x, points[0].y, 4.6, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,241,189,.82)";
  ctx.beginPath();
  ctx.arc(end.x, end.y, 4.8, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawCarryEvidencePlayer(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  moment: CarryPayload["moment"],
  frame: ReplayPayload["frames"][number],
  layout: ReturnType<typeof layoutPitch>,
  evidenceAlpha: number
) {
  if (evidenceAlpha <= 0.01) return;
  const player = frame.entities.find((entity) => entity.entity_id === moment.carrier_id);
  if (!player) return;
  const point = pitchPointToPixel(Number(player.x_m), Number(player.y_m), replay.pitch, layout);
  ctx.save();
  ctx.globalAlpha = evidenceAlpha;
  ctx.beginPath();
  ctx.fillStyle = "#fff1bd";
  ctx.strokeStyle = "rgba(20,27,19,.72)";
  ctx.lineWidth = 1.8;
  ctx.arc(point.x, point.y, 7.0, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.fillStyle = "#1e3f31";
  ctx.arc(point.x, point.y, 2.0, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawCaseStudyBall(
  ctx: CanvasRenderingContext2D,
  replay: ReplayPayload,
  frame: ReplayPayload["frames"][number],
  layout: ReturnType<typeof layoutPitch>
) {
  const ball = frame.entities.find((entity) => entity.entity_type === "ball");
  if (!ball) return;
  const point = pitchPointToPixel(Number(ball.x_m), Number(ball.y_m), replay.pitch, layout);
  ctx.save();
  ctx.beginPath();
  ctx.fillStyle = "#f2cf73";
  ctx.strokeStyle = "rgba(20,27,19,.92)";
  ctx.lineWidth = 1.5;
  ctx.arc(point.x, point.y, 4.2, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function seconds(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(2)}s` : "n/a";
}

function periodLabel(value: unknown) {
  const raw = String(value ?? "unknown");
  if (raw === "firstHalf") return "first half";
  if (raw === "secondHalf") return "second half";
  return raw.replaceAll("_", " ");
}

function primitiveFrameForProgress(replay: ReplayPayload, anchorFrameId: number, progress: number) {
  const frames = replay.frames;
  if (frames.length === 0) return undefined;
  const anchorIndex = Math.max(0, frames.findIndex((frame) => frame.frame_id === anchorFrameId));
  if (progress < 0.50) {
    const local = easeInOutCubic(clamp01(progress / 0.50));
    return frames[Math.min(anchorIndex, Math.round(local * anchorIndex))];
  }
  if (progress < 0.78) {
    return frames[anchorIndex];
  }
  const tailLength = Math.max(0, frames.length - 1 - anchorIndex);
  const local = easeInOutCubic(clamp01((progress - 0.78) / 0.22));
  return frames[Math.min(frames.length - 1, anchorIndex + Math.round(local * tailLength))];
}

function primitiveEvidenceAlpha(progress: number) {
  return fadeWindow(progress, 0.50, 0.60) * (1 - fadeWindow(progress, 0.72, 0.78));
}

function fadeWindow(value: number, start: number, end: number) {
  return clamp01((value - start) / (end - start));
}

function easeInOutCubic(value: number) {
  const v = clamp01(value);
  return v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2;
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}

const CSS = `
.cs{background:#faf9f5;color:#1e2320;min-height:100vh;padding:72px 24px 120px;font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.cs-col{max-width:680px;margin:0 auto}
.cs-eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:12px;font-weight:650;color:#5d7a68;margin:0 0 14px}
.cs h1{font-size:clamp(30px,5vw,42px);line-height:1.12;letter-spacing:-.02em;margin:0 0 18px;color:#1f2923}
.cs-lede{font-size:19px;line-height:1.55;color:#303831;margin:0 0 40px}
.cs h2{font-size:21px;letter-spacing:-.01em;margin:48px 0 14px;color:#1f2923}
.cs-example-title{font-size:15px;line-height:1.35;letter-spacing:0;margin:28px 0 10px;color:#1f2923}
.cs-example-context{display:grid;grid-template-columns:1fr;gap:8px;margin:0 0 20px;border-top:1px solid #dfe4da;border-bottom:1px solid #dfe4da;padding:12px 0}
.cs-example-context div{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;align-items:start}
.cs-example-context span{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;line-height:1.45;text-transform:uppercase;letter-spacing:.07em;color:#718071}
.cs-example-context strong{font-size:13px;line-height:1.45;color:#2d3830;font-weight:560}
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
.cs-replay{width:min(920px,calc(100vw - 40px));margin:28px 0 30px 50%;transform:translateX(-50%)}
.cs-replay-frame{background:#102a20;border:1px solid rgba(31,41,35,.18);border-radius:12px;overflow:hidden;box-shadow:0 18px 48px rgba(31,41,35,.18)}
.cs-replay .momentCanvasShell{width:100%;filter:none}
.cs-replay .momentCanvasShell canvas{border:0;border-radius:0}
.cs-replay-loading{display:grid;place-items:center;min-height:320px;color:rgba(250,249,245,.72);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;text-transform:uppercase;letter-spacing:.08em}
.cs-replay figcaption{margin:10px 2px 0;color:#4f5b52;font-size:13px;line-height:1.45}
.cs-replay figcaption span{display:block;margin:0 0 3px;color:#2f6b4f;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.cs-replay-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(86px,1fr));gap:6px;margin:8px 0 10px}
.cs-replay-facts div{min-width:0;border:1px solid #dfe4da;border-radius:6px;background:#f4f5ef;padding:6px 7px}
.cs-replay-facts dt{margin:0 0 2px;color:#6b756d;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;text-transform:uppercase;letter-spacing:.06em}
.cs-replay-facts dd{margin:0;color:#28332b;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:720px){.cs-replay-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.cs-replay{width:calc(100vw - 28px);margin-top:22px;margin-bottom:24px}}
`;
