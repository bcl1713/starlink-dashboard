import React, { useMemo } from 'react';
import { Polyline, Popup } from 'react-leaflet';
import type { LatLngExpression } from 'leaflet';
import type { Timeline, TimelineSegment } from '../../../services/timeline';

interface ColorCodedRouteProps {
  timeline: Timeline | null;
}

const STATUS_COLORS: Record<string, string> = {
  nominal: '#2ecc71', // Green
  degraded: '#f1c40f', // Yellow
  critical: '#e74c3c', // Red
};

interface SegmentPolyline {
  coordinates: LatLngExpression[];
  segment: TimelineSegment;
  color: string;
}

/**
 * Maps segment timestamps to route coordinates using samples
 */
function mapSegmentsToCoordinates(timeline: Timeline): SegmentPolyline[] {
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
        sample.longitude,
      ]);

      const color = STATUS_COLORS[segment.status.toLowerCase()] || '#95a5a6';

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
}) => {
  const segmentPolylines = useMemo(() => {
    if (!timeline) {
      return [];
    }
    return mapSegmentsToCoordinates(timeline);
  }, [timeline]);

  if (segmentPolylines.length === 0) {
    return null;
  }

  return (
    <>
      {segmentPolylines.map((polyline, index) => (
        <Polyline
          key={`segment-${index}`}
          positions={polyline.coordinates}
          color={polyline.color}
          weight={5}
          opacity={0.85}
          lineCap="round"
          lineJoin="round"
          interactive={true}
        >
          <Popup>
            <div className="text-sm">
              <div className="font-semibold capitalize">
                Status: {polyline.segment.status}
              </div>
              <div className="text-xs text-gray-600">
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
