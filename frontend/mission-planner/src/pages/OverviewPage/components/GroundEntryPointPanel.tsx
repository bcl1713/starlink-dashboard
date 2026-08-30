import { MapPin } from 'lucide-react';
import { type ReactNode } from 'react';

import { Button } from '../../../components/ui/button';
import type { GroundEntryPoint } from '../../../types/monitoring';
import { formatCoordinates } from '../formatters';
import { formatUtcTimestamp } from './metric-panel-time';
import { OverviewPanelState } from './OverviewPanelState';
import type { RetryOverviewPanel } from './metric-panel-types';
import type { OverviewSourceSlot } from '../overview-data-types';

export interface GroundEntryPointPanelProps {
  readonly slot: OverviewSourceSlot<GroundEntryPoint>;
  readonly retryPending: boolean;
  readonly onRetry?: RetryOverviewPanel;
  readonly headingAs?: 'h2' | 'h3';
  readonly onFocusCoordinates?: (
    coordinates: Readonly<{ latitude: number; longitude: number }>
  ) => void;
}

export function GroundEntryPointPanel(
  props: GroundEntryPointPanelProps
): ReactNode {
  const slot = projectGroundEntryPointSlot(props.slot);
  return (
    <OverviewPanelState
      title="Ground Entry Point"
      slot={slot}
      retryPending={props.retryPending}
      onRetry={props.onRetry}
      headingAs={props.headingAs}
    >
      {(gep) => {
        const hasCoordinates = gep.available && validCoordinates(gep);
        return (
          <div className="space-y-4">
            <dl className="grid gap-3 sm:grid-cols-2">
              <Detail
                label="Display"
                value={gep.available ? gep.display : null}
              />
              <Detail label="City" value={gep.available ? gep.city : null} />
              <Detail
                label="Region"
                value={gep.available ? gep.region : null}
              />
              <Detail
                label="Country"
                value={gep.available ? gep.country : null}
              />
              <Detail
                label="Coordinates"
                value={
                  hasCoordinates
                    ? formatCoordinates(gep.latitude, gep.longitude)
                    : null
                }
              />
              <Detail
                label="Observed"
                value={
                  gep.available && gep.observed_at
                    ? formatUtcTimestamp(gep.observed_at)
                    : null
                }
              />
            </dl>
            {hasCoordinates && props.onFocusCoordinates ? (
              <Button
                type="button"
                size="lg"
                variant="outline"
                onClick={() =>
                  props.onFocusCoordinates?.({
                    latitude: gep.latitude,
                    longitude: gep.longitude,
                  })
                }
              >
                <MapPin className="mr-2 h-4 w-4" aria-hidden="true" />
                Focus map
              </Button>
            ) : null}
          </div>
        );
      }}
    </OverviewPanelState>
  );
}

function projectGroundEntryPointSlot(
  slot: OverviewSourceSlot<GroundEntryPoint>
): OverviewSourceSlot<GroundEntryPoint> {
  if (slot.data?.available !== false) return slot;
  return {
    ...slot,
    availability: 'unavailable',
    phase: slot.phase === 'ready' ? 'unavailable' : slot.phase,
  };
}

function Detail(props: {
  readonly label: string;
  readonly value: string | null;
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{props.label}</dt>
      <dd className="text-sm font-semibold">{props.value ?? 'Unavailable'}</dd>
    </div>
  );
}

function validCoordinates(
  gep: GroundEntryPoint
): gep is GroundEntryPoint & { latitude: number; longitude: number } {
  return (
    typeof gep.latitude === 'number' &&
    Number.isFinite(gep.latitude) &&
    gep.latitude >= -90 &&
    gep.latitude <= 90 &&
    typeof gep.longitude === 'number' &&
    Number.isFinite(gep.longitude) &&
    gep.longitude >= -180 &&
    gep.longitude <= 180
  );
}
