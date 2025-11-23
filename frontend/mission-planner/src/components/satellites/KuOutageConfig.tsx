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
    if (newOutage.start_time && newOutage.end_time) {
      onOutagesChange([
        ...outages,
        {
          start_time: newOutage.start_time,
          end_time: newOutage.end_time,
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
              <TableHead>Start Time</TableHead>
              <TableHead>End Time</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {outages.map((outage, index) => (
              <TableRow key={index}>
                <TableCell>{new Date(outage.start_time).toLocaleString()}</TableCell>
                <TableCell>{new Date(outage.end_time).toLocaleString()}</TableCell>
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
                  type="datetime-local"
                  value={newOutage.start_time ?? ''}
                  onChange={(e) =>
                    setNewOutage({
                      ...newOutage,
                      start_time: e.target.value,
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  type="datetime-local"
                  value={newOutage.end_time ?? ''}
                  onChange={(e) =>
                    setNewOutage({
                      ...newOutage,
                      end_time: e.target.value,
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
