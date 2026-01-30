import { useState, useMemo } from 'react';
import { useRoutes, useDeleteRoute } from '../../hooks/api/useRoutes';
import type { Route } from '../../services/routes';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Button } from '../ui/button';
import { Trash2, Download, Eye, ArrowUp, ArrowDown } from 'lucide-react';

type SortField = 'name' | 'points' | 'status' | 'created';
type SortDirection = 'asc' | 'desc';

interface RouteListProps {
  onSelectRoute: (id: string) => void;
  onDelete: (id: string) => void;
  onDownload: (route: Route) => void;
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

export function RouteList({
  onSelectRoute,
  onDelete,
  onDownload,
}: RouteListProps) {
  const { data: routes, isLoading, error } = useRoutes();
  const deleteRoute = useDeleteRoute();
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const sortedRoutes = useMemo(() => {
    if (!routes) return [];

    return [...routes].sort((a, b) => {
      let comparison = 0;

      switch (sortField) {
        case 'name':
          comparison = a.name.localeCompare(b.name);
          break;
        case 'points':
          comparison = (a.point_count || 0) - (b.point_count || 0);
          break;
        case 'status':
          comparison = (a.is_active ? 1 : 0) - (b.is_active ? 1 : 0);
          break;
        case 'created':
          comparison =
            new Date(a.imported_at || 0).getTime() -
            new Date(b.imported_at || 0).getTime();
          break;
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });
  }, [routes, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  if (isLoading) return <div>Loading routes...</div>;
  if (error) return <div>Error loading routes: {(error as Error).message}</div>;

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this route?')) {
      deleteRoute.mutate(id);
      onDelete(id);
    }
  };

  return (
    <div className="border rounded-lg">
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
              onClick={() => handleSort('points')}
            >
              Points
              <SortIcon
                field="points"
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
            <TableHead
              className="cursor-pointer hover:bg-gray-100 select-none"
              onClick={() => handleSort('created')}
            >
              Imported
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
          {sortedRoutes.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="text-center py-8 text-gray-500">
                No routes yet. Upload a route to get started.
              </TableCell>
            </TableRow>
          ) : (
            sortedRoutes.map((route) => (
              <TableRow key={route.id}>
                <TableCell className="font-medium">{route.name}</TableCell>
                <TableCell>{route.point_count || 0}</TableCell>
                <TableCell>
                  <span
                    className={`px-2 py-1 rounded-full text-sm ${
                      route.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {route.is_active ? 'Active' : 'Inactive'}
                  </span>
                </TableCell>
                <TableCell>
                  {route.imported_at
                    ? new Date(route.imported_at).toLocaleDateString()
                    : '-'}
                </TableCell>
                <TableCell className="text-right space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onSelectRoute(route.id)}
                    title="View route details"
                  >
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDownload(route)}
                    title="Download KML"
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(route.id)}
                    title="Delete route"
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
