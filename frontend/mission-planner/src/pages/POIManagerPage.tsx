import { useState } from 'react';
import { usePOIs } from '../hooks/api/usePOIs';
import { POIList } from '../components/pois/POIList';
import { POIFilterBar } from '../components/pois/POIFilterBar';
import { POIMap } from '../components/pois/POIMap';
import { POIDialog } from '../components/pois/POIDialog';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';

export function POIManagerPage() {
  const [selectedPOIId, setSelectedPOIId] = useState<string | null>(null);
  const [editingPOIId, setEditingPOIId] = useState<string | null>(null);
  const [selectedCoords, setSelectedCoords] = useState<{
    lat: number;
    lng: number;
  } | null>(null);
  const [activeOnly, setActiveOnly] = useState(false);
  const { data: pois, refetch } = usePOIs(activeOnly);

  const handleMapClick = (lat: number, lng: number) => {
    setSelectedCoords({ lat, lng });
    setEditingPOIId('new');
  };

  const selectedPOI = pois?.find((p) => p.id === selectedPOIId);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">POI Manager</h1>
        <Button onClick={() => setEditingPOIId('new')}>Create POI</Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left panel - List and filters */}
        <div className="lg:col-span-2 space-y-4">
          <POIFilterBar
            onFilterChange={(filters) => {
              // TODO: Implement filtering logic
              console.log('Filters:', filters);
            }}
            onActiveOnlyChange={setActiveOnly}
          />

          <POIList
            onSelectPOI={setSelectedPOIId}
            onEditPOI={setEditingPOIId}
            onDeletePOI={() => setSelectedPOIId(null)}
          />
        </div>

        {/* Right panel - Map and Detail/Edit */}
        <div className="space-y-4">
          {/* Map */}
          <Card className="h-96">
            <POIMap
              pois={pois || []}
              onMapClick={handleMapClick}
              onPOIClick={(poi) => setSelectedPOIId(poi.id)}
            />
          </Card>

          {/* POI Details */}
          {selectedPOIId && !editingPOIId && selectedPOI && (
            <Card>
              <div className="p-6">
                <h2 className="text-lg font-semibold mb-4">POI Details</h2>
                <div className="space-y-2 text-sm">
                  <p>
                    <span className="text-gray-600">Name:</span>{' '}
                    {selectedPOI.name}
                  </p>
                  <p>
                    <span className="text-gray-600">Category:</span>{' '}
                    {selectedPOI.category || '—'}
                  </p>
                  <p>
                    <span className="text-gray-600">Icon:</span>{' '}
                    {selectedPOI.icon}
                  </p>
                  {selectedPOI.description && (
                    <p>
                      <span className="text-gray-600">Description:</span>{' '}
                      {selectedPOI.description}
                    </p>
                  )}
                  <p className="text-xs text-gray-500 pt-2">
                    {selectedPOI.latitude.toFixed(4)},{' '}
                    {selectedPOI.longitude.toFixed(4)}
                  </p>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* POI Dialog for Create/Edit */}
      <POIDialog
        open={!!editingPOIId}
        onOpenChange={(open) => {
          if (!open) {
            setEditingPOIId(null);
            setSelectedCoords(null);
          }
        }}
        poiId={editingPOIId || undefined}
        selectedCoords={selectedCoords || undefined}
        onSuccess={() => {
          refetch();
          setEditingPOIId(null);
          setSelectedCoords(null);
        }}
      />
    </div>
  );
}
