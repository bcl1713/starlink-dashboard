import React, { useState } from 'react';
import type { Timeline } from '../../services/timeline';
import { TimelineTable } from './TimelineTable';

interface TimelinePreviewSectionProps {
  timeline: Timeline | null;
  isCalculating: boolean;
  isUnsaved?: boolean;
  error?: Error | null;
}

export const TimelinePreviewSection: React.FC<TimelinePreviewSectionProps> = ({
  timeline,
  isCalculating,
  isUnsaved = false,
  error = null,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between p-4 bg-gray-50 cursor-pointer hover:bg-gray-100 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <button
            type="button"
            className="text-gray-600 hover:text-gray-800"
            aria-expanded={isExpanded}
          >
            {isExpanded ? (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            ) : (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            )}
          </button>

          <h3 className="text-lg font-semibold text-gray-800">
            Timeline Preview
          </h3>

          {isUnsaved && (
            <span className="inline-block px-2 py-1 text-xs font-semibold text-red-800 bg-red-100 rounded">
              Unsaved
            </span>
          )}

          {isCalculating && (
            <span className="inline-block text-xs text-gray-600">
              (calculating...)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-sm text-gray-600">
          {timeline && timeline.segments && (
            <span>{timeline.segments.length} segments</span>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="p-4 bg-white">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-800 text-sm">
              {error.message}
            </div>
          )}

          <TimelineTable timeline={timeline} isLoading={isCalculating} />

          {timeline && timeline.statistics && (
            <div className="mt-4 pt-4 border-t grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm font-medium text-gray-600">
                  Total Duration
                </div>
                <div className="text-lg font-semibold text-gray-900">
                  {timeline.statistics.total_duration_seconds
                    ? `${Math.round(timeline.statistics.total_duration_seconds / 60)}m`
                    : 'N/A'}
                </div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-600">
                  Degraded Time
                </div>
                <div className="text-lg font-semibold text-yellow-700">
                  {timeline.statistics.degraded_duration_seconds
                    ? `${Math.round(timeline.statistics.degraded_duration_seconds / 60)}m`
                    : '0m'}
                </div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-600">
                  Critical Time
                </div>
                <div className="text-lg font-semibold text-red-700">
                  {timeline.statistics.critical_duration_seconds
                    ? `${Math.round(timeline.statistics.critical_duration_seconds / 60)}m`
                    : '0m'}
                </div>
              </div>
              <div>
                <div className="text-sm font-medium text-gray-600">
                  Nominal Time
                </div>
                <div className="text-lg font-semibold text-green-700">
                  {timeline.statistics.nominal_duration_seconds
                    ? `${Math.round(timeline.statistics.nominal_duration_seconds / 60)}m`
                    : '0m'}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
