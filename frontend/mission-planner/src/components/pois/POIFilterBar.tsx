import { useState, useEffect } from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { X, Eye, EyeOff } from 'lucide-react';

interface POIFilterBarProps {
  onFilterChange: (filters: FilterOptions) => void;
  showRoutePOIs: boolean;
  onShowRoutePOIsChange: (show: boolean) => void;
}

export interface FilterOptions {
  search?: string;
  category?: string | null;
  courseStatus?: 'ahead_on_route' | 'already_passed' | 'not_on_route' | null;
}

export function POIFilterBar({
  onFilterChange,
  showRoutePOIs,
  onShowRoutePOIsChange,
}: POIFilterBarProps) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string | null>(null);
  const [courseStatus, setCourseStatus] = useState<
    'ahead_on_route' | 'already_passed' | 'not_on_route' | null
  >(null);

  useEffect(() => {
    onFilterChange({
      search: search || undefined,
      category,
      courseStatus,
    });
  }, [search, category, courseStatus, onFilterChange]);

  const handleReset = () => {
    setSearch('');
    setCategory(null);
    setCourseStatus(null);
    onFilterChange({});
  };

  const hasFilters = search || category || courseStatus;

  return (
    <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
      <div className="flex gap-2">
        <div className="flex-1">
          <Input
            placeholder="Search POIs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1"
          />
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Button
          variant={showRoutePOIs ? 'default' : 'outline'}
          size="sm"
          onClick={() => onShowRoutePOIsChange(!showRoutePOIs)}
        >
          {showRoutePOIs ? (
            <>
              <Eye className="w-4 h-4 mr-1" />
              Route POIs Visible
            </>
          ) : (
            <>
              <EyeOff className="w-4 h-4 mr-1" />
              Route POIs Hidden
            </>
          )}
        </Button>

        {courseStatus && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCourseStatus(null)}
          >
            {courseStatus}
            <X className="w-3 h-3 ml-1" />
          </Button>
        )}

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={handleReset}>
            Clear all
          </Button>
        )}
      </div>
    </div>
  );
}
