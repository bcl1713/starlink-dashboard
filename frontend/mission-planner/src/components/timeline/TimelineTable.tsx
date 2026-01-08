import React, { useMemo } from 'react';
import { type Timeline, type TimelineSegment } from '../../services/timeline';

interface TimelineTableProps {
  timeline: Timeline | null;
  isLoading?: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  nominal: 'bg-green-100 text-green-800',
  degraded: 'bg-yellow-100 text-yellow-800',
  critical: 'bg-red-100 text-red-800',
};

const STATUS_BADGE_COLORS: Record<string, string> = {
  nominal: 'bg-green-500',
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
              Status
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Start Time (UTC)
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Duration
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              X State
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Ka State
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Ku State
            </th>
            <th className="px-4 py-2 text-left font-semibold text-gray-700">
              Reasons
            </th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {displaySegments.map((segment: TimelineSegment, index: number) => (
            <tr
              key={segment.id || index}
              className={`hover:bg-gray-50 ${
                STATUS_COLORS[segment.status.toLowerCase()] || ''
              }`}
            >
              <td className="px-4 py-2 text-gray-700">{index + 1}</td>
              <td className="px-4 py-2">
                <div className="flex items-center gap-2">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      STATUS_BADGE_COLORS[segment.status.toLowerCase()] ||
                      'bg-gray-400'
                    }`}
                  ></div>
                  <span className="font-medium capitalize">
                    {segment.status}
                  </span>
                </div>
              </td>
              <td className="px-4 py-2 font-mono text-xs">
                {formatTime(segment.start_time)}
              </td>
              <td className="px-4 py-2">
                {calculateDuration(segment.start_time, segment.end_time)}
              </td>
              <td className="px-4 py-2 capitalize text-xs">
                {segment.x_state || 'unknown'}
              </td>
              <td className="px-4 py-2 capitalize text-xs">
                {segment.ka_state || 'unknown'}
              </td>
              <td className="px-4 py-2 capitalize text-xs">
                {segment.ku_state || 'unknown'}
              </td>
              <td className="px-4 py-2 text-xs">
                {segment.reasons && segment.reasons.length > 0 ? (
                  <div className="space-y-1">
                    {segment.reasons.slice(0, 2).map((reason, i) => (
                      <div
                        key={i}
                        className="bg-gray-200 px-2 py-1 rounded text-gray-700"
                      >
                        {reason}
                      </div>
                    ))}
                    {segment.reasons.length > 2 && (
                      <div className="text-gray-500">
                        +{segment.reasons.length - 2} more
                      </div>
                    )}
                  </div>
                ) : (
                  '-'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
