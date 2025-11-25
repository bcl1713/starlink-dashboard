import { useState } from 'react';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { useCreateSatellite } from '../../hooks/api/useSatellites';

interface AddSatelliteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddSatelliteDialog({
  open,
  onOpenChange,
}: AddSatelliteDialogProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState<'X-Band' | 'Ka-Band' | 'Ku-Band'>('X-Band');
  const [description, setDescription] = useState('');

  const createSatellite = useCreateSatellite();

  const handleSubmit = async () => {
    await createSatellite.mutateAsync({
      name,
      type,
      description: description || undefined,
    });
    onOpenChange(false);
    // Reset form
    setName('');
    setType('X-Band');
    setDescription('');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add New Satellite</DialogTitle>
          <DialogDescription>
            Add a new satellite to the catalog.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Satellite name"
            />
          </div>

          <div>
            <Label htmlFor="type">Type</Label>
            <Select value={type} onValueChange={(val) => setType(val as any)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="X-Band">X-Band</SelectItem>
                <SelectItem value="Ka-Band">Ka-Band</SelectItem>
                <SelectItem value="Ku-Band">Ku-Band</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!name}>
            Add Satellite
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
