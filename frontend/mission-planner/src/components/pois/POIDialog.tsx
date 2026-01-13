import { usePOI, useCreatePOI, useUpdatePOI } from '../../hooks/api/usePOIs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { POIForm } from './POIForm';
import type { POICreate, POIUpdate } from '../../services/pois';

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
  selectedCoords,
  onSuccess,
}: POIDialogProps) {
  const isNew = poiId === 'new';
  const { data: poi, isLoading: isLoadingPOI } = usePOI(
    !isNew && poiId ? poiId : ''
  );

  const createPOI = useCreatePOI();
  const updatePOI = useUpdatePOI();

  const isLoading = isLoadingPOI || createPOI.isPending || updatePOI.isPending;

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Create POI' : 'Edit POI'}</DialogTitle>
        </DialogHeader>

        <POIForm
          poi={poi}
          onSubmit={handleSubmit}
          onCancel={() => onOpenChange(false)}
          isLoading={isLoading}
          selectedCoords={selectedCoords}
        />
      </DialogContent>
    </Dialog>
  );
}
