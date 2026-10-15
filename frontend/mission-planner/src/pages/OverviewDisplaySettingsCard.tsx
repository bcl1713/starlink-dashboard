import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useOverviewDisplayController } from '@/hooks/useOverviewDisplayController';
import type {
  CommandFeedback,
  DisplayPeer,
} from '@/services/overview-display-protocol';

function commandMessage(
  feedback: CommandFeedback | null,
  peer: DisplayPeer | undefined
): string | null {
  if (!feedback || feedback.targetId !== peer?.id) return null;
  switch (feedback.status) {
    case 'pending':
      return 'Waiting for the Overview display to acknowledge…';
    case 'accepted':
      return 'Recenter accepted. The view is returning to its current automatic camera behavior.';
    case 'unsupported':
      return 'Recenter is unavailable on this display.';
    case 'timeout':
      return 'Request timed out. The display did not acknowledge within three seconds; check its actual state before retrying.';
    case 'expired':
      return 'Request expired. Try again from Configuration.';
    case 'unavailable':
      return 'Selected display unavailable. Choose an available Overview display.';
    case 'failed':
      return 'The display could not complete the request. Please try again.';
  }
}

export function OverviewDisplaySettingsCard(): React.JSX.Element {
  const { available, peers, feedback, send } = useOverviewDisplayController();
  const [selection, setSelection] = useState({
    id: '',
    explicit: false,
    requireChoice: false,
    lost: false,
  });
  const [popup, setPopup] = useState<{
    before: string[];
    status: 'waiting' | 'opened' | 'blocked';
  } | null>(null);
  const selected = peers.find((peer) => peer.id === selection.id);
  // Reconcile discovery before painting controls, so a second/lost peer cannot
  // leave a briefly actionable automatic target on screen.
  if (selection.id && !selected) {
    setSelection({ id: '', explicit: false, requireChoice: true, lost: true });
  } else if (
    peers.length > 1 &&
    !selection.explicit &&
    !selection.requireChoice
  ) {
    setSelection({ ...selection, id: '', requireChoice: true });
  } else if (peers.length === 1 && !selection.id && !selection.requireChoice) {
    setSelection({ ...selection, id: peers[0].id });
  }
  if (
    popup &&
    popup.status !== 'opened' &&
    peers.some((peer) => !popup.before.includes(peer.id))
  ) {
    setPopup({ ...popup, status: 'opened' });
  }
  useEffect(() => {
    if (popup?.status !== 'waiting') return;
    const timer = setTimeout(
      () =>
        setPopup((current) =>
          current?.status === 'waiting'
            ? { ...current, status: 'blocked' }
            : current
        ),
      3000
    );
    return () => clearTimeout(timer);
  }, [popup]);
  const pending = feedback?.status === 'pending';
  const message = !available
    ? 'Remote controls unavailable in this browser. Open Overview and use its local controls.'
    : (commandMessage(feedback, selected) ??
      (popup?.status === 'waiting'
        ? 'Waiting for the new Overview display to connect…'
        : popup?.status === 'opened'
          ? 'Overview display connected.'
          : null));
  const canSend = (action: 'recenter') =>
    available && selected?.actions.includes(action) && !pending;
  return (
    <Card className="min-w-0" role="region" aria-label="Overview displays">
      <CardHeader>
        <CardTitle>
          <h2>Overview displays</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Control an Overview window in this browser. Match its displayed label
          before sending a command.
        </p>
        {peers.length === 0 && <p>No Overview displays connected.</p>}
        {selection.lost && (
          <p>
            Selected display disconnected. Choose a display explicitly to
            continue.
          </p>
        )}
        <label className="block space-y-1">
          <span>Overview display</span>
          <select
            className="min-h-11 w-full rounded border bg-background px-3 focus-visible:outline-2 focus-visible:outline-ring"
            value={selected?.id ?? ''}
            disabled={!available || peers.length === 0}
            onChange={(event) =>
              setSelection({
                id: event.target.value,
                explicit: true,
                requireChoice: true,
                lost: false,
              })
            }
          >
            <option value="">Choose an Overview display</option>
            {peers.map((peer) => (
              <option key={peer.id} value={peer.id}>
                {peer.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={!canSend('recenter')}
            onClick={() => {
              if (selected) send(selected.id, 'recenter');
            }}
          >
            Recenter view
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={popup?.status === 'waiting'}
            onClick={() => {
              // noopener can return null even when the popup opens. Discovery is
              // the acknowledgment, never the returned window handle.
              setPopup({
                before: peers.map((peer) => peer.id),
                status: 'waiting',
              });
              try {
                window.open('/overview', '_blank', 'noopener');
              } catch {
                /* Discovery timeout supplies actionable guidance. */
              }
            }}
          >
            Open Overview
          </Button>
        </div>
        {message && <p role="status">{message}</p>}
        {popup?.status === 'blocked' && (
          <p role="alert">
            No new Overview display connected. Check popup blocking and allow
            popups for this site, or open Overview in a separate window.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
