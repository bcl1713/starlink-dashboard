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

const validateSatelliteId = (id: string): string | null => {
  if (!id || id.trim() === '') {
    return 'Satellite ID is required';
  }
  if (!/^[A-Z0-9-_]+$/i.test(id)) {
    return 'Satellite ID must contain only letters, numbers, hyphens, and underscores';
  }
  return null; // Valid
};

const validateLatitude = (lat: number | undefined): string | null => {
  if (lat === undefined || lat === null) {
    return 'Latitude is required';
  }
  if (lat < -90 || lat > 90) {
    return 'Latitude must be between -90 and 90 degrees';
  }
  return null; // Valid
};

const validateLongitude = (lon: number | undefined): string | null => {
  if (lon === undefined || lon === null) {
    return 'Longitude is required';
  }
  if (lon < -180 || lon > 180) {
    return 'Longitude must be between -180 and 180 degrees';
  }
  return null; // Valid
};

export function XBandConfig({
  startingSatellite,
  transitions,
  onStartingSatelliteChange,
  onTransitionsChange,
  availableSatellites,
}: XBandConfigProps) {
  const [newTransition, setNewTransition] = useState<Partial<XBandTransition>>({});
  const [satelliteIdError, setSatelliteIdError] = useState<string | null>(null);
  const [latitudeError, setLatitudeError] = useState<string | null>(null);
  const [longitudeError, setLongitudeError] = useState<string | null>(null);

  const handleAddTransition = () => {
    // Validate inputs
    const latError = validateLatitude(newTransition.latitude);
    const lonError = validateLongitude(newTransition.longitude);
    const satError = newTransition.target_satellite_id
      ? validateSatelliteId(newTransition.target_satellite_id)
      : 'Satellite ID is required';

    setLatitudeError(latError);
    setLongitudeError(lonError);
    setSatelliteIdError(satError);

    // Only proceed if all validations pass
    if (!latError && !lonError && !satError) {
      onTransitionsChange([
        ...transitions,
        {
          id: crypto.randomUUID(),
          latitude: newTransition.latitude!,
          longitude: newTransition.longitude!,
          target_satellite_id: newTransition.target_satellite_id!,
        },
      ]);
      setNewTransition({});
      // Clear errors after successful submission
      setSatelliteIdError(null);
      setLatitudeError(null);
      setLongitudeError(null);
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
              <TableHead>Target Satellite</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transitions.map((transition, index) => (
              <TableRow key={transition.id}>
                <TableCell>{transition.latitude}</TableCell>
                <TableCell>{transition.longitude}</TableCell>
                <TableCell>{transition.target_satellite_id}</TableCell>
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
                <div>
                  <Input
                    type="number"
                    step="0.000001"
                    placeholder="Latitude"
                    value={newTransition.latitude ?? ''}
                    onChange={(e) => {
                      const lat = parseFloat(e.target.value);
                      setNewTransition({
                        ...newTransition,
                        latitude: lat,
                      });
                      setLatitudeError(validateLatitude(lat));
                    }}
                    className={latitudeError ? 'border-red-500' : ''}
                  />
                  {latitudeError && (
                    <p className="text-sm text-red-500 mt-1">{latitudeError}</p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <div>
                  <Input
                    type="number"
                    step="0.000001"
                    placeholder="Longitude"
                    value={newTransition.longitude ?? ''}
                    onChange={(e) => {
                      const lon = parseFloat(e.target.value);
                      setNewTransition({
                        ...newTransition,
                        longitude: lon,
                      });
                      setLongitudeError(validateLongitude(lon));
                    }}
                    className={longitudeError ? 'border-red-500' : ''}
                  />
                  {longitudeError && (
                    <p className="text-sm text-red-500 mt-1">{longitudeError}</p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <div>
                  <Select
                    value={newTransition.target_satellite_id || ''}
                    onValueChange={(value) => {
                      setNewTransition({ ...newTransition, target_satellite_id: value });
                      setSatelliteIdError(validateSatelliteId(value));
                    }}
                  >
                    <SelectTrigger className={satelliteIdError ? 'border-red-500' : ''}>
                      <SelectValue placeholder="Target satellite" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableSatellites.map((sat) => (
                        <SelectItem key={sat} value={sat}>
                          {sat}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {satelliteIdError && (
                    <p className="text-sm text-red-500 mt-1">{satelliteIdError}</p>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Button
                  onClick={handleAddTransition}
                  disabled={!!latitudeError || !!longitudeError || !!satelliteIdError}
                >
                  Add
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
