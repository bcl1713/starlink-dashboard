import { Button } from '../../components/ui/button';

interface LegHeaderProps {
  missionId: string;
  legId: string;
  onBackClick: () => void;
}

/**
 * Header component for the Leg Detail page
 */
export function LegHeader({ missionId, legId, onBackClick }: LegHeaderProps) {
  return (
    <div>
      <Button variant="ghost" onClick={onBackClick} className="mb-4">
        ← Back to Mission
      </Button>
      <h1 className="text-3xl font-bold">Leg Configuration</h1>
      <p className="text-muted-foreground">
        Mission: {missionId} | Leg: {legId}
      </p>
    </div>
  );
}
