import { FormEvent, useMemo, useState } from "react";
import { coachExamplePrompts, interpretCoachQuery, type CoachInterpretation } from "./coachCompiler";
import { MomentZeroPitch, momentZeroEvidence } from "./MomentZero";

const DEFAULT_QUERY = "Show line breaks with no underneath outlet";

export function CoachSurface() {
  const examples = useMemo(() => coachExamplePrompts(), []);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [result, setResult] = useState<CoachInterpretation>(() => interpretCoachQuery(DEFAULT_QUERY));
  const [runId, setRunId] = useState(0);

  const submit = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    const next = interpretCoachQuery(query);
    setResult(next);
    if (next.kind === "moment") {
      setRunId((value) => value + 1);
    }
  };

  const chooseExample = (example: string) => {
    setQuery(example);
    const next = interpretCoachQuery(example);
    setResult(next);
    if (next.kind === "moment") {
      setRunId((value) => value + 1);
    }
  };

  const isMoment = result.kind === "moment";

  return (
    <main className="coachShell">
      <section className={isMoment ? "coachExperience isMoment" : "coachExperience"} aria-label="Priori coach preview">
        <div className="coachHeader">
          <span className="coachBrand">Priori</span>
          <h1>Speak football. See the moment.</h1>
        </div>

        <div className="coachTheater" aria-label="Observed football moment preview">
          <MomentZeroPitch key={runId} payload={momentZeroEvidence} />
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
            />
            <button type="submit">Show</button>
          </div>
          <p className="coachResponse">{responseCopy(result)}</p>
          <div className="coachPromptRail" aria-label="Example requests">
            {examples.map((example) => (
              <button type="button" key={example} onClick={() => chooseExample(example)}>
                {example}
              </button>
            ))}
          </div>
        </form>
      </section>
    </main>
  );
}

function responseCopy(result: CoachInterpretation) {
  if (result.kind === "moment") return result.display_answer;
  return result.prompt;
}
