import { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

interface EditableFieldProps {
  value: string;
  onSave: (newValue: string) => Promise<void>;
  isLoading?: boolean;
  multiline?: boolean;
  placeholder?: string;
  className?: string;
}

export function EditableField({
  value,
  onSave,
  isLoading = false,
  multiline = false,
  placeholder = '',
  className = '',
}: EditableFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setError(null);

    // Validate non-empty
    if (editValue.trim() === '') {
      setError('Value cannot be empty');
      return;
    }

    try {
      await onSave(editValue);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    }
  };

  const handleCancel = () => {
    setEditValue(value);
    setError(null);
    setIsEditing(false);
  };

  if (!isEditing) {
    return (
      <div
        className={`cursor-pointer hover:bg-gray-100 rounded px-2 py-1 ${className}`}
        onClick={() => {
          setEditValue(value);
          setIsEditing(true);
        }}
        title="Click to edit"
      >
        {value || placeholder}
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {multiline ? (
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full border rounded-md px-3 py-2 text-sm min-h-[80px] focus:outline-none focus:ring-2 focus:ring-blue-500"
          rows={3}
          autoFocus
        />
      ) : (
        <Input
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={placeholder}
          disabled={isLoading}
          className="w-full"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSave();
            } else if (e.key === 'Escape') {
              handleCancel();
            }
          }}
        />
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex gap-2">
        <Button size="sm" onClick={handleSave} disabled={isLoading}>
          {isLoading ? 'Saving...' : 'Save'}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={handleCancel}
          disabled={isLoading}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
