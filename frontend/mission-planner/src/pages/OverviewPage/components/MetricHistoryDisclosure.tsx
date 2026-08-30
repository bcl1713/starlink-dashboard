import { ChevronDown, ChevronUp } from 'lucide-react';
import { type ReactNode, useId, useState } from 'react';

import { Button } from '../../../components/ui/button';
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../../components/ui/table';
import { formatUtcTimestamp } from './metric-panel-time';
import type { TimeSeriesDefinition, TimeSeriesRow } from './metric-panel-types';

interface MetricHistoryDisclosureProps {
  readonly rows: readonly TimeSeriesRow[];
  readonly series: readonly TimeSeriesDefinition[];
  readonly caption: string;
}

export function MetricHistoryDisclosure(
  props: MetricHistoryDisclosureProps
): ReactNode {
  const [tableOpen, setTableOpen] = useState(false);
  const id = useId();
  const rows = props.rows.slice(-300);
  const caption =
    props.rows.length > 300
      ? `Latest 300 of ${props.rows.length} samples`
      : props.caption;

  return (
    <div className="space-y-3">
      <Button
        type="button"
        size="lg"
        variant="outline"
        aria-expanded={tableOpen}
        aria-controls={id}
        onClick={() => setTableOpen((open) => !open)}
      >
        {tableOpen ? (
          <ChevronUp className="mr-2 h-4 w-4" aria-hidden="true" />
        ) : (
          <ChevronDown className="mr-2 h-4 w-4" aria-hidden="true" />
        )}
        History
      </Button>
      {tableOpen ? (
        <Table
          containerClassName="overflow-x-auto"
          containerProps={{
            id,
            role: 'region',
            'aria-label': 'Metric history table',
            tabIndex: props.rows.length > 300 ? 0 : undefined,
          }}
        >
          <TableCaption>{caption}</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Timestamp</TableHead>
              {props.series.map((series) => (
                <TableHead key={series.key}>{series.label}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={`${row.timestamp}-${row.epochSeconds}`}>
                <TableCell>
                  <time dateTime={row.timestamp}>
                    {formatUtcTimestamp(row.timestamp)}
                  </time>
                </TableCell>
                {props.series.map((series, index) => (
                  <TableCell key={series.key}>
                    {formatTableValue(row.values[index], series)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}

function formatTableValue(
  value: number | null | undefined,
  series: TimeSeriesDefinition
): string {
  if (typeof value !== 'number' || !Number.isFinite(value))
    return 'Unavailable';
  return `${value.toFixed(1)} ${series.unit}`;
}
