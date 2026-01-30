import { useState, useMemo, useCallback } from 'react';
import { usePOIs } from '../hooks/api/usePOIs';
import { POIList } from '../components/pois/POIList';
import { POIFilterBar } from '../components/pois/POIFilterBar';
import type { FilterOptions } from '../components/pois/POIFilterBar';
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
  const [showRoutePOIs, setShowRoutePOIs] = useState(false);
  const [filters, setFilters] = useState<FilterOptions>({});

  // Fetch all POIs (no server-side filtering for active_only)
  const { data: allPOIs, isLoading, error, refetch } = usePOIs(false);

  // Filter POIs client-side
  const filteredPOIs = useMemo(() => {
    if (!allPOIs) return [];

    return allPOIs.filter((poi) => {
      // Filter out route POIs unless showRoutePOIs is true
      if (!showRoutePOIs && poi.route_id) {
        return false;
      }

      // Apply search filter
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        const matchesSearch =
          poi.name.toLowerCase().includes(searchLower) ||
          (poi.category && poi.category.toLowerCase().includes(searchLower)) ||
          (poi.description &&
            poi.description.toLowerCase().includes(searchLower));
        if (!matchesSearch) return false;
      }

      // Apply category filter
      if (filters.category && poi.category !== filters.category) {
        return false;
      }

      return true;
    });
  }, [allPOIs, showRoutePOIs, filters]);

  const handleMapClick = (lat: number, lng: number) => {
    setSelectedCoords({ lat, lng });
    setEditingPOIId('new');
  };

  const handleSelectPOI = (id: string) => {
    setSelectedPOIId(id);
    // Clear editing state when viewing a different POI
    if (editingPOIId && editingPOIId !== id) {
      setEditingPOIId(null);
    }
  };

  const handleEditPOI = (id: string) => {
    setEditingPOIId(id);
    setSelectedPOIId(id);
  };

  const handleFilterChange = useCallback((newFilters: FilterOptions) => {
    setFilters(newFilters);
  }, []);

  const selectedPOI = allPOIs?.find((p) => p.id === selectedPOIId);
  const focusPOI = selectedPOI || null;

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
            onFilterChange={handleFilterChange}
            showRoutePOIs={showRoutePOIs}
            onShowRoutePOIsChange={setShowRoutePOIs}
          />

          <POIList
            pois={filteredPOIs}
            isLoading={isLoading}
            error={error as Error | null}
            onSelectPOI={handleSelectPOI}
            onEditPOI={handleEditPOI}
            onDeletePOI={() => setSelectedPOIId(null)}
          />
        </div>

        {/* Right panel - Map and Detail/Edit */}
        <div className="space-y-4">
          {/* Map */}
          <Card className="h-96">
            <POIMap
              pois={filteredPOIs}
              onMapClick={handleMapClick}
              onPOIClick={(poi) => handleSelectPOI(poi.id)}
              focusPOI={focusPOI}
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
