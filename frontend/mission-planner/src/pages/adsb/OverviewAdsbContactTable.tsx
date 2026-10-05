import type { AdsbContactView } from './overview-adsb-state';
interface Props {
  contacts: readonly AdsbContactView[];
  disabled: boolean;
  onInclude: (hex: string) => void;
  onExclude: (hex: string) => void;
}
export function OverviewAdsbContactTable({
  contacts,
  disabled,
  onInclude,
  onExclude,
}: Props) {
  return (
    <section aria-label="Active ADS-B aircraft" className="mt-4">
      <h3 className="font-semibold">Active aircraft</h3>
      <p className="text-sm text-muted-foreground">
        All eligible worldwide contacts, including aircraft outside the visible
        globe.
      </p>
      {contacts.length === 0 ? (
        <p>No active aircraft. Saved lists remain available below.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">
              Active globally selected ADS-B aircraft
            </caption>
            <thead>
              <tr>
                <th scope="col">Hex</th>
                <th scope="col">Identity</th>
                <th scope="col">Selection</th>
                <th scope="col">Position age</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {[...contacts]
                .sort((a, b) => a.hex.localeCompare(b.hex))
                .map((c) => (
                  <tr key={c.hex}>
                    <th scope="row" className="p-2 font-mono">
                      {c.hex}
                    </th>
                    <td className="p-2 break-words [overflow-wrap:anywhere]">
                      {c.label}
                    </td>
                    <td className="p-2">
                      {c.included ? 'Included' : 'Background'}
                    </td>
                    <td className="p-2">
                      {c.freshness === 'current' ? 'Current' : '◷ Stale'} ·{' '}
                      {Math.floor(c.position_age_seconds)}s
                    </td>
                    <td className="p-2">
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="min-h-11 rounded border px-2 disabled:opacity-50"
                          type="button"
                          disabled={disabled || c.included}
                          aria-label={`Include ${c.hex}`}
                          onClick={() => onInclude(c.hex)}
                        >
                          Include
                        </button>
                        <button
                          className="min-h-11 rounded border px-2 disabled:opacity-50"
                          type="button"
                          disabled={disabled}
                          aria-label={`Exclude ${c.hex}`}
                          onClick={() => onExclude(c.hex)}
                        >
                          Exclude
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
