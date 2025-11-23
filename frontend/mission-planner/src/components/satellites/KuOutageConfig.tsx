import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import type { KuOutage } from '../../types/satellite';

interface KuOutageConfigProps {
  outages: KuOutage[];
  onOutagesChange: (outages: KuOutage[]) => void;
}

export function KuOutageConfig({
  outages,
  onOutagesChange,
}: KuOutageConfigProps) {
  const [newOutage, setNewOutage] = useState<Partial<KuOutage>>({});

  const handleAddOutage = () => {
    if (
      newOutage.start_waypoint_index !== undefined &&
      newOutage.end_waypoint_index !== undefined
    ) {
      onOutagesChange([
        ...outages,
        {
          start_waypoint_index: newOutage.start_waypoint_index,
          end_waypoint_index: newOutage.end_waypoint_index,
          start_waypoint_name: newOutage.start_waypoint_name || '',
          end_waypoint_name: newOutage.end_waypoint_name || '',
          reason: newOutage.reason,
        },
      ]);
      setNewOutage({});
    }
  };

  const handleRemoveOutage = (index: number) => {
    onOutagesChange(outages.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">Ku/Starlink Outage Windows</h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Start Index</TableHead>
              <TableHead>Start Name</TableHead>
              <TableHead>End Index</TableHead>
              <TableHead>End Name</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {outages.map((outage, index) => (
              <TableRow key={index}>
                <TableCell>{outage.start_waypoint_index}</TableCell>
                <TableCell>{outage.start_waypoint_name}</TableCell>
                <TableCell>{outage.end_waypoint_index}</TableCell>
                <TableCell>{outage.end_waypoint_name}</TableCell>
                <TableCell>{outage.reason || 'N/A'}</TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleRemoveOutage(index)}
                  >
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell>
                <Input
                  type="number"
                  placeholder="Start index"
                  value={newOutage.start_waypoint_index ?? ''}
                  onChange={(e) =>
                    setNewOutage({
                      ...newOutage,
                      start_waypoint_index: parseInt(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  placeholder="Start name"
                  value={newOutage.start_waypoint_name ?? ''}
                  onChange={(e) =>
                    setNewOutage({
                      ...newOutage,
                      start_waypoint_name: e.target.value,
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  placeholder="End index"
                  value={newOutage.end_waypoint_index ?? ''}
                  onChange={(e) =>
                    setNewOutage({
                      ...newOutage,
                      end_waypoint_index: parseInt(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  placeholder="End name"
                  value={newOutage.end_waypoint_name ?? ''}
                  onChange={(e) =>
                    setNewOutage({
                      ...newOutage,
                      end_waypoint_name: e.target.value,
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  placeholder="Reason (optional)"
                  value={newOutage.reason ?? ''}
                  onChange={(e) =>
                    setNewOutage({ ...newOutage, reason: e.target.value })
                  }
                />
              </TableCell>
              <TableCell>
                <Button onClick={handleAddOutage}>Add</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
