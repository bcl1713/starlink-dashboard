import { ChevronDown, ChevronUp } from 'lucide-react';
import {
  type ReactNode,
  useCallback,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';

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
  const [hasOverflow, setHasOverflow] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const tableRef = useRef<HTMLTableElement | null>(null);
  const id = useId();
  const rows = props.rows.slice(-300);
  const caption =
    props.rows.length > 300
      ? `Latest 300 of ${props.rows.length} samples`
      : props.caption;

  const measureOverflow = useCallback(() => {
    const scroller = scrollerRef.current;
    if (scroller === null) {
      setHasOverflow(false);
      return;
    }
    try {
      setHasOverflow(scroller.scrollWidth > scroller.clientWidth);
    } catch {
      setHasOverflow(false);
    }
  }, []);

  useLayoutEffect(() => {
    if (!tableOpen) return undefined;
    const scroller = scrollerRef.current;
    if (scroller === null) return undefined;
    let observer: ResizeObserver | null = null;
    try {
      observer = new ResizeObserver(() => measureOverflow());
      observer.observe(scroller);
      if (tableRef.current !== null) observer.observe(tableRef.current);
    } catch {
      try {
        observer?.disconnect();
      } catch {
        // ignored
      }
      return undefined;
    }
    return () => {
      try {
        observer?.disconnect();
      } catch {
        // ignored
      }
    };
  }, [measureOverflow, props.rows, props.series, tableOpen]);

  return (
    <div className="space-y-3">
      <Button
        type="button"
        size="lg"
        variant="outline"
        aria-expanded={tableOpen}
        aria-controls={id}
        onClick={() =>
          setTableOpen((open) => {
            if (open) setHasOverflow(false);
            return !open;
          })
        }
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
          ref={tableRef}
          containerRef={scrollerRef}
          containerClassName="overflow-x-auto"
          containerProps={{
            id,
            role: 'region',
            'aria-label': 'Metric history table',
            tabIndex: hasOverflow ? 0 : undefined,
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
