import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import type { Mission } from '../../types/mission';

interface MissionCardProps {
  mission: Mission;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onExport: (id: string, name: string) => void;
}

export function MissionCard({ mission, onSelect, onDelete, onExport }: MissionCardProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    onSelect(mission.id);
    navigate(`/missions/${mission.id}`);
  };

  return (
    <Card className="cursor-pointer hover:shadow-lg transition-shadow">
      <CardHeader onClick={handleClick}>
        <CardTitle>{mission.name}</CardTitle>
        <CardDescription>{mission.description || 'No description'}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">
            {mission.legs.length} leg{mission.legs.length !== 1 ? 's' : ''}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onExport(mission.id, mission.name);
              }}
            >
              Export
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(mission.id);
              }}
            >
              Delete
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
