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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

export default function SatelliteManagerPage() {
  const { data: satellites, isLoading, refetch } = useSatellites();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    satellite_id: '',
    transport: 'X',
    longitude: -120,
    slot: '',
    color: '#FF6B6B',
  });
  const [error, setError] = useState<string | null>(null);

  // Reset form when dialog closes
  useEffect(() => {
    if (!isDialogOpen) {
      setFormData({
        satellite_id: '',
        transport: 'X',
        longitude: -120,
        slot: '',
        color: '#FF6B6B',
      });
      setError(null);
    }
  }, [isDialogOpen]);

  const handleCreate = async () => {
    if (!formData.satellite_id.trim()) {
      setError('Satellite ID is required');
      return;
    }
    if (!formData.transport) {
      setError('Transport type is required');
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
        transport: formData.transport,
        longitude: formData.longitude,
        slot: formData.slot.trim() || undefined,
        color: formData.color,
      });
      setIsDialogOpen(false);
      refetch();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create satellite'
      );
    } finally {
      setIsCreating(false);
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
            geostationary satellites at the equator (latitude = 0).
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
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
                  Transport Type
                </label>
                <Select
                  value={formData.transport}
                  onValueChange={(value) =>
                    setFormData({ ...formData, transport: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="X">X-Band</SelectItem>
                    <SelectItem value="Ka">Ka-Band</SelectItem>
                    <SelectItem value="Ku">Ku-Band</SelectItem>
                  </SelectContent>
                </Select>
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
              <div>
                <label className="block text-sm font-medium mb-1">
                  Orbital Slot (optional)
                </label>
                <Input
                  value={formData.slot}
                  onChange={(e) =>
                    setFormData({ ...formData, slot: e.target.value })
                  }
                  placeholder="e.g., X-Slot-1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Display Color
                </label>
                <div className="flex gap-2">
                  <Input
                    type="color"
                    value={formData.color}
                    onChange={(e) =>
                      setFormData({ ...formData, color: e.target.value })
                    }
                  />
                  <Input
                    type="text"
                    value={formData.color}
                    onChange={(e) =>
                      setFormData({ ...formData, color: e.target.value })
                    }
                  />
                </div>
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setIsDialogOpen(false)}
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
          <Card key={satellite.satellite_id}>
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
                {satellite.slot && (
                  <p>
                    <strong>Slot:</strong> {satellite.slot}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <div
                    className="w-6 h-6 rounded-full border border-gray-300"
                    style={{ backgroundColor: satellite.color }}
                  />
                  <span className="text-xs text-gray-500">Display color</span>
                </div>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleDelete(satellite.satellite_id)}
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
    </div>
  );
}
