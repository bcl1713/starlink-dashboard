import { useState } from 'react';
import { useSatelliteData } from './SatelliteManagerPage/useSatelliteData';
import { SatelliteList } from './SatelliteManagerPage/SatelliteList';
import { SatelliteDialogs } from './SatelliteManagerPage/SatelliteDialogs';

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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onEdit = (satellite: any) => {
    handleEdit(satellite);
    setIsEditDialogOpen(true);
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
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
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
