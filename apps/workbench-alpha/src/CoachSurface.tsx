import { useEffect, useMemo, useState } from "react";
import { fetchCoachCatalog, fetchMatches } from "./api";
import { CoachMomentPitch, momentHighBypassEvidence, type CoachMomentPayload } from "./MomentZero";
import type { CoachInterpretResponse, MatchSummary } from "./types";

const HIGH_BYPASS_CLAIM_KIND = "high_bypass_completed_pass";
const MATCH_CONTEXT_FALLBACKS: Record<string, { title: string; home: string; away: string }> = {
  J03WOH: { title: "Fortuna Dusseldorf:SSV Jahn Regensburg", home: "Fortuna", away: "Jahn Regensburg" }
};
const PASS_LENGTH_FILTERS = [
  { value: "all", label: "Any length", min: 0 },
  { value: "15", label: "15m+", min: 15 },
  { value: "25", label: "25m+", min: 25 },
  { value: "35", label: "35m+", min: 35 }
] as const;
const PASS_PROGRESS_FILTERS = [
  { value: "all", label: "Any progress", min: 0 },
  { value: "8", label: "+8m", min: 8 },
  { value: "20", label: "+20m", min: 20 },
  { value: "30", label: "+30m", min: 30 }
] as const;
const ORIGIN_FILTERS = [
  { value: "all", label: "Any origin" },
  { value: "own_half", label: "Own half" },
  { value: "middle_third", label: "Middle" },
  { value: "final_third", label: "Final third" }
] as const;
const PLAY_PHASE_FILTERS = [
  { value: "open_play", label: "Open play" },
  { value: "all", label: "All phases" },
  { value: "restart", label: "Restarts" },
  { value: "unknown", label: "Unknown" }
] as const;

type LengthFilter = (typeof PASS_LENGTH_FILTERS)[number]["value"];
type ProgressFilter = (typeof PASS_PROGRESS_FILTERS)[number]["value"];
type OriginFilter = (typeof ORIGIN_FILTERS)[number]["value"];
type PhaseFilter = (typeof PLAY_PHASE_FILTERS)[number]["value"];

type FilterOption = {
  value: string;
  label: string;
  count: number;
};

type MomentFilters = {
  match: string;
  team: string;
  length: LengthFilter;
  progress: ProgressFilter;
  origin: OriginFilter;
  phase: PhaseFilter;
};

export function CoachSurface() {
  const [activeInstances, setActiveInstances] = useState<CoachMomentPayload[]>([momentHighBypassEvidence]);
  const [activeInstanceIndex, setActiveInstanceIndex] = useState(0);
  const [filters, setFilters] = useState<MomentFilters>({
    match: "all",
    team: "all",
    length: "all",
    progress: "all",
    origin: "all",
    phase: "open_play"
  });
  const [matches, setMatches] = useState<MatchSummary[]>([]);
  const [runId, setRunId] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cleanInstances = useMemo(() => activeInstances.filter(isCleanControlReplay), [activeInstances]);
  const visibleInstances = useMemo(
    () => filteredCatalogInstances(cleanInstances, filters, matches),
    [cleanInstances, filters, matches]
  );
  const matchOptionInstances = useMemo(
    () => filteredCatalogInstances(cleanInstances, { ...filters, match: "all" }, matches),
    [cleanInstances, filters, matches]
  );
  const teamOptionInstances = useMemo(
    () => filteredCatalogInstances(cleanInstances, { ...filters, team: "all" }, matches),
    [cleanInstances, filters, matches]
  );
  const activePayload = visibleInstances[activeInstanceIndex] ?? visibleInstances[0] ?? null;
  const matchOptions = useMemo(() => catalogMatchOptions(matchOptionInstances, matches), [matchOptionInstances, matches]);
  const teamOptions = useMemo(
    () => catalogTeamOptions(teamOptionInstances, filters.match, matches),
    [teamOptionInstances, filters.match, matches]
  );

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

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    fetchCoachCatalog(HIGH_BYPASS_CLAIM_KIND)
      .then((next) => {
        if (cancelled) return;
        const payloads = payloadsFromResponse(next);
        if (next.status === "moment_found" && payloads.length > 0) {
          setActiveInstances(payloads);
          setActiveInstanceIndex(0);
          setFilters({
            match: "all",
            team: "all",
            length: "all",
            progress: "all",
            origin: "all",
            phase: "open_play"
          });
          setRunId((value) => value + 1);
        }
      })
      .catch(() => {
        if (!cancelled) setError("The high-bypass clean-control catalog could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (activeInstanceIndex >= visibleInstances.length) {
      setActiveInstanceIndex(0);
    }
  }, [activeInstanceIndex, visibleInstances.length]);

  const chooseInstance = (nextIndex: number) => {
    if (visibleInstances.length <= 0) return;
    const bounded = Math.max(0, Math.min(visibleInstances.length - 1, nextIndex));
    if (bounded === activeInstanceIndex) return;
    setActiveInstanceIndex(bounded);
    setRunId((value) => value + 1);
  };

  const updateFilters = (patch: Partial<MomentFilters>) => {
    setFilters((current) => ({
      ...current,
      ...patch,
      ...(patch.match ? { team: "all" } : null)
    }));
    setActiveInstanceIndex(0);
    setRunId((value) => value + 1);
  };

  return (
    <main className="coachShell">
      <section className="coachExperience isMoment" aria-label="Priori high-bypass replay browser">
        <div className="coachHeader">
          <span className="coachBrand">Priori</span>
          <h1>High-bypass control.</h1>
        </div>

        <section className="coachFocusSummary" aria-label="Current replay family">
          <div>
            <span>Clean-control browser</span>
            <strong>One pass bypasses five or more opponents, then the receiver keeps clean control.</strong>
          </div>
          <p>{visibleInstances.length} of {cleanInstances.length} clean replays match the current filters.</p>
        </section>

        <div className="coachTheater" aria-label="Observed high-bypass replay">
          {activePayload ? (
            <>
              <MomentContext payload={activePayload} matches={matches} />
              <CoachMomentPitch key={runId} payload={activePayload} overlayMode="clean" />
              <MomentTrustControls
                payload={activePayload}
                instanceCount={visibleInstances.length}
                instanceIndex={activeInstanceIndex}
                onInstanceChange={chooseInstance}
              />
            </>
          ) : (
            <NoReplayState isLoading={isLoading} error={error} />
          )}
          <MomentFilterControls
            filters={filters}
            matchOptions={matchOptions}
            teamOptions={teamOptions}
            visibleCount={visibleInstances.length}
            totalCount={cleanInstances.length}
            onChange={updateFilters}
          />
        </div>
      </section>
    </main>
  );
}

function payloadsFromResponse(response: CoachInterpretResponse) {
  if (response.status !== "moment_found") return [];
  return response.moments
    .map((moment) => moment.replay_payload)
    .filter((payload): payload is NonNullable<typeof payload> => Boolean(payload))
    .map((payload) => payload as unknown as CoachMomentPayload);
}

function isCleanControlReplay(payload: CoachMomentPayload) {
  const clean = cleanControlRetention(payload);
  return (
    clean?.mode === "tracking_clean_team_control_after_reception_v0" &&
    clean.status === "PASS"
  );
}

function filteredCatalogInstances(
  payloads: CoachMomentPayload[],
  filters: MomentFilters,
  matches: MatchSummary[]
) {
  const lengthMin = thresholdMin(PASS_LENGTH_FILTERS, filters.length);
  const progressMin = thresholdMin(PASS_PROGRESS_FILTERS, filters.progress);
  return payloads.filter((payload) => {
    if (filters.match !== "all" && payload.moment.match_id !== filters.match) return false;
    if (filters.team !== "all" && attackingTeamKey(payload, matches) !== filters.team) return false;

    const lengthMeters = passLengthMeters(payload);
    if (lengthMin > 0 && (lengthMeters === null || lengthMeters < lengthMin)) return false;

    const progressMeters = passProgressionMeters(payload);
    if (progressMin > 0 && (progressMeters === null || progressMeters < progressMin)) return false;

    if (filters.origin !== "all" && passOriginZone(payload) !== filters.origin) return false;
    if (filters.phase !== "all" && passPhaseStatus(payload) !== filters.phase) return false;
    return true;
  });
}

function thresholdMin<T extends readonly { value: string; min: number }[]>(options: T, value: string) {
  return options.find((option) => option.value === value)?.min ?? 0;
}

function catalogMatchOptions(payloads: CoachMomentPayload[], matches: MatchSummary[]): FilterOption[] {
  const counts = new Map<string, number>();
  for (const payload of payloads) {
    counts.set(payload.moment.match_id, (counts.get(payload.moment.match_id) ?? 0) + 1);
  }
  const options = [...counts.entries()]
    .map(([matchId, count]) => ({
      value: matchId,
      label: matchLabel(matchId, matches),
      count
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: "all", label: "All matches", count: payloads.length }, ...options];
}

function catalogTeamOptions(payloads: CoachMomentPayload[], matchFilter: string, matches: MatchSummary[]): FilterOption[] {
  const scopedPayloads = matchFilter === "all" ? payloads : payloads.filter((payload) => payload.moment.match_id === matchFilter);
  const counts = new Map<string, { label: string; count: number }>();
  for (const payload of scopedPayloads) {
    const key = attackingTeamKey(payload, matches);
    const current = counts.get(key);
    counts.set(key, {
      label: attackingTeamLabel(payload, matches),
      count: (current?.count ?? 0) + 1
    });
  }
  const options = [...counts.entries()]
    .map(([value, item]) => ({ value, label: item.label, count: item.count }))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [{ value: "all", label: "All teams", count: scopedPayloads.length }, ...options];
}

function NoReplayState({ isLoading, error }: { isLoading: boolean; error: string | null }) {
  return (
    <div className="coachNoReplay" role="status">
      <span>{isLoading ? "Loading clean-control replays" : "No clean replay"}</span>
      <strong>{error ?? "No high-bypass clean-control replay matches these filters."}</strong>
    </div>
  );
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
        <strong>{formatMatchTitle(match?.match_title ?? fallback?.title ?? "Observed match")}</strong>
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
  instanceCount,
  instanceIndex,
  onInstanceChange
}: {
  payload: CoachMomentPayload;
  instanceCount: number;
  instanceIndex: number;
  onInstanceChange: (index: number) => void;
}) {
  const cleanControl = cleanControlRetention(payload);
  const facts = highBypassFacts(payload);
  return (
    <div className="coachTrustControls" aria-label="Replay inspection controls">
      <div>
        <span>Clean control</span>
        <strong>{cleanControlCopy(cleanControl)}</strong>
      </div>
      <div>
        <span>Pass facts</span>
        <strong>{facts}</strong>
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
    </div>
  );
}

function MomentFilterControls({
  filters,
  matchOptions,
  teamOptions,
  visibleCount,
  totalCount,
  onChange
}: {
  filters: MomentFilters;
  matchOptions: FilterOption[];
  teamOptions: FilterOption[];
  visibleCount: number;
  totalCount: number;
  onChange: (patch: Partial<MomentFilters>) => void;
}) {
  return (
    <div className="coachMomentFilters" aria-label="High-bypass filters">
      <div className="coachMatchFilter">
        <span>Match</span>
        <div className="coachMatchButtons" role="group" aria-label="Filter by match">
          {matchOptions.map((option) => (
            <button
              type="button"
              key={option.value}
              className={filters.match === option.value ? "isActive" : ""}
              onClick={() => onChange({ match: option.value })}
            >
              {option.label} <small>{option.count}</small>
            </button>
          ))}
        </div>
      </div>
      <div className="coachMomentFilterGrid">
        <label>
          <span>Phase</span>
          <select value={filters.phase} onChange={(event) => onChange({ phase: event.target.value as PhaseFilter })}>
            {PLAY_PHASE_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Team</span>
          <select value={filters.team} onChange={(event) => onChange({ team: event.target.value })}>
            {teamOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} ({option.count})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Origin</span>
          <select value={filters.origin} onChange={(event) => onChange({ origin: event.target.value as OriginFilter })}>
            {ORIGIN_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Pass length</span>
          <select value={filters.length} onChange={(event) => onChange({ length: event.target.value as LengthFilter })}>
            {PASS_LENGTH_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Pass progress</span>
          <select value={filters.progress} onChange={(event) => onChange({ progress: event.target.value as ProgressFilter })}>
            {PASS_PROGRESS_FILTERS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <strong>{visibleCount} of {totalCount} clean replays</strong>
      </div>
    </div>
  );
}

function highBypassFacts(payload: CoachMomentPayload) {
  const moment = momentRecord(payload);
  const bypassed = Number(moment.opponents_bypassed_count ?? requestedEvidence(payload).opponents_bypassed_count ?? 0);
  const lengthMeters = passLengthMeters(payload);
  const progression = passProgressionMeters(payload);
  const parts = [
    `${bypassed} bypassed`,
    lengthMeters === null ? null : `${lengthMeters.toFixed(1)}m pass`,
    progression === null ? null : `+${progression.toFixed(1)}m`,
    originLabel(passOriginZone(payload)),
    phaseLabel(payload)
  ].filter(Boolean);
  return parts.join(" · ");
}

function possessionRetention(payload: CoachMomentPayload) {
  return (payload.moment as { possession_retention?: Record<string, unknown> }).possession_retention ?? null;
}

function cleanControlRetention(payload: CoachMomentPayload) {
  return (payload.moment as { clean_control_retention?: Record<string, unknown> }).clean_control_retention ?? null;
}

function cleanControlCopy(cleanControl: Record<string, unknown> | null) {
  if (!cleanControl) return "Clean-control check unavailable.";
  const receiverSeconds = Number(cleanControl.receiver_clean_control_max_seconds ?? 0);
  const teamSeconds = Number(cleanControl.team_clean_control_max_seconds ?? 0);
  const movementSeconds = Number(cleanControl.receiver_ball_comovement_max_seconds ?? 0);
  if (cleanControl.status === "PASS") {
    return `Receiver ${receiverSeconds.toFixed(1)}s · movement ${movementSeconds.toFixed(1)}s · team ${teamSeconds.toFixed(1)}s.`;
  }
  const reason = String(cleanControl.reason ?? "not backed").replaceAll("_", " ");
  return `Not a clean-control replay: ${reason}.`;
}

function requestedEvidence(payload: CoachMomentPayload): Record<string, unknown> {
  return (payload.moment as { requested_evidence?: Record<string, unknown> }).requested_evidence ?? {};
}

function momentRecord(payload: CoachMomentPayload): Record<string, unknown> {
  return payload.moment as unknown as Record<string, unknown>;
}

function passLengthMeters(payload: CoachMomentPayload) {
  const moment = momentRecord(payload);
  const release = pointFrom(moment.release_ball_point ?? requestedEvidence(payload).release_ball_point);
  const reception = pointFrom(moment.reception_ball_point ?? requestedEvidence(payload).reception_ball_point);
  if (!release || !reception) return null;
  return Math.hypot(reception.x_m - release.x_m, reception.y_m - release.y_m);
}

function passProgressionMeters(payload: CoachMomentPayload) {
  const moment = momentRecord(payload);
  const raw = moment.forward_progression_m ?? requestedEvidence(payload).forward_progression_m;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function passOriginZone(payload: CoachMomentPayload): OriginFilter {
  const moment = momentRecord(payload);
  const release = pointFrom(moment.release_ball_point ?? requestedEvidence(payload).release_ball_point);
  if (!release) return "all";
  const attackingDirection = Number(moment.attacking_direction ?? 1);
  const attackX = release.x_m * (Number.isFinite(attackingDirection) && attackingDirection !== 0 ? attackingDirection : 1);
  if (attackX < 0) return "own_half";
  if (attackX < 17.5) return "middle_third";
  return "final_third";
}

function passPhaseStatus(payload: CoachMomentPayload): PhaseFilter {
  const value = String(momentRecord(payload).open_play_status ?? "unknown");
  if (value === "open_play" || value === "restart") return value;
  return "unknown";
}

function phaseLabel(payload: CoachMomentPayload) {
  const moment = momentRecord(payload);
  const status = passPhaseStatus(payload);
  if (status === "open_play") return "open play";
  if (status === "restart") {
    return restartLabel(String(moment.restart_type ?? "")) ?? "restart";
  }
  return "phase unknown";
}

function restartLabel(value: string) {
  if (value === "throw_in") return "throw-in";
  if (value === "free_kick") return "free kick";
  if (value === "corner_kick") return "corner";
  if (value === "goal_kick") return "goal kick";
  if (value === "kick_off") return "kick-off";
  if (value === "penalty") return "penalty";
  return null;
}

function pointFrom(value: unknown): { x_m: number; y_m: number } | null {
  if (!value || typeof value !== "object") return null;
  const point = value as { x_m?: unknown; y_m?: unknown };
  const x_m = Number(point.x_m);
  const y_m = Number(point.y_m);
  if (!Number.isFinite(x_m) || !Number.isFinite(y_m)) return null;
  return { x_m, y_m };
}

function originLabel(value: OriginFilter) {
  if (value === "own_half") return "own half origin";
  if (value === "middle_third") return "middle origin";
  if (value === "final_third") return "final-third origin";
  return "origin unknown";
}

function attackingTeamKey(payload: CoachMomentPayload, matches: MatchSummary[]) {
  return attackingTeamLabel(payload, matches).toLowerCase();
}

function attackingTeamLabel(payload: CoachMomentPayload, matches: MatchSummary[]) {
  const match = matches.find((item) => item.match_id === payload.moment.match_id);
  const fallback = MATCH_CONTEXT_FALLBACKS[payload.moment.match_id];
  return teamName(match, payload.moment.perspective_team_role, fallback);
}

function matchLabel(matchId: string, matches: MatchSummary[]) {
  const match = matches.find((item) => item.match_id === matchId);
  return formatMatchTitle(match?.match_title ?? MATCH_CONTEXT_FALLBACKS[matchId]?.title ?? matchId);
}

function teamName(match: MatchSummary | undefined, role: string, fallback: { home: string; away: string } | undefined) {
  if (!match) {
    if (role === "home") return fallback?.home ?? "Home";
    if (role === "away") return fallback?.away ?? "Away";
    return role;
  }
  if (role === "home") return readableTeamName(match.home_team_brand?.short_name || match.home_team, "Home");
  if (role === "away") return readableTeamName(match.away_team_brand?.short_name || match.away_team, "Opponent");
  return role;
}

function readableTeamName(name: string | undefined, fallback: string) {
  if (!name) return fallback;
  return /^J\d{2}[A-Z]{3}$/i.test(name) ? fallback : name;
}

function formatMatchTitle(title: string) {
  return title.replace(/:(?!\s)/g, ": ");
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
