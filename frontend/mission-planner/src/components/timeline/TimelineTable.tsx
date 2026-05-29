import React, { useMemo } from 'react';
import { type Timeline, type TimelineSegment } from '../../services/timeline';

interface TimelineTableProps {
  timeline: Timeline | null;
  isLoading?: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  nominal: 'bg-green-100 text-green-800',
  sof: 'bg-blue-100 text-blue-800',
  degraded: 'bg-yellow-200 text-black',
  critical: 'bg-red-100 text-red-800',
};

const STATUS_BADGE_COLORS: Record<string, string> = {
  nominal: 'bg-green-500',
  sof: 'bg-blue-500',
  degraded: 'bg-yellow-500',
  critical: 'bg-red-500',
};

function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'UTC',
    });
  } catch {
    return isoString;
  }
}

function calculateDuration(start: string, end: string): string {
  try {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const durationMs = endDate.getTime() - startDate.getTime();
    const minutes = Math.floor(durationMs / 60000);
    const seconds = Math.floor((durationMs % 60000) / 1000);

    if (minutes === 0) {
      return `${seconds}s`;
    }
    return `${minutes}m ${seconds}s`;
  } catch {
    return 'N/A';
  }
}

function metadataString(segment: TimelineSegment, key: string): string | null {
  const value = segment.metadata?.[key];
  return typeof value === 'string' && value.trim() ? value : null;
}

function metadataStringList(segment: TimelineSegment, key: string): string[] {
  const value = segment.metadata?.[key];
  if (Array.isArray(value)) {
    return value.filter(
      (item): item is string =>
        typeof item === 'string' && item.trim().length > 0
    );
  }
  if (typeof value === 'string' && value.trim()) {
    return [value];
  }
  return [];
}

function availabilityLabel(segment: TimelineSegment): string {
  return metadataString(segment, 'availability_label') || segment.status;
}

function callPosture(segment: TimelineSegment): string {
  return metadataString(segment, 'call_posture') || segment.status;
}

function primaryReason(segment: TimelineSegment): string {
  return (
    metadataString(segment, 'primary_reason') || segment.reasons?.[0] || '—'
  );
}

function systemsAffected(segment: TimelineSegment): string {
  const systems = metadataStringList(segment, 'systems_affected');
  return systems.length > 0 ? systems.join(', ') : '—';
}

function notesAndSources(segment: TimelineSegment): string[] {
  const notes = metadataStringList(segment, 'notes');
  const sources = metadataStringList(segment, 'source_reasons');
  const values = [...notes, ...sources];
  return values.filter((item, index) => values.indexOf(item) === index);
}

export const TimelineTable: React.FC<TimelineTableProps> = ({
  timeline,
  isLoading = false,
}) => {
  const displaySegments = useMemo(() => {
    if (!timeline || !timeline.segments) {
      return [];
    }
    // For virtualization support in future, just return all segments for now
    return timeline.segments;
  }, [timeline]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
        <span className="ml-3 text-gray-600">Calculating preview...</span>
      </div>
    );
  }

  if (!timeline || displaySegments.length === 0) {
    return (
      <div className="p-4 text-gray-500 text-center">
        No timeline data available
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Segment
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Call Posture
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Primary Reason
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Start Time (UTC)
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              End Time (UTC)
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Duration
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Systems Affected
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Notes / Source Events
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {displaySegments.map((segment: TimelineSegment, index: number) => {
            const sourceNotes = notesAndSources(segment);
            const statusKey = segment.status.toLowerCase();
            const bodyTextClass =
              statusKey === 'degraded' ? 'text-black' : 'text-gray-700';
            return (
              <tr
                key={segment.id || index}
                className={`hover:bg-gray-50 ${STATUS_COLORS[statusKey] || ''}`}
              >
                <td className={`px-4 py-2 ${bodyTextClass}`}>{index + 1}</td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        STATUS_BADGE_COLORS[statusKey] || 'bg-gray-400'
                      }`}
                    ></div>
                    <span className="font-medium">
                      {availabilityLabel(segment)}
                    </span>
                  </div>
                  <div className="text-xs text-gray-600">
                    {callPosture(segment)}
                  </div>
                </td>
                <td className={`px-4 py-2 text-xs ${bodyTextClass}`}>
                  {primaryReason(segment)}
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  {formatTime(segment.start_time)}
                </td>
                <td className="px-4 py-2 font-mono text-xs">
                  {formatTime(segment.end_time)}
                </td>
                <td className="px-4 py-2">
                  {calculateDuration(segment.start_time, segment.end_time)}
                </td>
                <td className="px-4 py-2 text-xs">
                  {systemsAffected(segment)}
                </td>
                <td className="px-4 py-2 text-xs">
                  {sourceNotes.length > 0 ? (
                    <div className="space-y-1">
                      {sourceNotes.slice(0, 2).map((note, i) => (
                        <div
                          key={i}
                          className="bg-gray-200 px-2 py-1 rounded text-gray-700"
                        >
                          {note}
                        </div>
                      ))}
                      {sourceNotes.length > 2 && (
                        <div className="text-gray-500">
                          +{sourceNotes.length - 2} more
                        </div>
                      )}
                    </div>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
