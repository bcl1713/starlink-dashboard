import { useEffect, useRef, useState } from 'react';
import type { TrainingIdentity } from './trainingProgress';
import { armPrivateReceiptLoss } from './trainingReceiptLoss';

export function TrainingReceiptLoss({
  identity,
}: {
  identity: TrainingIdentity;
}) {
  const pending = useRef<AbortController | null>(null);
  const [armed, setArmed] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => () => pending.current?.abort(), []);
  async function arm() {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setArmed(true);
    setMessage('Checking the current marked private store…');
    try {
      await armPrivateReceiptLoss(identity, controller.signal, (reason) => {
        if (controller.signal.aborted) return;
        setArmed(false);
        setMessage(
          reason === 'withheld'
            ? 'One successful note response was withheld. Keep the uncertain draft and check current evidence before retry or restore.'
            : 'Exercise expired; no response was withheld.'
        );
      });
      if (!controller.signal.aborted)
        setMessage(
          'Armed for 60 seconds: create and save one private note normally. Its successful response will be withheld once. Other commands are unchanged.'
        );
    } catch (reason) {
      if (!controller.signal.aborted) {
        setArmed(false);
        setMessage(
          reason instanceof Error
            ? reason.message
            : 'Could not arm the private exercise.'
        );
      }
    }
  }
  return (
    <fieldset className="space-y-2 rounded border p-3">
      <legend>Private lost-receipt exercise</legend>
      <p>
        The normal backend save still runs. This exercise withholds one
        successful note response from this tab’s journal owner; it does not
        simulate an aircraft outage or create a replacement command.
      </p>
      <button className="ws-button" disabled={armed} onClick={() => void arm()}>
        Arm one note receipt loss
      </button>
      {armed && (
        <button
          className="ws-button"
          onClick={() => {
            pending.current?.abort();
            setArmed(false);
            setMessage(
              'Exercise canceled; no further response will be withheld.'
            );
          }}
        >
          Cancel receipt-loss exercise
        </button>
      )}
      {message && <p role="status">{message}</p>}
    </fieldset>
  );
}
