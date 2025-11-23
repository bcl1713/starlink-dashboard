import { useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import type { XBandTransition } from '../../types/satellite';

interface XBandConfigProps {
  startingSatellite?: string;
  transitions: XBandTransition[];
  onStartingSatelliteChange: (satellite: string) => void;
  onTransitionsChange: (transitions: XBandTransition[]) => void;
  availableSatellites: string[];
}

export function XBandConfig({
  startingSatellite,
  transitions,
  onStartingSatelliteChange,
  onTransitionsChange,
  availableSatellites,
}: XBandConfigProps) {
  const [newTransition, setNewTransition] = useState<Partial<XBandTransition>>({});

  const handleAddTransition = () => {
    if (
      newTransition.latitude !== undefined &&
      newTransition.longitude !== undefined &&
      newTransition.to_satellite
    ) {
      onTransitionsChange([
        ...transitions,
        {
          latitude: newTransition.latitude,
          longitude: newTransition.longitude,
          from_satellite: transitions[transitions.length - 1]?.to_satellite || startingSatellite || '',
          to_satellite: newTransition.to_satellite,
        },
      ]);
      setNewTransition({});
    }
  };

  const handleRemoveTransition = (index: number) => {
    onTransitionsChange(transitions.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">Starting Satellite</label>
        <Select value={startingSatellite} onValueChange={onStartingSatelliteChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select starting satellite" />
          </SelectTrigger>
          <SelectContent>
            {availableSatellites.map((sat) => (
              <SelectItem key={sat} value={sat}>
                {sat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <h3 className="text-sm font-medium mb-2">Transitions</h3>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Latitude</TableHead>
              <TableHead>Longitude</TableHead>
              <TableHead>From Satellite</TableHead>
              <TableHead>To Satellite</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transitions.map((transition, index) => (
              <TableRow key={index}>
                <TableCell>{transition.latitude}</TableCell>
                <TableCell>{transition.longitude}</TableCell>
                <TableCell>{transition.from_satellite}</TableCell>
                <TableCell>{transition.to_satellite}</TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleRemoveTransition(index)}
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
                  step="0.000001"
                  placeholder="Latitude"
                  value={newTransition.latitude ?? ''}
                  onChange={(e) =>
                    setNewTransition({
                      ...newTransition,
                      latitude: parseFloat(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="0.000001"
                  placeholder="Longitude"
                  value={newTransition.longitude ?? ''}
                  onChange={(e) =>
                    setNewTransition({
                      ...newTransition,
                      longitude: parseFloat(e.target.value),
                    })
                  }
                />
              </TableCell>
              <TableCell>
                {transitions[transitions.length - 1]?.to_satellite || startingSatellite || 'N/A'}
              </TableCell>
              <TableCell>
                <Select
                  value={newTransition.to_satellite}
                  onValueChange={(value) =>
                    setNewTransition({ ...newTransition, to_satellite: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="To satellite" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableSatellites.map((sat) => (
                      <SelectItem key={sat} value={sat}>
                        {sat}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <Button onClick={handleAddTransition}>Add</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
