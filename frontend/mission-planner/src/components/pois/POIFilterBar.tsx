import { useState } from 'react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { X } from 'lucide-react';

interface POIFilterBarProps {
  onFilterChange: (filters: FilterOptions) => void;
  onActiveOnlyChange?: (activeOnly: boolean) => void;
}

export interface FilterOptions {
  search?: string;
  category?: string | null;
  courseStatus?: 'ahead_on_route' | 'already_passed' | 'not_on_route' | null;
  approaching?: boolean;
}

export function POIFilterBar({
  onFilterChange,
  onActiveOnlyChange,
}: POIFilterBarProps) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string | null>(null);
  const [courseStatus, setCourseStatus] = useState<
    'ahead_on_route' | 'already_passed' | 'not_on_route' | null
  >(null);
  const [approaching, setApproaching] = useState(false);
  const [activeOnly, setActiveOnly] = useState(false);

  const handleFilterChange = () => {
    onFilterChange({
      search: search || undefined,
      category,
      courseStatus,
      approaching,
    });
  };

  const handleActiveOnlyChange = (value: boolean) => {
    setActiveOnly(value);
    onActiveOnlyChange?.(value);
  };

  const handleReset = () => {
    setSearch('');
    setCategory(null);
    setCourseStatus(null);
    setApproaching(false);
    setActiveOnly(false);
    onFilterChange({});
    onActiveOnlyChange?.(false);
  };

  return (
    <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
      <div className="flex gap-2">
        <div className="flex-1">
          <Input
            placeholder="Search POIs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyUp={handleFilterChange}
            className="flex-1"
          />
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Button
          variant={activeOnly ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleActiveOnlyChange(!activeOnly)}
        >
          {activeOnly ? 'Showing Active Only' : 'Show All POIs'}
        </Button>

        <Button
          variant={approaching ? 'default' : 'outline'}
          size="sm"
          onClick={() => {
            setApproaching(!approaching);
            handleFilterChange();
          }}
        >
          Approaching (30 min)
        </Button>

        {courseStatus && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setCourseStatus(null);
              handleFilterChange();
            }}
          >
            {courseStatus}
            <X className="w-3 h-3 ml-1" />
          </Button>
        )}

        {search || category || courseStatus || approaching || activeOnly ? (
          <Button variant="ghost" size="sm" onClick={handleReset}>
            Clear all
          </Button>
        ) : null}
      </div>
    </div>
  );
}
