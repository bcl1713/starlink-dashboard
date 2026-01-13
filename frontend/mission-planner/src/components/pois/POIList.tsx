import { usePOIs, useDeletePOI } from '../../hooks/api/usePOIs';
import type { POI } from '../../services/pois';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Button } from '../ui/button';
import { Trash2, Edit, Eye } from 'lucide-react';

interface POIListProps {
  onSelectPOI: (id: string) => void;
  onEditPOI: (id: string) => void;
  onDeletePOI: (id: string) => void;
}

export function POIList({ onSelectPOI, onEditPOI, onDeletePOI }: POIListProps) {
  const { data: pois, isLoading, error } = usePOIs();
  const deletePOI = useDeletePOI();

  if (isLoading) return <div>Loading POIs...</div>;
  if (error) return <div>Error loading POIs: {(error as Error).message}</div>;

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this POI?')) {
      deletePOI.mutate(id);
      onDeletePOI(id);
    }
  };

  return (
    <div className="border rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Coordinates</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {pois?.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-gray-500">
                No POIs yet. Create one to get started.
              </TableCell>
            </TableRow>
          ) : (
            pois?.map((poi: POI) => (
              <TableRow key={poi.id}>
                <TableCell className="font-medium">{poi.name}</TableCell>
                <TableCell>
                  {poi.category || <span className="text-gray-400">—</span>}
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
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
