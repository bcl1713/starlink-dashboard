import { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import type { ManualAARTrack, ManualAARTrackPoint } from '../../types/aar';

interface ManualAARTrackEditorProps {
  tracks: ManualAARTrack[];
  onSaveTrack: (track: ManualAARTrack) => Promise<void>;
  onRemoveTrack: (trackId: string) => void;
}

const isLatitude = (value: number) =>
  Number.isFinite(value) && value >= -90 && value <= 90;
const isLongitude = (value: number) =>
  Number.isFinite(value) && value >= -180 && value <= 180;

interface DraftPoint {
  latitude: string;
  longitude: string;
}

const emptyPoint = (): DraftPoint => ({ latitude: '', longitude: '' });

export function ManualAARTrackEditor({
  tracks,
  onSaveTrack,
  onRemoveTrack,
}: ManualAARTrackEditorProps) {
  const [name, setName] = useState('Manual AR Track');
  const [points, setPoints] = useState<DraftPoint[]>([
    emptyPoint(),
    emptyPoint(),
  ]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const updatePoint = (
    pointIndex: number,
    field: keyof DraftPoint,
    value: string
  ) => {
    setPoints((currentPoints) =>
      currentPoints.map((point, index) =>
        index === pointIndex ? { ...point, [field]: value } : point
      )
    );
  };

  const addTrack = async () => {
    setSuccess(null);
    if (!name.trim()) {
      setError('Enter a name for the manual AR track.');
      return;
    }
    if (points.length < 2) {
      setError('A manual AR track needs at least two points.');
      return;
    }
    if (
      points.some((point) => !point.latitude.trim() || !point.longitude.trim())
    ) {
      setError(
        'Enter both latitude and longitude for every manual AR track point.'
      );
      return;
    }
    const parsedPoints: ManualAARTrackPoint[] = points.map((point) => ({
      latitude: Number(point.latitude),
      longitude: Number(point.longitude),
    }));
    if (
      !parsedPoints.every(
        (point) => isLatitude(point.latitude) && isLongitude(point.longitude)
      )
    ) {
      setError('Latitude must be -90 to 90 and longitude must be -180 to 180.');
      return;
    }
    if (
      parsedPoints.some(
        (point, index) =>
          index > 0 &&
          point.latitude === parsedPoints[index - 1].latitude &&
          point.longitude === parsedPoints[index - 1].longitude
      )
    ) {
      setError('Adjacent manual AR track points cannot be duplicates.');
      return;
    }

    try {
      setIsSaving(true);
      await onSaveTrack({
        id: crypto.randomUUID(),
        name: name.trim(),
        points: parsedPoints,
      });
      setError(null);
      setSuccess('Manual AR track saved.');
      setPoints([emptyPoint(), emptyPoint()]);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? `Unable to save manual AR track: ${saveError.message}`
          : 'Unable to save manual AR track. Please try again.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium">Manual AR Tracks</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Add a deviation track by ordered latitude/longitude points. It is
          saved separately from the planned route and may cross the
          antimeridian.
        </p>
      </div>

      {tracks.map((track) => (
        <div key={track.id} className="rounded border p-3 text-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <strong>{track.name}</strong>
              <p className="text-xs text-muted-foreground">
                {track.points.length} operator-entered points
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => onRemoveTrack(track.id)}
            >
              Remove
            </Button>
          </div>
        </div>
      ))}

      <div className="space-y-3 rounded border p-3">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-label="Manual AR track name"
        />
        {points.map((point, index) => (
          <div key={index} className="flex items-center gap-2">
            <Input
              type="number"
              value={point.latitude}
              min={-90}
              max={90}
              step="any"
              aria-label={`Manual AR point ${index + 1} latitude`}
              onChange={(event) =>
                updatePoint(index, 'latitude', event.target.value)
              }
            />
            <Input
              type="number"
              value={point.longitude}
              min={-180}
              max={180}
              step="any"
              aria-label={`Manual AR point ${index + 1} longitude`}
              onChange={(event) =>
                updatePoint(index, 'longitude', event.target.value)
              }
            />
            <Button
              variant="outline"
              size="sm"
              disabled={points.length <= 2}
              onClick={() =>
                setPoints(
                  points.filter((_, pointIndex) => pointIndex !== index)
                )
              }
            >
              Remove
            </Button>
          </div>
        ))}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {success && (
          <p role="status" className="text-sm text-green-700">
            {success}
          </p>
        )}
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setPoints([...points, emptyPoint()])}
          >
            Add Point
          </Button>
          <Button onClick={addTrack} disabled={isSaving}>
            {isSaving
              ? 'Saving Manual AR Track...'
              : 'Save and Persist Manual AR Track'}
          </Button>
        </div>
      </div>
    </div>
  );
}
