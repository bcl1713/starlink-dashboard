import { useState } from 'react';
import { useSatellites } from '../../hooks/api/useSatellites';
import {
  satelliteService,
  type SatelliteResponse,
} from '../../services/satellites';

interface SatelliteFormData {
  satellite_id: string;
  longitude: string;
}

interface UseSatelliteDataReturn {
  satellites: SatelliteResponse[] | undefined;
  isLoading: boolean;
  refetch: () => void;
  formData: SatelliteFormData;
  setFormData: React.Dispatch<React.SetStateAction<SatelliteFormData>>;
  error: string | null;
  setError: React.Dispatch<React.SetStateAction<string | null>>;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: string | null;
  editingSatelliteId: string | null;
  setEditingSatelliteId: React.Dispatch<React.SetStateAction<string | null>>;
  handleCreate: () => Promise<void>;
  handleUpdate: () => Promise<void>;
  handleDelete: (satelliteId: string) => Promise<void>;
  handleEdit: (satellite: SatelliteResponse) => void;
}

/**
 * Custom hook for managing satellite data and operations
 */
export function useSatelliteData(): UseSatelliteDataReturn {
  const { data: satellites, isLoading, refetch } = useSatellites();
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [editingSatelliteId, setEditingSatelliteId] = useState<string | null>(
    null
  );
  const [formData, setFormData] = useState<SatelliteFormData>({
    satellite_id: '',
    longitude: '',
  });
  const [error, setError] = useState<string | null>(null);

  const validateForm = (): boolean => {
    if (!formData.satellite_id.trim()) {
      setError('Satellite ID is required');
      return false;
    }
    if (!formData.longitude.trim()) {
      setError('Longitude is required');
      return false;
    }
    const longitude = parseFloat(formData.longitude);
    if (isNaN(longitude) || longitude < -180 || longitude > 180) {
      setError('Longitude must be a valid number between -180 and 180');
      return false;
    }
    return true;
  };

  const handleCreate = async () => {
    if (!validateForm()) return;

    setIsCreating(true);
    setError(null);
    try {
      await satelliteService.create({
        satellite_id: formData.satellite_id.trim(),
        transport: 'X', // Default to X-Band
        longitude: parseFloat(formData.longitude),
      });
      refetch();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create satellite'
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleEdit = (satellite: SatelliteResponse) => {
    setEditingSatelliteId(satellite.satellite_id);
    setFormData({
      satellite_id: satellite.satellite_id,
      longitude:
        satellite.longitude !== null ? satellite.longitude.toString() : '',
    });
  };

  const handleUpdate = async () => {
    if (!validateForm()) return;
    if (!editingSatelliteId) {
      setError('Satellite ID not found');
      return;
    }

    setIsUpdating(true);
    setError(null);
    try {
      await satelliteService.update(editingSatelliteId, {
        satellite_id: formData.satellite_id.trim(),
        longitude: parseFloat(formData.longitude),
      });
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

  return {
    satellites,
    isLoading,
    refetch,
    formData,
    setFormData,
    error,
    setError,
    isCreating,
    isUpdating,
    isDeleting,
    editingSatelliteId,
    setEditingSatelliteId,
    handleCreate,
    handleUpdate,
    handleDelete,
    handleEdit,
  };
}
