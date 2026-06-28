import { FormEvent, useEffect, useMemo, useState } from "react";
import { coachInterpret, fetchMatches } from "./api";
import {
  MomentZeroPitch,
  momentLineBreakSupportedEvidence,
  momentZeroEvidence,
  type MomentZeroPayload
} from "./MomentZero";
import type { CoachInterpretResponse, MatchSummary } from "./types";

const DEFAULT_QUERY = "Show line breaks with underneath support";
const EXAMPLES = [
  "Show line breaks with underneath support",
  "Show line breaks with no underneath outlet",
  "Show line breaks with two underneath outlets",
  "Show expected pass completion",
  "Show dangerous attacks"
];
const CATALOG_MOMENTS = [
  {
    id: "line-break-supported",
    title: "Line break, outlet arrives",
    query: "Show line breaks with underneath support",
    answer: "Line broken. Support arrives underneath.",
    count: 2,
    payload: momentLineBreakSupportedEvidence,
    mode: "supported"
  },
  {
    id: "line-break-isolated",
    title: "Line break, outlet absent",
    query: "Show line breaks with no underneath outlet",
    answer: "Line broken. The outlet space stays empty.",
    count: 3,
    payload: momentZeroEvidence,
    mode: "isolated"
  }
] as const;
const MATCH_CONTEXT_FALLBACKS: Record<string, { title: string; home: string; away: string }> = {
  J03WOH: { title: "Fortuna match J03WOH", home: "Fortuna", away: "J03WOH" }
};

export function CoachSurface() {
  const examples = useMemo(() => EXAMPLES, []);
  const catalogMoments = useMemo(() => CATALOG_MOMENTS, []);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [result, setResult] = useState<CoachInterpretResponse | null>(null);
  const [activePayload, setActivePayload] = useState<MomentZeroPayload>(momentLineBreakSupportedEvidence);
  const [activeCatalogId, setActiveCatalogId] = useState<string>(CATALOG_MOMENTS[0].id);
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [runId, setRunId] = useState(0);
  const [isLooking, setIsLooking] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const payload = next.moments[0]?.replay_payload;
      if (next.status === "moment_found" && payload) {
        setActivePayload(payload as unknown as MomentZeroPayload);
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
      const payload = next.moments[0]?.replay_payload;
      if (next.status === "moment_found" && payload) {
        setActivePayload(payload as unknown as MomentZeroPayload);
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
    setQuery(moment.query);
    setResult(null);
    setError(null);
    setActivePayload(moment.payload);
    setActiveCatalogId(moment.id);
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
          <MomentZeroPitch key={runId} payload={activePayload} />
        </div>

        <section className="coachCatalog" aria-label="Compiler-found moment catalog">
          <div className="coachCatalogHeader">
            <span>Real moments in this match</span>
            <strong>Compiler-found catalog</strong>
          </div>
          <div className="coachCatalogGrid">
            {catalogMoments.map((moment) => (
              <button
                type="button"
                key={moment.id}
                className={moment.id === activeCatalogId ? `coachMomentTile isActive ${moment.mode}` : `coachMomentTile ${moment.mode}`}
                onClick={() => chooseCatalogMoment(moment)}
                disabled={isLooking}
              >
                <span>{moment.count} found</span>
                <strong>{moment.title}</strong>
                <small>{moment.answer}</small>
              </button>
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

function catalogIdForMoment(momentId: string | undefined) {
  if (momentId === "line_break_with_underneath_outlet") return "line-break-supported";
  if (momentId === "line_break_no_underneath_support") return "line-break-isolated";
  return null;
}

function MomentContext({ payload, matches }: { payload: MomentZeroPayload; matches: MatchSummary[] }) {
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
