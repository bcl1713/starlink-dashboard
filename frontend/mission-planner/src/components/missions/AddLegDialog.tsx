import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import type { MissionLeg } from '../../types/mission';
import { routesApi } from '../../services/routes';
import type { Route } from '../../services/routes';

interface AddLegDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingLegCount: number;
  onAddLeg: (leg: Partial<MissionLeg>) => Promise<void>;
}

export function AddLegDialog({
  open,
  onOpenChange,
  existingLegCount,
  onAddLeg,
}: AddLegDialogProps) {
  const [legName, setLegName] = useState('');
  const [description, setDescription] = useState('');
  const [routeOption, setRouteOption] = useState<'existing' | 'upload'>('existing');
  const [selectedRouteId, setSelectedRouteId] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [isLoadingRoutes, setIsLoadingRoutes] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState('');

  // Load routes when dialog opens
  useEffect(() => {
    if (open) {
      setIsLoadingRoutes(true);
      routesApi
        .list()
        .then(setRoutes)
        .catch((err) => console.error('Failed to load routes:', err))
        .finally(() => setIsLoadingRoutes(false));

      // Set default leg name
      setLegName(`Leg ${existingLegCount + 1}`);
    }
  }, [open, existingLegCount]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setUploadError('');

    try {
      let routeId = selectedRouteId;

      // If uploading new route, upload it first
      if (routeOption === 'upload' && uploadedFile) {
        const newRoute = await routesApi.upload(uploadedFile);
        routeId = newRoute.id;
      }

      // Generate leg ID based on name (slugify)
      const legId = legName
        .toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-]/g, '');

      await onAddLeg({
        id: legId,
        name: legName,
        route_id: routeId || undefined,
        description: description || undefined,
        transports: {
          initial_x_satellite_id: 'X-1',
          initial_ka_satellite_ids: ['AOR', 'POR', 'IOR'],
          x_transitions: [],
          ka_outages: [],
          aar_windows: [],
          ku_overrides: [],
        },
      });

      // Reset form
      setLegName('');
      setDescription('');
      setSelectedRouteId('');
      setUploadedFile(null);
      setRouteOption('existing');
      onOpenChange(false);
    } catch (error: any) {
      console.error('Failed to add leg:', error);
      setUploadError(error.message || 'Failed to add leg');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid = legName.trim() &&
    (routeOption === 'existing' ? selectedRouteId : uploadedFile);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add New Leg to Mission</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <Label htmlFor="leg-name">Leg Name *</Label>
              <Input
                id="leg-name"
                value={legName}
                onChange={(e) => setLegName(e.target.value)}
                placeholder="Leg 1"
                required
                disabled={isSubmitting}
              />
              <p className="text-xs text-gray-500 mt-1">
                Default: Leg {existingLegCount + 1}
              </p>
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                disabled={isSubmitting}
              />
            </div>

            <div>
              <Label>Route</Label>
              <div className="space-y-2 mt-2">
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant={routeOption === 'existing' ? 'default' : 'outline'}
                    onClick={() => setRouteOption('existing')}
                    className="flex-1"
                    disabled={isSubmitting}
                  >
                    Select Existing
                  </Button>
                  <Button
                    type="button"
                    variant={routeOption === 'upload' ? 'default' : 'outline'}
                    onClick={() => setRouteOption('upload')}
                    className="flex-1"
                    disabled={isSubmitting}
                  >
                    Upload KML
                  </Button>
                </div>

                {routeOption === 'existing' && (
                  <Select
                    value={selectedRouteId}
                    onValueChange={setSelectedRouteId}
                    disabled={isLoadingRoutes || isSubmitting}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          isLoadingRoutes
                            ? 'Loading routes...'
                            : 'Select a route'
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {routes.length === 0 && !isLoadingRoutes && (
                        <SelectItem value="_none" disabled>
                          No routes available
                        </SelectItem>
                      )}
                      {routes.map((route) => (
                        <SelectItem key={route.id} value={route.id}>
                          {route.name || route.id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                {routeOption === 'upload' && (
                  <div>
                    <Input
                      type="file"
                      accept=".kml"
                      onChange={(e) => setUploadedFile(e.target.files?.[0] || null)}
                      disabled={isSubmitting}
                    />
                    {uploadedFile && (
                      <p className="text-xs text-gray-600 mt-1">
                        Selected: {uploadedFile.name}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {uploadError && (
              <p className="text-sm text-red-600">{uploadError}</p>
            )}
          </div>

          <DialogFooter className="mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !isFormValid}>
              {isSubmitting ? 'Adding...' : 'Add Leg'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
