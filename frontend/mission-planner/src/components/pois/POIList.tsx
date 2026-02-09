import { useState, useMemo } from 'react';
import { useDeletePOI } from '../../hooks/api/usePOIs';
import type { POI, POIWithETA } from '../../services/pois';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Button } from '../ui/button';
import { Trash2, Edit, Eye, ArrowUp, ArrowDown } from 'lucide-react';

type SortField =
  | 'name'
  | 'category'
  | 'coordinates'
  | 'status'
  | 'created'
  | 'eta';
type SortDirection = 'asc' | 'desc';

interface POIListProps {
  pois?: POI[];
  etaData?: POIWithETA[];
  isLoading?: boolean;
  error?: Error | null;
  onSelectPOI: (id: string) => void;
  onEditPOI: (id: string) => void;
  onDeletePOI: (id: string) => void;
}

const SortIcon = ({
  field,
  currentSortField,
  sortDirection,
}: {
  field: SortField;
  currentSortField: SortField;
  sortDirection: SortDirection;
}) => {
  if (currentSortField !== field) return null;
  return sortDirection === 'asc' ? (
    <ArrowUp className="w-3 h-3 inline ml-1" />
  ) : (
    <ArrowDown className="w-3 h-3 inline ml-1" />
  );
};

export function POIList({
  pois,
  etaData,
  isLoading,
  error,
  onSelectPOI,
  onEditPOI,
  onDeletePOI,
}: POIListProps) {
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const deletePOI = useDeletePOI();

  // Build a lookup map from ETA data
  const etaMap = useMemo(() => {
    if (!etaData) return new Map<string, POIWithETA>();
    return new Map(etaData.map((p) => [p.id, p]));
  }, [etaData]);

  const hasEtaData = etaData && etaData.length > 0;

  const sortedPOIs = useMemo(() => {
    if (!pois) return [];

    return [...pois].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'category':
          comparison = (a.category || '').localeCompare(b.category || '');
          break;
        case 'coordinates':
          comparison = a.latitude - b.latitude || a.longitude - b.longitude;
          break;
        case 'status':
          comparison = (a.active ? 1 : 0) - (b.active ? 1 : 0);
          break;
        case 'created':
          comparison =
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case 'eta': {
          const etaA = etaMap.get(a.id)?.eta || '';
          const etaB = etaMap.get(b.id)?.eta || '';
          comparison = etaA.localeCompare(etaB);
          break;
        }
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [pois, sortField, sortDirection, etaMap]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this POI?')) {
      await deletePOI.mutateAsync(id);
      onDeletePOI(id);
    }
  };

  if (isLoading) return <div>Loading POIs...</div>;
  if (error) return <div>Error loading POIs: {(error as Error).message}</div>;

  const colCount = hasEtaData ? 8 : 6;

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead
              className="cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => handleSort('name')}
            >
              Name
              <SortIcon
                field="name"
                currentSortField={sortField}
                sortDirection={sortDirection}
              />
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => handleSort('category')}
            >
              Category
              <SortIcon
                field="category"
                currentSortField={sortField}
                sortDirection={sortDirection}
              />
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => handleSort('coordinates')}
            >
              Coordinates
              <SortIcon
                field="coordinates"
                currentSortField={sortField}
                sortDirection={sortDirection}
              />
            </TableHead>
            <TableHead
              className="cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => handleSort('status')}
            >
              Status
              <SortIcon
                field="status"
                currentSortField={sortField}
                sortDirection={sortDirection}
              />
            </TableHead>
            {hasEtaData && (
              <>
                <TableHead
                  className="cursor-pointer hover:bg-gray-100 select-none"
                  onClick={() => handleSort('eta')}
                >
                  ETA / Bearing
                  <SortIcon
                    field="eta"
                    currentSortField={sortField}
                    sortDirection={sortDirection}
                  />
                </TableHead>
                <TableHead>Course</TableHead>
              </>
            )}
            <TableHead
              className="cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => handleSort('created')}
            >
              Created
              <SortIcon
                field="created"
                currentSortField={sortField}
                sortDirection={sortDirection}
              />
            </TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedPOIs.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={colCount}
                className="text-center py-8 text-gray-500"
              >
                No POIs yet. Create one to get started.
              </TableCell>
            </TableRow>
          ) : (
            sortedPOIs.map((poi: POI) => {
              const eta = etaMap.get(poi.id);
              return (
                <TableRow key={poi.id}>
                  <TableCell className="font-medium">{poi.name}</TableCell>
                  <TableCell>
                    {poi.category || (
                      <span className="text-gray-400">&mdash;</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {poi.latitude.toFixed(4)}, {poi.longitude.toFixed(4)}
                  </TableCell>
                  <TableCell>
                    <span
                      className={`px-2 py-1 rounded-full text-sm ${
                        poi.active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {poi.active ? 'Active' : 'Inactive'}
                    </span>
                  </TableCell>
                  {hasEtaData && (
                    <>
                      <TableCell className="text-sm">
                        {eta?.eta_seconds != null && eta.eta_seconds >= 0 ? (
                          <div>
                            <span className="font-medium">
                              {formatETA(eta.eta_seconds)}
                            </span>
                            {eta.eta_type && (
                              <span
                                className={`ml-1 text-xs px-1 py-0.5 rounded ${
                                  eta.eta_type === 'anticipated'
                                    ? 'bg-orange-100 text-orange-700'
                                    : 'bg-blue-100 text-blue-700'
                                }`}
                              >
                                {eta.eta_type === 'anticipated' ? 'ant' : 'est'}
                              </span>
                            )}
                            {eta.bearing_degrees != null && (
                              <span className="text-gray-500 ml-1">
                                {eta.bearing_degrees.toFixed(0)}&deg;
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400">&mdash;</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {eta?.route_aware_status ? (
                          <RouteAwareStatusBadge
                            status={eta.route_aware_status}
                          />
                        ) : eta?.course_status ? (
                          <CourseStatusBadge status={eta.course_status} />
                        ) : (
                          <span className="text-gray-400">&mdash;</span>
                        )}
                      </TableCell>
                    </>
                  )}
                  <TableCell>
                    {new Date(poi.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right space-x-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onSelectPOI(poi.id)}
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEditPOI(poi.id)}
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(poi.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function formatETA(seconds: number): string {
  if (seconds < 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m} min`;
}

function CourseStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    on_course: 'bg-green-100 text-green-800',
    slightly_off: 'bg-yellow-100 text-yellow-800',
    off_track: 'bg-orange-100 text-orange-800',
    behind: 'bg-red-100 text-red-800',
  };
  const labels: Record<string, string> = {
    on_course: 'On Course',
    slightly_off: 'Slightly Off',
    off_track: 'Off Track',
    behind: 'Behind',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs ${styles[status] || ''}`}>
      {labels[status] || status}
    </span>
  );
}

function RouteAwareStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ahead_on_route: 'bg-blue-100 text-blue-800',
    already_passed: 'bg-gray-100 text-gray-600',
    not_on_route: 'bg-yellow-100 text-yellow-800',
    pre_departure: 'bg-orange-100 text-orange-700',
  };
  const labels: Record<string, string> = {
    ahead_on_route: 'Ahead',
    already_passed: 'Passed',
    not_on_route: 'Off Route',
    pre_departure: 'Pre-Dep',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs ${styles[status] || ''}`}>
      {labels[status] || status}
    </span>
  );
}
