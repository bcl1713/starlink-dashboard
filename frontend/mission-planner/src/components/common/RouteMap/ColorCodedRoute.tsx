import React, { useMemo } from 'react';
import { Polyline, Popup } from 'react-leaflet';
import type { LatLngExpression } from 'leaflet';
import type { Timeline, TimelineSegment } from '../../../services/timeline';

interface ColorCodedRouteProps {
  timeline: Timeline | null;
  isIDLCrossing: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  nominal: 'var(--status-nominal)',
  sof: 'var(--status-advisory)',
  advisory: 'var(--status-advisory)',
  degraded: 'var(--status-degraded)',
  critical: 'var(--status-critical)',
};

function displayStatus(status: string): string {
  return status.toLowerCase() === 'sof' ? 'ADVISORY' : status.toUpperCase();
}

interface SegmentPolyline {
  coordinates: LatLngExpression[];
  segment: TimelineSegment;
  color: string;
}

/**
 * Maps segment timestamps to route coordinates using samples
 */
function mapSegmentsToCoordinates(
  timeline: Timeline,
  isIDLCrossing: boolean
): SegmentPolyline[] {
  if (!timeline.samples || timeline.samples.length === 0) {
    return [];
  }

  const samples = timeline.samples;
  const segments = timeline.segments || [];

  const result: SegmentPolyline[] = [];

  for (const segment of segments) {
    const startTime = new Date(segment.start_time).getTime();
    const endTime = new Date(segment.end_time).getTime();

    // Find samples that fall within this segment's time range
    const segmentSamples = samples.filter((sample) => {
      const sampleTime = new Date(sample.timestamp).getTime();
      return sampleTime >= startTime && sampleTime <= endTime;
    });

    if (segmentSamples.length > 0) {
      const coordinates: LatLngExpression[] = segmentSamples.map((sample) => [
        sample.latitude,
        isIDLCrossing && sample.longitude < 0
          ? sample.longitude + 360
          : sample.longitude,
      ]);

      const statusKey = segment.status.toLowerCase();
      const color = STATUS_COLORS[statusKey] || 'var(--muted-foreground)';

      result.push({
        coordinates,
        segment,
        color,
      });
    }
  }

  return result;
}

export const ColorCodedRoute: React.FC<ColorCodedRouteProps> = ({
  timeline,
  isIDLCrossing,
}) => {
  const segmentPolylines = useMemo(() => {
    if (!timeline) {
      return [];
    }
    return mapSegmentsToCoordinates(timeline, isIDLCrossing);
  }, [timeline, isIDLCrossing]);

  if (segmentPolylines.length === 0) {
    return null;
  }

  return (
    <>
      {segmentPolylines.map((polyline, index) => (
        <Polyline
          key={`segment-${index}`}
          positions={polyline.coordinates}
          pathOptions={{
            color: polyline.color,
            weight: 5,
            opacity: 0.85,
            lineCap: 'round',
            lineJoin: 'round',
          }}
          interactive={true}
        >
          <Popup>
            <div className="text-sm">
              <div className="font-semibold capitalize">
                Status: {displayStatus(polyline.segment.status)}
              </div>
              <div className="text-xs text-muted-foreground">
                {new Date(polyline.segment.start_time).toLocaleTimeString(
                  'en-US',
                  {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false,
                    timeZone: 'UTC',
                  }
                )}{' '}
                -{' '}
                {new Date(polyline.segment.end_time).toLocaleTimeString(
                  'en-US',
                  {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false,
                    timeZone: 'UTC',
                  }
                )}
              </div>
            </div>
          </Popup>
        </Polyline>
      ))}
    </>
  );
};
