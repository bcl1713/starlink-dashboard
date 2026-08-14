import { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { createClientId } from '@/lib/clientId';
import type { AARSegment } from '../../types/aar';

interface AARSegmentEditorProps {
  segments: AARSegment[];
  onSegmentsChange: (segments: AARSegment[]) => void;
  availableWaypoints: string[];
}

const ELAPSED_PATTERN = /^T\+\d{1,3}:\d{2}(?::\d{2})?$/i;

function normalizeElapsedInput(value: string) {
  const trimmed = value.trim().toUpperCase();
  if (!trimmed) {
    return null;
  }
  const withPrefix = trimmed.startsWith('T+') ? trimmed : `T+${trimmed}`;
  return ELAPSED_PATTERN.test(withPrefix) ? withPrefix : trimmed;
}

export function AARSegmentEditor({
  segments,
  onSegmentsChange,
  availableWaypoints,
}: AARSegmentEditorProps) {
  const [newSegment, setNewSegment] = useState<Partial<AARSegment>>({});

  const updateSegmentElapsedOverride = (index: number, value: string) => {
    const normalized = normalizeElapsedInput(value);
    onSegmentsChange(
      segments.map((segment, segmentIndex) =>
        segmentIndex === index
          ? {
              ...segment,
              override_start_elapsed: normalized,
              override_start_time: null,
              override_end_time: null,
            }
          : segment
      )
    );
  };

  const clearSegmentOverrides = (index: number) => {
    onSegmentsChange(
      segments.map((segment, segmentIndex) =>
        segmentIndex === index
          ? {
              ...segment,
              override_start_elapsed: null,
              override_start_time: null,
              override_end_time: null,
            }
          : segment
      )
    );
  };

  // Calculate available end waypoints (only those after the start waypoint)
  const getAvailableEndWaypoints = () => {
    if (!newSegment.start_waypoint_name) {
      return [];
    }
    const startIndex = availableWaypoints.indexOf(
      newSegment.start_waypoint_name
    );
    if (startIndex === -1) {
      return [];
    }
    // Return only waypoints after the start waypoint
    return availableWaypoints.slice(startIndex + 1);
  };

  const availableEndWaypoints = getAvailableEndWaypoints();

  const handleAddSegment = () => {
    if (newSegment.start_waypoint_name && newSegment.end_waypoint_name) {
      onSegmentsChange([
        ...segments,
        {
          id: createClientId(),
          start_waypoint_name: newSegment.start_waypoint_name,
          end_waypoint_name: newSegment.end_waypoint_name,
        },
      ]);
      setNewSegment({});
    }
  };

  const handleRemoveSegment = (index: number) => {
    onSegmentsChange(segments.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">AAR Segments</h3>
        <p className="mb-3 text-xs text-muted-foreground">
          Enter flight-deck AR timing as a mission-elapsed start value such as
          T+07:12. The original AR duration is preserved automatically, so AREX
          shifts by the same delta when the ARIP override changes.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Start Waypoint</TableHead>
              <TableHead>End Waypoint</TableHead>
              <TableHead>Override AR Start (T+HH:MM)</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {segments.map((segment, index) => {
              const elapsedValue = segment.override_start_elapsed ?? '';
              const elapsedIsValid =
                !elapsedValue || ELAPSED_PATTERN.test(elapsedValue);
              return (
                <TableRow key={segment.id}>
                  <TableCell>{segment.start_waypoint_name}</TableCell>
                  <TableCell>{segment.end_waypoint_name}</TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <Input
                        placeholder="T+00:00"
                        value={elapsedValue}
                        onChange={(event) =>
                          updateSegmentElapsedOverride(
                            index,
                            event.target.value
                          )
                        }
                        aria-label={`Mission elapsed AR start for ${segment.start_waypoint_name}`}
                      />
                      <p className="text-xs text-muted-foreground">
                        Preserves AR duration and shifts AREX automatically.
                      </p>
                      {!elapsedIsValid && (
                        <p className="text-xs text-destructive">
                          Use T+HH:MM or T+HH:MM:SS.
                        </p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => clearSegmentOverrides(index)}
                      >
                        Clear T+
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleRemoveSegment(index)}
                      >
                        Remove
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            <TableRow>
              <TableCell>
                <Select
                  value={newSegment.start_waypoint_name ?? ''}
                  onValueChange={(value) =>
                    setNewSegment({
                      ...newSegment,
                      start_waypoint_name: value,
                      end_waypoint_name: undefined,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Start waypoint" />
                  </SelectTrigger>
                  <SelectContent className="max-h-[300px]">
                    {availableWaypoints.map((waypoint) => (
                      <SelectItem key={waypoint} value={waypoint}>
                        {waypoint}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <Select
                  value={newSegment.end_waypoint_name ?? ''}
                  onValueChange={(value) =>
                    setNewSegment({ ...newSegment, end_waypoint_name: value })
                  }
                  disabled={!newSegment.start_waypoint_name}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="End waypoint" />
                  </SelectTrigger>
                  <SelectContent className="max-h-[300px]">
                    {availableEndWaypoints.map((waypoint) => (
                      <SelectItem key={waypoint} value={waypoint}>
                        {waypoint}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <span className="text-xs text-muted-foreground">
                  Optional after adding; defaults to waypoint timing.
                </span>
              </TableCell>
              <TableCell>
                <Button onClick={handleAddSegment}>Add</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
