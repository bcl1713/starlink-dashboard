import { useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import type { KaOutage } from '../../types/satellite';

interface KaOutageConfigProps {
  outages: KaOutage[];
  onOutagesChange: (outages: KaOutage[]) => void;
}

// Helper to calculate end time for display
const calculateEndTime = (startTime: string, durationSeconds: number): string => {
  const start = new Date(startTime);
  const end = new Date(start.getTime() + durationSeconds * 1000);
  return end.toISOString().slice(0, 16); // Format for datetime-local
};

// Helper to calculate duration from times
const calculateDuration = (startTime: string, endTime: string): number => {
  const start = new Date(startTime).getTime();
  const end = new Date(endTime).getTime();
  return Math.max(0, (end - start) / 1000); // seconds
};

interface NewOutageInput {
  start_time: string;
  end_time: string;
}

export function KaOutageConfig({
  outages,
  onOutagesChange,
}: KaOutageConfigProps) {
  const [newOutage, setNewOutage] = useState<Partial<NewOutageInput>>({});

  const handleAddOutage = () => {
    if (newOutage.start_time && newOutage.end_time) {
      const durationSeconds = calculateDuration(newOutage.start_time, newOutage.end_time);
      onOutagesChange([
        ...outages,
        {
          id: crypto.randomUUID(),
          start_time: newOutage.start_time,
          duration_seconds: durationSeconds,
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
        <h3 className="text-sm font-medium mb-2">Ka Outage Windows</h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Start Time</TableHead>
              <TableHead>Duration (hours)</TableHead>
              <TableHead>End Time</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {outages.map((outage, index) => (
              <TableRow key={outage.id}>
                <TableCell>{new Date(outage.start_time).toLocaleString()}</TableCell>
                <TableCell>{(outage.duration_seconds / 3600).toFixed(2)}</TableCell>
                <TableCell>{new Date(new Date(outage.start_time).getTime() + outage.duration_seconds * 1000).toLocaleString()}</TableCell>
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
                {newOutage.start_time && newOutage.end_time && (
                  <span>
                    {(calculateDuration(newOutage.start_time, newOutage.end_time) / 3600).toFixed(2)}
                  </span>
                )}
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
                <Button onClick={handleAddOutage}>Add</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
