import { useState, useEffect } from 'react';
import { useSatellites } from '../hooks/api/useSatellites';
import { satelliteService } from '../services/satellites';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '../components/ui/dialog';

export default function SatelliteManagerPage() {
  const { data: satellites, isLoading, refetch } = useSatellites();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [editingSatelliteId, setEditingSatelliteId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    satellite_id: '',
    longitude: -120,
  });
  const [error, setError] = useState<string | null>(null);

  // Reset form when dialog closes
  useEffect(() => {
    if (!isAddDialogOpen) {
      setFormData({
        satellite_id: '',
        longitude: -120,
      });
      setError(null);
    }
  }, [isAddDialogOpen]);

  // Reset edit form when dialog closes
  useEffect(() => {
    if (!isEditDialogOpen) {
      setEditingSatelliteId(null);
      setFormData({
        satellite_id: '',
        longitude: -120,
      });
      setError(null);
    }
  }, [isEditDialogOpen]);

  const handleCreate = async () => {
    if (!formData.satellite_id.trim()) {
      setError('Satellite ID is required');
      return;
    }
    if (formData.longitude < -180 || formData.longitude > 180) {
      setError('Longitude must be between -180 and 180');
      return;
    }

    setIsCreating(true);
    setError(null);
    try {
      await satelliteService.create({
        satellite_id: formData.satellite_id.trim(),
        transport: 'X', // Default to X-Band
        longitude: formData.longitude,
      });
      setIsAddDialogOpen(false);
      refetch();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create satellite'
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleEdit = (satellite: any) => {
    setEditingSatelliteId(satellite.satellite_id);
    setFormData({
      satellite_id: satellite.satellite_id,
      longitude: satellite.longitude || -120,
    });
    setIsEditDialogOpen(true);
  };

  const handleUpdate = async () => {
    if (!formData.satellite_id.trim()) {
      setError('Satellite ID is required');
      return;
    }
    if (formData.longitude < -180 || formData.longitude > 180) {
      setError('Longitude must be between -180 and 180');
      return;
    }

    if (!editingSatelliteId) {
      setError('Satellite ID not found');
      return;
    }

    setIsUpdating(true);
    setError(null);
    try {
      await satelliteService.update(editingSatelliteId, {
        satellite_id: formData.satellite_id.trim(),
        longitude: formData.longitude,
      });
      setIsEditDialogOpen(false);
      refetch();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to update satellite'
      );
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (satelliteId: string) => {
    if (!confirm(`Delete satellite ${satelliteId}?`)) {
      return;
    }

    setIsDeleting(satelliteId);
    try {
      await satelliteService.delete(satelliteId);
      refetch();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to delete satellite'
      );
    } finally {
      setIsDeleting(null);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold mb-2">Satellite Manager</h1>
          <p className="text-gray-600">
            Manage X-Band, Ka-Band, and Ku-Band satellites. These are
            geostationary satellites at the equator (latitude = 0). Click on a
            satellite to edit.
          </p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>Add Satellite</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Satellite</DialogTitle>
              <DialogDescription>
                Create a new satellite entry. Satellites are geostationary at
                the equator.
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
                  placeholder="X-1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Longitude (-180 to 180)
                </label>
                <Input
                  type="number"
                  step="0.001"
                  min="-180"
                  max="180"
                  value={formData.longitude}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      longitude: parseFloat(e.target.value),
                    })
                  }
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsAddDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={isCreating}>
                {isCreating ? 'Creating...' : 'Create Satellite'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}

      {isLoading && <p className="mt-4">Loading satellites...</p>}

      {!isLoading && satellites && satellites.length === 0 && (
        <p className="mt-4 text-gray-500">No satellites in catalog.</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {satellites?.map((satellite) => (
          <Card
            key={satellite.satellite_id}
            className="cursor-pointer hover:shadow-lg transition-shadow"
            onClick={() => handleEdit(satellite)}
          >
            <CardHeader>
              <CardTitle>{satellite.satellite_id}</CardTitle>
              <CardDescription>
                {satellite.longitude !== null
                  ? `${satellite.longitude > 0 ? satellite.longitude + '°E' : Math.abs(satellite.longitude) + '°W'}`
                  : 'Position TBD'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm mb-4">
                <p>
                  <strong>Transport:</strong> {satellite.transport}-Band
                </p>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(satellite.satellite_id);
                }}
                disabled={isDeleting === satellite.satellite_id}
              >
                {isDeleting === satellite.satellite_id
                  ? 'Deleting...'
                  : 'Delete'}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

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
                placeholder="X-1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">
                Longitude (-180 to 180)
              </label>
              <Input
                type="number"
                step="0.001"
                min="-180"
                max="180"
                value={formData.longitude}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    longitude: parseFloat(e.target.value),
                  })
                }
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
    </div>
  );
}
