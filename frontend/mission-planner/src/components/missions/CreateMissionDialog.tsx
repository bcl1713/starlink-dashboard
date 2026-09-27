import { useState } from 'react';
import { useCreateMission } from '../../hooks/api/useMissions';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

interface CreateMissionDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (missionId: string) => void;
}

export function CreateMissionDialog({
  open,
  onClose,
  onSuccess,
}: CreateMissionDialogProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const createMission = useCreateMission();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) return;

    const id = name.toLowerCase().replace(/\s+/g, '-');
    setCreateError(null);

    try {
      const mission = await createMission.mutateAsync({
        id,
        name,
        description: description || undefined,
        legs: [],
      });

      setName('');
      setDescription('');
      onSuccess(mission.id);
      onClose();
    } catch (error) {
      setCreateError(
        error instanceof Error
          ? `Unable to create mission: ${error.message}`
          : 'Unable to create mission. Please try again.'
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create New Mission</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="name">Mission Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Operation Falcon"
              required
            />
          </div>
          <div>
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Multi-leg transcontinental mission"
            />
          </div>
          {createError && (
            <p role="alert" className="text-sm text-destructive">
              {createError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMission.isPending}>
              {createMission.isPending ? 'Creating...' : 'Create Mission'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
