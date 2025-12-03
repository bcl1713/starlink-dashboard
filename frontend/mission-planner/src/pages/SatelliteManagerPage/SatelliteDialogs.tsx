import { useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '../../components/ui/dialog';

interface SatelliteFormData {
  satellite_id: string;
  longitude: string;
}

interface SatelliteDialogsProps {
  // Add Dialog
  isAddDialogOpen: boolean;
  setIsAddDialogOpen: (open: boolean) => void;
  isCreating: boolean;
  onCreateSuccess: () => void;

  // Edit Dialog
  isEditDialogOpen: boolean;
  setIsEditDialogOpen: (open: boolean) => void;
  isUpdating: boolean;
  onUpdateSuccess: () => void;

  // Form state
  formData: SatelliteFormData;
  setFormData: React.Dispatch<React.SetStateAction<SatelliteFormData>>;
  error: string | null;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  onCreate: () => Promise<void>;
  onUpdate: () => Promise<void>;
}

/**
 * Component containing both add and edit dialogs for satellites
 */
export function SatelliteDialogs({
  isAddDialogOpen,
  setIsAddDialogOpen,
  isCreating,
  onCreateSuccess,
  isEditDialogOpen,
  setIsEditDialogOpen,
  isUpdating,
  onUpdateSuccess,
  formData,
  setFormData,
  error,
  setError,
  onCreate,
  onUpdate,
}: SatelliteDialogsProps) {
  // Reset form when add dialog closes
  useEffect(() => {
    if (!isAddDialogOpen) {
      setFormData({
        satellite_id: '',
        longitude: '',
      });
      setError(null);
    }
  }, [isAddDialogOpen, setFormData, setError]);

  // Reset edit form when dialog closes
  useEffect(() => {
    if (!isEditDialogOpen) {
      setFormData({
        satellite_id: '',
        longitude: '',
      });
      setError(null);
    }
  }, [isEditDialogOpen, setFormData, setError]);

  const handleCreate = async () => {
    await onCreate();
    if (!error) {
      setIsAddDialogOpen(false);
      onCreateSuccess();
    }
  };

  const handleUpdate = async () => {
    await onUpdate();
    if (!error) {
      setIsEditDialogOpen(false);
      onUpdateSuccess();
    }
  };

  return (
    <>
      {/* Add Satellite Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogTrigger asChild>
          <Button>Add Satellite</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Satellite</DialogTitle>
            <DialogDescription>
              Create a new satellite entry. Satellites are geostationary at the
              equator.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Satellite ID (e.g., X-1)
              </label>
              <Input
                value={formData.satellite_id}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    satellite_id: e.target.value,
                  })
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreate();
                  }
                }}
                placeholder="X-1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Longitude (-180 to 180)
              </label>
              <Input
                type="text"
                value={formData.longitude}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    longitude: e.target.value,
                  })
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleCreate();
                  }
                }}
                placeholder="-120"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={isCreating}>
              {isCreating ? 'Creating...' : 'Create Satellite'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Satellite Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Satellite</DialogTitle>
            <DialogDescription>
              Update the satellite ID and longitude.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Satellite ID (e.g., X-1)
              </label>
              <Input
                value={formData.satellite_id}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    satellite_id: e.target.value,
                  })
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleUpdate();
                  }
                }}
                placeholder="X-1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Longitude (-180 to 180)
              </label>
              <Input
                type="text"
                value={formData.longitude}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    longitude: e.target.value,
                  })
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleUpdate();
                  }
                }}
                placeholder="-120"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsEditDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={isUpdating}>
              {isUpdating ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
