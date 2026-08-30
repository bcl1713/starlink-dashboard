import { type ReactNode, useId } from 'react';

import { Button } from '../../../components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '../../../components/ui/card';
import type { OverviewPanelStateProps } from './metric-panel-types';

export function OverviewPanelState<T>(
  props: OverviewPanelStateProps<T>
): ReactNode {
  const headingId = useId();
  const Heading = props.headingAs ?? 'h2';
  const state = panelState(props.slot);
  const hasData = props.slot.data !== undefined;
  const showRetry =
    props.onRetry !== undefined &&
    (state.kind === 'error' || state.kind === 'stale');

  const retry = () => {
    try {
      void Promise.resolve(props.onRetry?.()).catch(() => undefined);
    } catch {
      // Retry failures are announced by Task9 source state, not local state.
    }
  };

  return (
    <Card role="region" aria-labelledby={headingId}>
      <CardHeader>
        <CardTitle>
          <Heading id={headingId} className="text-base font-semibold">
            {props.title}
          </Heading>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">{state.text}</p>
          {showRetry ? (
            <Button
              type="button"
              size="lg"
              variant="outline"
              disabled={props.retryPending}
              onClick={retry}
            >
              Retry
            </Button>
          ) : null}
        </div>
        {hasData ? props.children(props.slot.data as T) : null}
      </CardContent>
    </Card>
  );
}

function panelState<T>(slot: OverviewPanelStateProps<T>['slot']) {
  if (
    slot.data === undefined &&
    slot.pending &&
    slot.phase === 'initial-loading'
  ) {
    return { kind: 'loading', text: 'Loading' } as const;
  }
  if (slot.error !== null || slot.phase === 'error') {
    return {
      kind: 'error',
      text: slot.error?.message ?? 'Source refresh failed.',
    } as const;
  }
  if (slot.availability === 'unavailable') {
    return { kind: 'unavailable', text: 'Unavailable' } as const;
  }
  if (slot.paused || slot.phase === 'paused') {
    return { kind: 'paused', text: 'Paused' } as const;
  }
  if (slot.freshness === 'stale' || slot.phase === 'stale') {
    return { kind: 'stale', text: 'Stale' } as const;
  }
  if (slot.data !== undefined && slot.pending) {
    return { kind: 'refreshing', text: 'Refreshing' } as const;
  }
  if (slot.data !== undefined) return { kind: 'ready', text: 'Ready' } as const;
  return { kind: 'unknown', text: 'Unavailable' } as const;
}
