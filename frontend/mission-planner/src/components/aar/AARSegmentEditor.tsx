import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import type { AARSegment } from '../../types/aar';

interface AARSegmentEditorProps {
  segments: AARSegment[];
  onSegmentsChange: (segments: AARSegment[]) => void;
}

export function AARSegmentEditor({
  segments,
  onSegmentsChange,
}: AARSegmentEditorProps) {
  const [newSegment, setNewSegment] = useState<Partial<AARSegment>>({});

  const handleAddSegment = () => {
    if (
      newSegment.name &&
      newSegment.start_waypoint_index !== undefined &&
      newSegment.end_waypoint_index !== undefined
    ) {
      onSegmentsChange([
        ...segments,
        {
          id: crypto.randomUUID(),
          name: newSegment.name,
          start_waypoint_index: newSegment.start_waypoint_index,
          end_waypoint_index: newSegment.end_waypoint_index,
          start_waypoint_name: newSegment.start_waypoint_name || '',
          end_waypoint_name: newSegment.end_waypoint_name || '',
          altitude_feet: newSegment.altitude_feet,
          notes: newSegment.notes,
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
              <TableHead>Name</TableHead>
              <TableHead>Start Index</TableHead>
              <TableHead>Start Name</TableHead>
              <TableHead>End Index</TableHead>
              <TableHead>End Name</TableHead>
              <TableHead>Altitude (ft)</TableHead>
              <TableHead>Notes</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {segments.map((segment, index) => (
              <TableRow key={segment.id}>
                <TableCell>{segment.name}</TableCell>
                <TableCell>{segment.start_waypoint_index}</TableCell>
                <TableCell>{segment.start_waypoint_name}</TableCell>
                <TableCell>{segment.end_waypoint_index}</TableCell>
                <TableCell>{segment.end_waypoint_name}</TableCell>
                <TableCell>{segment.altitude_feet || 'N/A'}</TableCell>
                <TableCell>{segment.notes || 'N/A'}</TableCell>
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
                <Input
                  placeholder="Segment name"
                  value={newSegment.name ?? ''}
                  onChange={(e) =>
                    setNewSegment({ ...newSegment, name: e.target.value })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  placeholder="Start index"
                  value={newSegment.start_waypoint_index ?? ''}
                  onChange={(e) =>
                    setNewSegment({
                      ...newSegment,
                      start_waypoint_index: parseInt(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  placeholder="Start name"
                  value={newSegment.start_waypoint_name ?? ''}
                  onChange={(e) =>
                    setNewSegment({
                      ...newSegment,
                      start_waypoint_name: e.target.value,
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  placeholder="End index"
                  value={newSegment.end_waypoint_index ?? ''}
                  onChange={(e) =>
                    setNewSegment({
                      ...newSegment,
                      end_waypoint_index: parseInt(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  placeholder="End name"
                  value={newSegment.end_waypoint_name ?? ''}
                  onChange={(e) =>
                    setNewSegment({
                      ...newSegment,
                      end_waypoint_name: e.target.value,
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  placeholder="Altitude"
                  value={newSegment.altitude_feet ?? ''}
                  onChange={(e) =>
                    setNewSegment({
                      ...newSegment,
                      altitude_feet: parseInt(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  placeholder="Notes"
                  value={newSegment.notes ?? ''}
                  onChange={(e) =>
                    setNewSegment({ ...newSegment, notes: e.target.value })
                  }
                />
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
