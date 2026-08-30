import { type ReactNode, useMemo } from 'react';

import type { POIETAResponse } from '../../../types/monitoring';
import {
  formatETA,
  selectApplicablePOIs,
  classifyEtaUrgency,
} from '../formatters';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../../components/ui/table';
import { OverviewPanelState } from './OverviewPanelState';
import type { RetryOverviewPanel } from './metric-panel-types';
import type { OverviewSourceSlot } from '../overview-data-types';

export interface POIQuickReferenceProps {
  readonly slot: OverviewSourceSlot<POIETAResponse>;
  readonly retryPending: boolean;
  readonly onRetry?: RetryOverviewPanel;
  readonly headingAs?: 'h2' | 'h3';
}

export function POIQuickReference(props: POIQuickReferenceProps): ReactNode {
  return (
    <OverviewPanelState
      title="POI Quick Reference (Top 5)"
      slot={props.slot}
      retryPending={props.retryPending}
      onRetry={props.onRetry}
      headingAs={props.headingAs}
    >
      {(response) => <POITable response={response} />}
    </OverviewPanelState>
  );
}

function POITable({ response }: { readonly response: POIETAResponse }) {
  const selected = useMemo(
    () => selectApplicablePOIs(response.pois),
    [response.pois]
  );
  return (
    <Table>
      <TableCaption>POI Quick Reference (Top 5)</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead>ETA</TableHead>
          <TableHead>POI</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Course Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {selected.map((poi) => {
          const urgency = classifyEtaUrgency(poi.eta_seconds);
          return (
            <TableRow key={poi.poi_id}>
              <TableCell className="font-semibold">
                {formatETA(poi.eta_seconds)}
                <span className="ml-2 text-xs text-muted-foreground">
                  {urgency.label}
                </span>
              </TableCell>
              <TableCell>{poi.name}</TableCell>
              <TableCell>{poi.category ?? 'Unavailable'}</TableCell>
              <TableCell>{poi.course_status ?? 'Unavailable'}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
