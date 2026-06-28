import { FormEvent, useMemo, useState } from "react";
import { coachInterpret } from "./api";
import { MomentZeroPitch, momentZeroEvidence, type MomentZeroPayload } from "./MomentZero";
import type { CoachInterpretResponse } from "./types";

const DEFAULT_QUERY = "Show line breaks with no underneath outlet";
const EXAMPLES = [
  "Show line breaks with no underneath outlet",
  "Show expected pass completion",
  "Show dangerous attacks"
];

export function CoachSurface() {
  const examples = useMemo(() => EXAMPLES, []);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [result, setResult] = useState<CoachInterpretResponse | null>(null);
  const [activePayload, setActivePayload] = useState<MomentZeroPayload>(momentZeroEvidence);
  const [runId, setRunId] = useState(0);
  const [isLooking, setIsLooking] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        setRunId((value) => value + 1);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The moment could not be loaded.");
    } finally {
      setIsLooking(false);
    }
  };

  const isMoment = !result || result.status === "moment_found";

  return (
    <main className="coachShell">
      <section className={isMoment ? "coachExperience isMoment" : "coachExperience"} aria-label="Priori coach preview">
        <div className="coachHeader">
          <span className="coachBrand">Priori</span>
          <h1>Speak football. See the moment.</h1>
        </div>

        <div className="coachTheater" aria-label="Observed football moment preview">
          <MomentZeroPitch key={runId} payload={activePayload} />
        </div>

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
          <p className={isLooking ? "coachResponse isLoading" : "coachResponse"}>{responseCopy(result, isLooking, error)}</p>
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

function responseCopy(result: CoachInterpretResponse | null, isLooking: boolean, error: string | null) {
  if (error) return error;
  if (isLooking) return "Looking across the matches.";
  if (result) return result.display_answer;
  return "Try an observable football idea.";
}
