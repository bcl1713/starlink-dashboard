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

  const handleAddSegment = () => {
    if (newSegment.start_waypoint && newSegment.end_waypoint) {
      onSegmentsChange([
        ...segments,
        {
          id: crypto.randomUUID(),
          start_waypoint: newSegment.start_waypoint,
          end_waypoint: newSegment.end_waypoint,
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
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Start Waypoint</TableHead>
              <TableHead>End Waypoint</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {segments.map((segment, index) => (
              <TableRow key={segment.id}>
                <TableCell>{segment.start_waypoint}</TableCell>
                <TableCell>{segment.end_waypoint}</TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleRemoveSegment(index)}
                  >
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>
                <Select
                  value={newSegment.start_waypoint ?? ''}
                  onValueChange={(value) =>
                    setNewSegment({ ...newSegment, start_waypoint: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Start waypoint" />
                  </SelectTrigger>
                  <SelectContent>
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
                  value={newSegment.end_waypoint ?? ''}
                  onValueChange={(value) =>
                    setNewSegment({ ...newSegment, end_waypoint: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="End waypoint" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableWaypoints.map((waypoint) => (
                      <SelectItem key={waypoint} value={waypoint}>
                        {waypoint}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
