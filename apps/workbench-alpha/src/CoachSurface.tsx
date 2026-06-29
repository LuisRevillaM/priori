import { FormEvent, useEffect, useMemo, useState } from "react";
import { coachInterpret, fetchMatches } from "./api";
import { coachProductClaimGate } from "./coachProductClaims";
import {
  CoachMomentPitch,
  momentHighBypassEvidence,
  momentLineBreakSupportedEvidence,
  momentZeroEvidence,
  type CoachMomentPayload,
  type MomentOverlayMode
} from "./MomentZero";
import type { CoachInterpretResponse, MatchSummary } from "./types";

const DEFAULT_QUERY = "Show high-bypass passes";
const EXAMPLES = [
  "Show high-bypass passes",
  "Show line breaks with underneath support",
  "Show line breaks with no underneath outlet",
  "Show line breaks with two underneath outlets",
  "Show expected pass completion",
  "Show dangerous attacks"
];
const CATALOG_MOMENTS = [
  {
    id: "high-bypass",
    title: "High-bypass pass",
    query: "Show high-bypass passes",
    answer: "Completed passes bypassed multiple opponents.",
    claimKind: "high_bypass_completed_pass",
    count: 5,
    payload: momentHighBypassEvidence,
    mode: "bypass"
  },
  {
    id: "line-break-supported",
    title: "Line break, outlet arrives",
    query: "Show line breaks with underneath support",
    answer: "Line broken. Support arrives underneath.",
    claimKind: "line_break_with_underneath_outlet",
    count: 2,
    payload: momentLineBreakSupportedEvidence,
    mode: "supported"
  },
  {
    id: "line-break-isolated",
    title: "Line break, outlet absent",
    query: "Show line breaks with no underneath outlet",
    answer: "Line broken. The outlet space stays empty.",
    claimKind: "line_break_no_underneath_support",
    count: 3,
    payload: momentZeroEvidence,
    mode: "isolated"
  }
] as const;
const MATCH_CONTEXT_FALLBACKS: Record<string, { title: string; home: string; away: string }> = {
  J03WOH: { title: "Fortuna Düsseldorf:SSV Jahn Regensburg", home: "Fortuna", away: "Jahn Regensburg" }
};

export function CoachSurface() {
  const examples = useMemo(() => EXAMPLES, []);
  const catalogMoments = useMemo(() => CATALOG_MOMENTS, []);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [result, setResult] = useState<CoachInterpretResponse | null>(null);
  const [activeInstances, setActiveInstances] = useState<CoachMomentPayload[]>([momentHighBypassEvidence]);
  const [activeInstanceIndex, setActiveInstanceIndex] = useState(0);
  const [activeCatalogId, setActiveCatalogId] = useState<string>(CATALOG_MOMENTS[0].id);
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [runId, setRunId] = useState(0);
  const [overlayMode, setOverlayMode] = useState<MomentOverlayMode>("clean");
  const [isLooking, setIsLooking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activePayload = activeInstances[activeInstanceIndex] ?? CATALOG_MOMENTS[0].payload;

  useEffect(() => {
    let cancelled = false;
    fetchMatches()
      .then((payload) => {
        if (!cancelled) setMatches(payload.matches);
      })
      .catch(() => {
        if (!cancelled) setMatches([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    setIsLooking(true);
    setError(null);
    try {
      const next = await coachInterpret({ query });
      setResult(next);
      const payloads = payloadsFromResponse(next);
      if (next.status === "moment_found" && payloads.length > 0) {
        setActiveInstances(payloads);
        setActiveInstanceIndex(0);
        setActiveCatalogId(catalogIdForMoment(next.moments[0]?.moment_id) ?? "");
        setRunId((value) => value + 1);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The moment could not be loaded.");
    } finally {
      setIsLooking(false);
    }
  };

  const chooseExample = async (example: string) => {
    setQuery(example);
    setIsLooking(true);
    setError(null);
    try {
      const next = await coachInterpret({ query: example });
      setResult(next);
      const payloads = payloadsFromResponse(next);
      if (next.status === "moment_found" && payloads.length > 0) {
        setActiveInstances(payloads);
        setActiveInstanceIndex(0);
        setActiveCatalogId(catalogIdForMoment(next.moments[0]?.moment_id) ?? "");
        setRunId((value) => value + 1);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The moment could not be loaded.");
    } finally {
      setIsLooking(false);
    }
  };

  const chooseCatalogMoment = (moment: (typeof CATALOG_MOMENTS)[number]) => {
    if (!coachProductClaimGate(moment.claimKind, moment.payload).passed) return;
    setQuery(moment.query);
    setResult(null);
    setError(null);
    setActiveInstances([moment.payload]);
    setActiveInstanceIndex(0);
    setActiveCatalogId(moment.id);
    setRunId((value) => value + 1);
    void chooseExample(moment.query);
  };

  const chooseInstance = (nextIndex: number) => {
    const bounded = Math.max(0, Math.min(activeInstances.length - 1, nextIndex));
    if (bounded === activeInstanceIndex) return;
    setActiveInstanceIndex(bounded);
    setRunId((value) => value + 1);
  };

  const isMoment = !result || result.status === "moment_found";
  const activeCatalog = catalogMoments.find((moment) => moment.id === activeCatalogId) ?? catalogMoments[0];

  return (
    <main className="coachShell">
      <section className={isMoment ? "coachExperience isMoment" : "coachExperience"} aria-label="Priori coach preview">
        <div className="coachHeader">
          <span className="coachBrand">Priori</span>
          <h1>Speak football. See the moment.</h1>
        </div>

        <div className="coachTheater" aria-label="Observed football moment preview">
          <MomentContext payload={activePayload} matches={matches} />
          <CoachMomentPitch key={`${runId}-${overlayMode}`} payload={activePayload} overlayMode={overlayMode} />
          <MomentTrustControls
            payload={activePayload}
            overlayMode={overlayMode}
            instanceCount={activeInstances.length}
            instanceIndex={activeInstanceIndex}
            onInstanceChange={chooseInstance}
            onOverlayModeChange={setOverlayMode}
          />
        </div>

        <section className="coachCatalog" aria-label="Compiler-found moment catalog">
          <div className="coachCatalogHeader">
            <span>Real moments in this match</span>
            <strong>Compiler-found catalog</strong>
          </div>
          <div className="coachCatalogGrid">
            {catalogMoments.map((moment) => (
              <CatalogMomentTile
                key={moment.id}
                moment={moment}
                isActive={moment.id === activeCatalogId}
                isLooking={isLooking}
                onChoose={chooseCatalogMoment}
              />
            ))}
          </div>
        </section>

        <form className="coachCommand" onSubmit={submit}>
          <label htmlFor="coach-query">Ask for an observable moment</label>
          <div className="coachInputRow">
            <input
              id="coach-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              autoComplete="off"
              spellCheck={false}
              disabled={isLooking}
            />
            <button type="submit" disabled={isLooking}>{isLooking ? "Looking" : "Show"}</button>
          </div>
          <p className={isLooking ? "coachResponse isLoading" : "coachResponse"}>{responseCopy(result, isLooking, error, activeCatalog.answer)}</p>
          <div className="coachPromptRail" aria-label="Example requests">
            {examples.map((example) => (
              <button type="button" key={example} onClick={() => void chooseExample(example)} disabled={isLooking}>
                {example}
              </button>
            ))}
          </div>
        </form>
      </section>
    </main>
  );
}

function CatalogMomentTile({
  moment,
  isActive,
  isLooking,
  onChoose
}: {
  moment: (typeof CATALOG_MOMENTS)[number];
  isActive: boolean;
  isLooking: boolean;
  onChoose: (moment: (typeof CATALOG_MOMENTS)[number]) => void;
}) {
  const claimGate = coachProductClaimGate(moment.claimKind, moment.payload);
  return (
    <button
      type="button"
      className={isActive ? `coachMomentTile isActive ${moment.mode}` : `coachMomentTile ${moment.mode}`}
      onClick={() => onChoose(moment)}
      disabled={isLooking || !claimGate.passed}
      aria-disabled={isLooking || !claimGate.passed}
    >
      <span>{claimGate.passed ? `${moment.count} found · click to browse` : "Claim not backed"}</span>
      <strong>{moment.title}</strong>
      <small>{claimGate.passed ? moment.answer : "This replay is hidden until the full product claim is backed."}</small>
    </button>
  );
}

function catalogIdForMoment(momentId: string | undefined) {
  if (momentId === "line_break_with_underneath_outlet") return "line-break-supported";
  if (momentId === "line_break_no_underneath_support") return "line-break-isolated";
  if (momentId === "high_bypass_completed_pass") return "high-bypass";
  return null;
}

function payloadsFromResponse(response: CoachInterpretResponse) {
  if (response.status !== "moment_found") return [];
  return response.moments
    .map((moment) => moment.replay_payload)
    .filter((payload): payload is NonNullable<typeof payload> => Boolean(payload))
    .map((payload) => payload as unknown as CoachMomentPayload);
}

function MomentContext({ payload, matches }: { payload: CoachMomentPayload; matches: MatchSummary[] }) {
  const moment = payload.moment;
  const match = matches.find((item) => item.match_id === moment.match_id);
  const fallback = MATCH_CONTEXT_FALLBACKS[moment.match_id];
  const attack = teamName(match, moment.perspective_team_role, fallback);
  const defend = teamName(match, moment.defending_team_role, fallback);
  return (
    <div className="coachMomentContext" aria-label="Match and team context">
      <div>
        <span>{moment.match_id}</span>
        <strong>{match?.match_title ?? fallback?.title ?? "Observed match"}</strong>
        <span>{periodLabel(moment.period)} · {clockLabel(moment.reception_frame_id, payload.replay.frame_rate_hz)}</span>
      </div>
      <div className="coachTeamLegend">
        <span><i className="attackSwatch" />{attack} on ball</span>
        <span><i className="defenseSwatch" />{defend} defending</span>
      </div>
    </div>
  );
}

function MomentTrustControls({
  payload,
  overlayMode,
  instanceCount,
  instanceIndex,
  onInstanceChange,
  onOverlayModeChange
}: {
  payload: CoachMomentPayload;
  overlayMode: MomentOverlayMode;
  instanceCount: number;
  instanceIndex: number;
  onInstanceChange: (index: number) => void;
  onOverlayModeChange: (mode: MomentOverlayMode) => void;
}) {
  const retention = possessionRetention(payload);
  return (
    <div className="coachTrustControls" aria-label="Replay inspection controls">
      <div>
        <span>Possession feed</span>
        <strong>{retentionCopy(retention)}</strong>
      </div>
      <div className="coachInstanceControls" aria-label="Found moment browser">
        <button
          type="button"
          onClick={() => onInstanceChange(instanceIndex - 1)}
          disabled={instanceIndex <= 0}
          aria-label="Previous found moment"
        >
          Previous
        </button>
        <span>{instanceCount > 0 ? `${instanceIndex + 1} of ${instanceCount}` : "No replay"}</span>
        <button
          type="button"
          onClick={() => onInstanceChange(instanceIndex + 1)}
          disabled={instanceIndex >= instanceCount - 1}
          aria-label="Next found moment"
        >
          Next
        </button>
      </div>
      <div className="coachOverlayToggle" role="group" aria-label="Replay overlay mode">
        <button
          type="button"
          className={overlayMode === "clean" ? "isActive" : ""}
          onClick={() => onOverlayModeChange("clean")}
        >
          Clean replay
        </button>
        <button
          type="button"
          className={overlayMode === "evidence" ? "isActive" : ""}
          onClick={() => onOverlayModeChange("evidence")}
        >
          Evidence overlay
        </button>
      </div>
    </div>
  );
}

function possessionRetention(payload: CoachMomentPayload) {
  return (payload.moment as { possession_retention?: Record<string, unknown> }).possession_retention ?? null;
}

function retentionCopy(retention: Record<string, unknown> | null) {
  if (!retention) return "Eight-second replay after reception.";
  const seconds = Number(retention.observed_seconds_after_reception ?? retention.required_retention_seconds ?? 0);
  const rounded = Number.isFinite(seconds) && seconds > 0 ? `${seconds.toFixed(seconds % 1 === 0 ? 0 : 1)}s` : "the follow-through";
  if (retention.status === "PASS") return `Provider possession stays with the same team for ${rounded}.`;
  if (retention.status === "FAIL") return `Provider possession changes during ${rounded}.`;
  return "Provider possession is unknown in this replay.";
}

function teamName(match: MatchSummary | undefined, role: string, fallback: { home: string; away: string } | undefined) {
  if (!match) {
    if (role === "home") return fallback?.home ?? "Home";
    if (role === "away") return fallback?.away ?? "Away";
    return role;
  }
  if (role === "home") return match.home_team_brand?.short_name || match.home_team;
  if (role === "away") return match.away_team_brand?.short_name || match.away_team;
  return role;
}

function periodLabel(period: string) {
  if (period === "secondHalf") return "Second half";
  if (period === "firstHalf") return "First half";
  return "Period";
}

function clockLabel(frameId: number, frameRateHz: number) {
  const rate = Number.isFinite(frameRateHz) && frameRateHz > 0 ? frameRateHz : 25;
  const totalSeconds = Math.max(0, Math.round(frameId / rate));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function responseCopy(result: CoachInterpretResponse | null, isLooking: boolean, error: string | null, fallback: string) {
  if (error) return error;
  if (isLooking) return "Looking through this match.";
  if (result) return result.display_answer;
  return fallback;
}
