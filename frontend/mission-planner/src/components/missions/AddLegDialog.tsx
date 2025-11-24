import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import type { MissionLeg } from '../../types/mission';

interface AddLegDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAddLeg: (leg: Partial<MissionLeg>) => Promise<void>;
  isSubmitting?: boolean;
}

export function AddLegDialog({
  open,
  onOpenChange,
  onAddLeg,
  isSubmitting = false,
}: AddLegDialogProps) {
  const [legId, setLegId] = useState('');
  const [legName, setLegName] = useState('');
  const [routeId, setRouteId] = useState('');
  const [description, setDescription] = useState('');
  const [localSubmitting, setLocalSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!legId.trim() || !legName.trim()) {
      return;
    }

    setLocalSubmitting(true);

    try {
      await onAddLeg({
        id: legId,
        name: legName,
        route_id: routeId || undefined,
        description: description || undefined,
        transports: {
          initial_x_satellite_id: 'X-1',
          initial_ka_satellite_ids: ['AOR', 'POR', 'IOR'],
          x_transitions: [],
          ka_outages: [],
          aar_windows: [],
          ku_overrides: [],
        },
      });

      // Reset form
      setLegId('');
      setLegName('');
      setRouteId('');
      setDescription('');
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to add leg:', error);
    } finally {
      setLocalSubmitting(false);
    }
  };

  const submitting = localSubmitting || isSubmitting;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add New Leg to Mission</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="leg-id">Leg ID *</Label>
            <Input
              id="leg-id"
              value={legId}
              onChange={(e) => setLegId(e.target.value)}
              placeholder="leg-1"
              required
              disabled={submitting}
            />
          </div>
          <div>
            <Label htmlFor="leg-name">Leg Name *</Label>
            <Input
              id="leg-name"
              value={legName}
              onChange={(e) => setLegName(e.target.value)}
              placeholder="First Leg"
              required
              disabled={submitting}
            />
          </div>
          <div>
            <Label htmlFor="route-id">Route ID</Label>
            <Input
              id="route-id"
              value={routeId}
              onChange={(e) => setRouteId(e.target.value)}
              placeholder="simple-circular"
              disabled={submitting}
            />
          </div>
          <div>
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              disabled={submitting}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting || !legId.trim() || !legName.trim()}>
              {submitting ? 'Adding...' : 'Add Leg'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
