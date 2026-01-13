import { useState } from 'react';
import { Button } from './button';
import { ChevronDown } from 'lucide-react';

interface IconPickerProps {
  value: string;
  onChange: (icon: string) => void;
  disabled?: boolean;
}

const AVAILABLE_ICONS = [
  '📍',
  '🔴',
  '🟠',
  '🟡',
  '🟢',
  '🔵',
  '🟣',
  '⚫',
  '⭐',
  '❤️',
  '✈️',
  '🚀',
  '📌',
  '🏁',
  '⚠️',
  '🛑',
];

export function IconPicker({ value, onChange, disabled }: IconPickerProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative inline-block">
      <Button
        variant="outline"
        onClick={() => setOpen(!open)}
        disabled={disabled}
        className="w-full justify-between"
      >
        <span className="text-lg">{value || '📍'}</span>
        <ChevronDown className="w-4 h-4" />
      </Button>

      {open && (
        <div className="absolute z-50 w-48 bg-white border rounded-lg shadow-lg p-2 mt-2 grid grid-cols-4 gap-2">
          {AVAILABLE_ICONS.map((icon) => (
            <button
              key={icon}
              onClick={() => {
                onChange(icon);
                setOpen(false);
              }}
              className={`p-2 text-2xl rounded hover:bg-gray-100 transition ${
                value === icon ? 'bg-blue-100' : ''
              }`}
            >
              {icon}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
