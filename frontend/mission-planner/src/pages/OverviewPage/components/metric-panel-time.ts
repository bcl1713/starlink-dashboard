import { formatAwareTimestampUtc } from '../../../services/monitoring-timestamp-internal';

export function formatUtcTimestamp(timestamp: string): string {
  return formatAwareTimestampUtc(timestamp) ?? 'Unavailable';
}
