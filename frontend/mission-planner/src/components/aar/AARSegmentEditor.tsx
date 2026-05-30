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
import type { AARSegment } from '../../types/aar';

interface AARSegmentEditorProps {
  segments: AARSegment[];
  onSegmentsChange: (segments: AARSegment[]) => void;
  availableWaypoints: string[];
}

export function AARSegmentEditor({
  segments,
  onSegmentsChange,
  availableWaypoints,
}: AARSegmentEditorProps) {
  const [newSegment, setNewSegment] = useState<Partial<AARSegment>>({});

  const formatOverrideForInput = (value?: string | null) => {
    if (!value) {
      return '';
    }
    const normalized = value.endsWith('Z') ? value : `${value}Z`;
    return normalized.slice(0, 16);
  };

  const toUtcOverride = (value: string) => {
    if (!value) {
      return null;
    }
    return `${value}:00Z`;
  };

  const updateSegmentOverride = (
    index: number,
    field: 'override_start_time' | 'override_end_time',
    value: string
  ) => {
    onSegmentsChange(
      segments.map((segment, segmentIndex) =>
        segmentIndex === index
          ? { ...segment, [field]: toUtcOverride(value) }
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
          id: crypto.randomUUID(),
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
          Optional UTC overrides let operators enter wind-adjusted,
          pilot-projected AR start/end times. Saving the leg persists these
          times and regenerates the preview/export from the adjusted boundaries.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Start Waypoint</TableHead>
              <TableHead>End Waypoint</TableHead>
              <TableHead>Override Start (UTC)</TableHead>
              <TableHead>Override End (UTC)</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {segments.map((segment, index) => (
              <TableRow key={segment.id}>
                <TableCell>{segment.start_waypoint_name}</TableCell>
                <TableCell>{segment.end_waypoint_name}</TableCell>
                <TableCell>
                  <Input
                    type="datetime-local"
                    value={formatOverrideForInput(segment.override_start_time)}
                    onChange={(event) =>
                      updateSegmentOverride(
                        index,
                        'override_start_time',
                        event.target.value
                      )
                    }
                    aria-label={`Override start time for ${segment.start_waypoint_name}`}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="datetime-local"
                    value={formatOverrideForInput(segment.override_end_time)}
                    onChange={(event) =>
                      updateSegmentOverride(
                        index,
                        'override_end_time',
                        event.target.value
                      )
                    }
                    aria-label={`Override end time for ${segment.end_waypoint_name}`}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => clearSegmentOverrides(index)}
                    >
                      Clear Times
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
            ))}
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
                  Uses waypoint time unless set after adding.
                </span>
              </TableCell>
              <TableCell>
                <span className="text-xs text-muted-foreground">
                  Uses waypoint time unless set after adding.
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
