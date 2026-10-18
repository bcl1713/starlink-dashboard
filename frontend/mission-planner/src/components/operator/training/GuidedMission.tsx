import { useState } from 'react';
import {
  createProgress,
  loadProgress,
  moveProgress,
  resetProgress,
  revisitStage,
  saveProgress,
  type TrainingIdentity,
  type TrainingProgress,
} from './trainingProgress';
import {
  evaluateStep,
  trainingSteps,
  type TrainingEvidence,
  type TrainingStageId,
} from './trainingSteps';
import { TrainingStep } from './TrainingStep';

const storage = {
  getItem: (key: string) => window.localStorage.getItem(key),
  setItem: (key: string, value: string) =>
    window.localStorage.setItem(key, value),
  removeItem: (key: string) => window.localStorage.removeItem(key),
};
interface Props {
  identity: TrainingIdentity;
  evidence: TrainingEvidence;
  onOpenTarget: (stage: TrainingStageId) => void;
  onDismiss: () => void;
  onCheckEvidence?: () => Promise<void>;
}
export function GuidedMission(props: Props) {
  return <Guide key={JSON.stringify(props.identity)} {...props} />;
}
function Guide({
  identity,
  evidence,
  onOpenTarget,
  onDismiss,
  onCheckEvidence,
}: Props) {
  const [initial] = useState(() => loadProgress(storage, identity));
  const [progress, setProgress] = useState(
    () => initial.progress ?? createProgress(identity)
  );
  const [error, setError] = useState<string | null>(initial.error);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [observation, setObservation] = useState('');
  const [root, setRoot] = useState('');
  const step = trainingSteps.find((item) => item.id === progress.currentStage)!;
  const evaluation = evaluateStep(
    step.id,
    { ...evidence, available: evidence.available && !checkError },
    progress
  );
  function keep(next: TrainingProgress) {
    setProgress(next);
    setError(saveProgress(storage, next).error);
  }
  async function check() {
    if (!onCheckEvidence) return;
    setChecking(true);
    setCheckError(null);
    try {
      await onCheckEvidence();
    } catch (reason) {
      setCheckError(
        reason instanceof Error
          ? reason.message
          : 'Could not check current evidence.'
      );
    } finally {
      setChecking(false);
    }
  }
  return (
    <aside
      aria-label="Guided mission walkthrough"
      className="space-y-4 rounded border p-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p>Private training · Simulation</p>
        <button className="ws-button" onClick={onDismiss}>
          Dismiss guide
        </button>
      </div>
      {error && (
        <p role="alert">
          Guide progress could not be saved or resumed: {error} Current work
          stays in this window.
        </p>
      )}
      {checkError && <p role="alert">Evidence check failed: {checkError}</p>}
      {!expanded ? (
        <div className="flex flex-wrap items-center gap-2">
          <p>
            {step.id} · {step.title}
          </p>
          <button className="ws-button" onClick={() => setExpanded(true)}>
            Resume guide instructions
          </button>
        </div>
      ) : (
        <>
          <label>
            Lesson
            <select
              className="ws-field"
              value={step.id}
              onChange={(event) => {
                setObservation('');
                keep(
                  revisitStage(progress, event.target.value as TrainingStageId)
                );
              }}
            >
              {trainingSteps.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.id} · {item.title}
                </option>
              ))}
            </select>
          </label>
          <TrainingStep stageId={step.id} evaluation={evaluation} />
          <button
            className="ws-button"
            onClick={() => {
              setExpanded(false);
              onOpenTarget(step.id);
            }}
          >
            Open lesson controls
          </button>
          {onCheckEvidence && (
            <button
              className="ws-button"
              disabled={checking}
              onClick={() => void check()}
            >
              {checking
                ? 'Checking current evidence…'
                : 'Check current evidence'}
            </button>
          )}
          {step.manual.length > 0 && (
            <fieldset className="space-y-2">
              <legend>Human observations</legend>
              <label>
                What did you observe?
                <textarea
                  className="ws-field"
                  value={observation}
                  onChange={(event) => setObservation(event.target.value)}
                />
              </label>
              {step.manual.map((outcome) => (
                <button
                  className="ws-button"
                  key={outcome}
                  disabled={!observation.trim()}
                  onClick={() => {
                    keep({
                      ...progress,
                      manualEvidence: [
                        ...progress.manualEvidence.filter(
                          (item) => item.outcomeId !== outcome
                        ),
                        {
                          outcomeId: outcome,
                          observedAt: new Date().toISOString(),
                          note: observation.trim(),
                        },
                      ],
                    });
                    setObservation('');
                  }}
                >
                  Record observation: {outcome.replaceAll('-', ' ')}
                </button>
              ))}
            </fieldset>
          )}
          <p>
            Next moves through instructions. It does not complete a lesson. Back
            never undoes saved actions; Skip remains separate from Passed.
          </p>
          <nav aria-label="Guide navigation" className="flex flex-wrap gap-2">
            <button
              className="ws-button"
              disabled={step.id === 'T01'}
              onClick={() => keep(moveProgress(progress, 'back'))}
            >
              Back
            </button>
            <button
              className="ws-button"
              onClick={() => keep(moveProgress(progress, 'skip'))}
            >
              Skip lesson
            </button>
            <button
              className="ws-button"
              disabled={step.id === 'T11'}
              onClick={() => keep(moveProgress(progress, 'next'))}
            >
              Next lesson
            </button>
          </nav>
          <details>
            <summary>Restart and reset</summary>
            <p>
              Reset guide progress only clears this guide’s navigation and
              observations. It does not delete records, drafts or pending
              commands.
            </p>
            <button
              className="ws-button"
              onClick={() => {
                const result = resetProgress(storage, identity);
                setError(result.error);
                if (!result.error) {
                  setProgress(createProgress(identity));
                  setObservation('');
                }
              }}
            >
              Reset guide progress
            </button>
            <p>
              Reset mission stops the owned training instance, retains its old
              private data and starts a fresh sibling root. Run the local
              launcher from the repository on your nonproduction computer; then
              open the new address and select its training mission. Replay may
              need to be started again through Missions; no exact replay frame
              is restored.
            </p>
            <label>
              Private training root from your launcher output
              <input
                className="ws-field"
                value={root}
                onChange={(event) => setRoot(event.target.value)}
                placeholder="/path/to/private-training-root"
              />
            </label>
            {root.trim() && (
              <pre className="overflow-auto whitespace-pre-wrap">
                scripts/operator-training.sh reset --root{' '}
                {"'" + root.trim().replaceAll("'", "'\\''") + "'"}
              </pre>
            )}
          </details>
        </>
      )}
    </aside>
  );
}
