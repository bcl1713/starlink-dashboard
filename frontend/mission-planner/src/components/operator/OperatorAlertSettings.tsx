import * as Popover from '@radix-ui/react-popover';
import { usePageTheme } from '@/lib/page-theme';
import type { AlertPreferences, DeliveryResult } from './eventEmitter';
interface AlertSettingsProps {
  preferences: AlertPreferences;
  onChange: (preferences: AlertPreferences) => void;
  delivery: DeliveryResult | null;
  onEnable: () => Promise<void>;
}
export function OperatorAlertSettings({
  preferences,
  onChange,
  delivery,
  onEnable,
}: AlertSettingsProps) {
  const theme = usePageTheme();
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button className="min-h-11 rounded-md border px-3 text-sm">
          Local alerts
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={8}
          align="end"
          className={`z-[1002] w-72 space-y-3 rounded-xl border bg-card p-4 text-sm text-foreground shadow-xl ${theme}`}
        >
          <h3 className="font-semibold">Local alerts</h3>
          {(
            [
              ['enabled', 'In-app cues'],
              ['sound', 'Sound'],
              ['vibration', 'Vibration'],
            ] as const
          ).map(([key, label]) => (
            <label
              key={key}
              className="flex min-h-11 items-center justify-between gap-3"
            >
              <span>{label}</span>
              <input
                type="checkbox"
                checked={preferences[key]}
                onChange={(event) =>
                  onChange({ ...preferences, [key]: event.target.checked })
                }
              />
            </label>
          ))}
          <button
            className="min-h-11 w-full rounded-md border px-3 disabled:opacity-50"
            disabled={!delivery}
            onClick={() => {
              void onEnable();
            }}
          >
            Enable sound and vibration
          </button>
          <p>
            Sound {delivery?.sound.replaceAll('_', ' ') ?? 'needs interaction'}{' '}
            · vibration{' '}
            {delivery?.vibration.replaceAll('_', ' ') ?? 'best effort'}.
          </p>
          <p className="text-muted-foreground">
            Closed or background browser delivery is not guaranteed. Routine
            follow-ups are silent; vibration is best effort.
          </p>
          {delivery?.coordination === 'unavailable' && (
            <p role="status">
              Automatic cues unavailable on this browser. The timeline remains
              available.
            </p>
          )}
          <Popover.Close className="min-h-11 rounded-md border px-3">
            Close settings
          </Popover.Close>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
