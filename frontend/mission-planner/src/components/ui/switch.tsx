import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

// Native input retains labels, Space-key interaction and form semantics.
export const Switch = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>
>(({ className, ...props }, ref) => (
  <span className="relative inline-flex h-6 w-11 shrink-0 align-middle">
    <input
      {...props}
      ref={ref}
      type="checkbox"
      role="switch"
      className={cn(
        'peer absolute inset-0 z-10 m-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed',
        className
      )}
    />
    <span
      aria-hidden="true"
      className="pointer-events-none h-6 w-11 rounded-full border border-input bg-muted transition-colors peer-checked:border-primary peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background peer-disabled:opacity-50"
    />
    <span
      aria-hidden="true"
      className="pointer-events-none absolute left-0.5 top-0.5 size-5 rounded-full bg-foreground shadow-sm transition-transform peer-checked:translate-x-5 peer-checked:bg-primary-foreground peer-disabled:opacity-50"
    />
  </span>
));
Switch.displayName = 'Switch';
