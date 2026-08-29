import { useState } from 'react';
import { usePOI, useCreatePOI, useUpdatePOI } from '../../hooks/api/usePOIs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { POIForm } from './POIForm';
import { POIMap } from './POIMap';
import type { POICreate, POIUpdate, POI } from '../../services/pois';

interface POIDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  poiId?: string | 'new';
  selectedCoords?: { lat: number; lng: number };
  onSuccess?: () => void;
}

export function POIDialog({
  open,
  onOpenChange,
  poiId,
  selectedCoords: initialCoords,
  onSuccess,
}: POIDialogProps) {
  const isNew = poiId === 'new';
  const { data: poi, isLoading: isLoadingPOI } = usePOI(
    !isNew && poiId ? poiId : ''
  );

  // Track coordinates for the map marker
  const [currentCoords, setCurrentCoords] = useState<{
    lat: number;
    lng: number;
  } | null>(initialCoords || null);

  const [prevPoiId, setPrevPoiId] = useState<string | undefined>(undefined);
  const [prevInitialCoords, setPrevInitialCoords] = useState(initialCoords);

  // Adjust state while rendering if props/data change
  if (poi && poi.id !== prevPoiId) {
    setPrevPoiId(poi.id);
    setCurrentCoords({ lat: poi.latitude, lng: poi.longitude });
  }

  if (
    initialCoords &&
    (initialCoords !== prevInitialCoords ||
      (prevInitialCoords &&
        (initialCoords.lat !== prevInitialCoords.lat ||
          initialCoords.lng !== prevInitialCoords.lng)))
  ) {
    setPrevInitialCoords(initialCoords);
    setCurrentCoords(initialCoords);
  }

  // Reset when dialog closes (during render)
  if (!open && (currentCoords !== null || prevPoiId !== undefined)) {
    setCurrentCoords(null);
    setPrevPoiId(undefined);
  }

  const createPOI = useCreatePOI();
  const updatePOI = useUpdatePOI();

  const isLoading = isLoadingPOI || createPOI.isPending || updatePOI.isPending;

  // Determine error message from mutation states
  const error = createPOI.isError
    ? createPOI.error instanceof Error
      ? createPOI.error.message
      : 'Failed to create POI. Please check your input and try again.'
    : updatePOI.isError
      ? updatePOI.error instanceof Error
        ? updatePOI.error.message
        : 'Failed to update POI. Please check your input and try again.'
      : undefined;

  const handleSubmit = (data: POICreate | POIUpdate) => {
    if (isNew) {
      createPOI.mutate(data as POICreate, {
        onSuccess: () => {
          onOpenChange(false);
          onSuccess?.();
        },
      });
    } else if (poiId && poiId !== 'new') {
      updatePOI.mutate(
        { id: poiId, updates: data as POIUpdate },
        {
          onSuccess: () => {
            onOpenChange(false);
            onSuccess?.();
          },
        }
      );
    }
  };

  // Reset error states when dialog closes or opens
  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      createPOI.reset();
      updatePOI.reset();
    }
    onOpenChange(newOpen);
  };

  const handleMapClick = (lat: number, lng: number) => {
    setCurrentCoords({ lat, lng });
  };

  // Create a temporary POI for the map marker
  const mapPOIs: POI[] = currentCoords
    ? [
        {
          id: 'temp-marker',
          name: 'New Position',
          latitude: currentCoords.lat,
          longitude: currentCoords.lng,
          icon: '📍',
          category: null,
          active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]
    : [];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="grid max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-[800px]">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Create POI' : 'Edit POI'}</DialogTitle>
        </DialogHeader>

        <div className="min-h-0 overflow-y-auto pr-1 [scrollbar-gutter:stable]">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Form */}
            <div>
              <POIForm
                poi={poi}
                onSubmit={handleSubmit}
                isLoading={isLoading}
                error={error}
                selectedCoords={currentCoords || undefined}
              />
            </div>

            {/* Map for positioning */}
            <div className="space-y-2">
              <p className="text-sm text-gray-600">
                Click on the map to set the POI position
              </p>
              <div className="h-80 overflow-hidden rounded-lg border">
                <POIMap
                  pois={mapPOIs}
                  onMapClick={handleMapClick}
                  center={
                    currentCoords
                      ? [currentCoords.lat, currentCoords.lng]
                      : poi
                        ? [poi.latitude, poi.longitude]
                        : [0, 0]
                  }
                  zoom={currentCoords || poi ? 10 : 3}
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t pt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button form="poi-form" type="submit" disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save POI'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
