import { useState } from 'react';
import type { POI, POICreate, POIUpdate } from '../../services/pois';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Label } from '../ui/label';
import { IconPicker } from '../ui/IconPicker';

const CATEGORY_OPTIONS = [
  { value: 'airport', label: 'Airport' },
  { value: 'city', label: 'City' },
  { value: 'landmark', label: 'Landmark' },
  { value: 'waypoint', label: 'Waypoint' },
  { value: 'departure', label: 'Departure' },
  { value: 'arrival', label: 'Arrival' },
  { value: 'alternate', label: 'Alternate' },
  { value: 'satellite', label: 'Satellite' },
  { value: 'other', label: 'Other' },
];

interface POIFormProps {
  poi?: POI;
  onSubmit: (data: POICreate | POIUpdate) => void;
  onCancel: () => void;
  isLoading?: boolean;
  error?: string;
  selectedCoords?: { lat: number; lng: number };
}

export function POIForm({
  poi,
  onSubmit,
  onCancel,
  isLoading,
  error,
  selectedCoords,
}: POIFormProps) {
  const [formData, setFormData] = useState({
    name: poi?.name || '',
    latitude: selectedCoords?.lat || poi?.latitude || 0,
    longitude: selectedCoords?.lng || poi?.longitude || 0,
    icon: poi?.icon || '',
    category: poi?.category || '',
    description: poi?.description || '',
    route_id: poi?.route_id || '',
    mission_id: poi?.mission_id || '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }
    if (typeof formData.latitude !== 'number' || isNaN(formData.latitude)) {
      newErrors.latitude = 'Valid latitude is required';
    }
    if (typeof formData.longitude !== 'number' || isNaN(formData.longitude)) {
      newErrors.longitude = 'Valid longitude is required';
    }
    if (!formData.category) {
      newErrors.category = 'Category is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    onSubmit({
      ...formData,
      category: formData.category || null,
      icon: formData.icon || '📍',
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div>
        <Label htmlFor="name">Name *</Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="POI name"
          disabled={isLoading}
        />
        {errors.name && (
          <p className="text-red-500 text-sm mt-1">{errors.name}</p>
        )}
      </div>

      <div>
        <Label htmlFor="category">Category *</Label>
        <select
          id="category"
          value={formData.category}
          onChange={(e) =>
            setFormData({ ...formData, category: e.target.value })
          }
          disabled={isLoading}
          className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select a category</option>
          {CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {errors.category && (
          <p className="text-red-500 text-sm mt-1">{errors.category}</p>
        )}
      </div>

      <div>
        <Label htmlFor="icon">Icon (Optional)</Label>
        <IconPicker
          value={formData.icon}
          onChange={(icon) => setFormData({ ...formData, icon })}
          disabled={isLoading}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="latitude">Latitude *</Label>
          <Input
            id="latitude"
            type="number"
            step="0.0001"
            value={formData.latitude}
            onChange={(e) =>
              setFormData({
                ...formData,
                latitude: parseFloat(e.target.value) || 0,
              })
            }
            placeholder="-90 to 90"
            disabled={isLoading}
          />
          {errors.latitude && (
            <p className="text-red-500 text-sm mt-1">{errors.latitude}</p>
          )}
        </div>

        <div>
          <Label htmlFor="longitude">Longitude *</Label>
          <Input
            id="longitude"
            type="number"
            step="0.0001"
            value={formData.longitude}
            onChange={(e) =>
              setFormData({
                ...formData,
                longitude: parseFloat(e.target.value) || 0,
              })
            }
            placeholder="-180 to 180"
            disabled={isLoading}
          />
          {errors.longitude && (
            <p className="text-red-500 text-sm mt-1">{errors.longitude}</p>
          )}
        </div>
      </div>

      <div>
        <Label htmlFor="description">Description</Label>
        <Input
          id="description"
          value={formData.description}
          onChange={(e) =>
            setFormData({ ...formData, description: e.target.value })
          }
          placeholder="Optional description"
          disabled={isLoading}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="route_id">Route ID</Label>
          <Input
            id="route_id"
            value={formData.route_id}
            onChange={(e) =>
              setFormData({ ...formData, route_id: e.target.value })
            }
            placeholder="Optional"
            disabled={isLoading}
          />
        </div>

        <div>
          <Label htmlFor="mission_id">Mission ID</Label>
          <Input
            id="mission_id"
            value={formData.mission_id}
            onChange={(e) =>
              setFormData({ ...formData, mission_id: e.target.value })
            }
            placeholder="Optional"
            disabled={isLoading}
          />
        </div>
      </div>

      <div className="flex gap-2 justify-end pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Saving...' : 'Save POI'}
        </Button>
      </div>
    </form>
  );
}
