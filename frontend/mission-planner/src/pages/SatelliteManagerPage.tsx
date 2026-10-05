import { useState } from 'react';
import { useSatelliteData } from './SatelliteManagerPage/useSatelliteData';
import { SatelliteList } from './SatelliteManagerPage/SatelliteList';
import { SatelliteDialogs } from './SatelliteManagerPage/SatelliteDialogs';
import type { SatelliteResponse } from '../services/satellites';

export default function SatelliteManagerPage() {
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const {
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
    handleCreate,
    handleUpdate,
    handleDelete,
    handleEdit,
  } = useSatelliteData();

  const onEdit = (satellite: SatelliteResponse) => {
    handleEdit(satellite);
    setIsEditDialogOpen(true);
  };

  return (
    <div className="app-page">
      <div className="page-header">
        <div>
          <h1 className="page-title mb-2">Satellite Manager</h1>
          <p className="page-description">
            Manage X-Band, Ka-Band, and Ku-Band satellites. These are
            geostationary satellites at the equator (latitude = 0). Click on a
            satellite to edit.
          </p>
        </div>
        <SatelliteDialogs
          isAddDialogOpen={isAddDialogOpen}
          setIsAddDialogOpen={setIsAddDialogOpen}
          isCreating={isCreating}
          onCreateSuccess={refetch}
          isEditDialogOpen={isEditDialogOpen}
          setIsEditDialogOpen={setIsEditDialogOpen}
          isUpdating={isUpdating}
          onUpdateSuccess={refetch}
          formData={formData}
          setFormData={setFormData}
          error={error}
          setError={setError}
          onCreate={handleCreate}
          onUpdate={handleUpdate}
        />
      </div>

      {error && (
        <div className="mb-4 p-3 status-critical border border-destructive/30 rounded">
          {error}
        </div>
      )}

      <SatelliteList
        satellites={satellites}
        isLoading={isLoading}
        isDeleting={isDeleting}
        onEdit={onEdit}
        onDelete={handleDelete}
      />
    </div>
  );
}
