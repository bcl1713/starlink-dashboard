import { useState } from 'react';
import { useTransportAvailability } from '@/hooks/api/useTransportAvailability';
import {
  activeTransportFailures,
  rfTransports,
  type RFTransport,
} from '@/services/transportAvailability';
export function OperatorTransportAvailability({
  missionId,
}: {
  missionId: string;
}) {
  const availability = useTransportAvailability(missionId);
  const [reasons, setReasons] = useState<Partial<Record<RFTransport, string>>>(
    {}
  );
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const view = availability.data;
  const failures = view ? activeTransportFailures(view) : {};
  const activeLeg = view?.legs.find(
    (row) =>
      row.leg_id === view.active_leg_id ||
      row.installed_leg_id === view.active_leg_id
  );
  return (
    <section
      id="mission-transport-availability"
      aria-label="Mission transport availability"
      className="min-w-0 space-y-3 rounded-xl border border-slate-600 p-4"
    >
      <h2>Transport availability</h2>
      <p className="ws-meta">
        Equipment failures apply from now through the rest of this mission,
        across legs, until restored. Restore returns to planned settings.
      </p>
      {!view && (
        <p role={availability.isError ? 'alert' : 'status'}>
          {availability.isError
            ? 'Availability could not be loaded.'
            : 'Loading availability…'}
        </p>
      )}
      {view && (
        <>
          {!view.operator_actions_allowed && (
            <p role="status">{view.operator_actions_unavailable_reason}</p>
          )}
          <div className="grid min-w-0 gap-3 lg:grid-cols-3">
            {rfTransports.map(({ key, label }) => {
              const failure = failures[key];
              const planned = activeLeg?.planned[key];
              const disabled =
                availability.isSaving ||
                availability.isError ||
                !view.operator_actions_allowed;
              return (
                <fieldset
                  aria-label={`${label} availability`}
                  key={key}
                  className="min-w-0 space-y-3 rounded-lg border border-slate-600 p-3"
                >
                  <legend className="px-1 font-semibold">{label}</legend>
                  <p>
                    {view.effective?.[key] === true
                      ? 'Available'
                      : failure
                        ? 'Unavailable · equipment failure'
                        : planned === false
                          ? 'Planned unavailable'
                          : 'No active availability'}
                  </p>
                  {failure?.reason && (
                    <p className="ws-meta break-words">{failure.reason}</p>
                  )}
                  {!failure && (
                    <label className="block text-sm">
                      Reason (optional)
                      <input
                        className="ws-field w-full min-w-0"
                        maxLength={2000}
                        aria-label={`${label} reason (optional)`}
                        value={reasons[key] ?? ''}
                        disabled={disabled}
                        onChange={(e) =>
                          setReasons((current) => ({
                            ...current,
                            [key]: e.target.value,
                          }))
                        }
                      />
                    </label>
                  )}
                  <button
                    className="ws-button w-full whitespace-normal"
                    disabled={disabled}
                    onClick={async () => {
                      setError('');
                      setMessage('');
                      try {
                        await availability.act({
                          transport: key,
                          action: failure ? 'restore' : 'unavailable',
                          ...(!failure && reasons[key]?.trim()
                            ? { reason: reasons[key]!.trim() }
                            : {}),
                        });
                        setReasons((current) => ({ ...current, [key]: '' }));
                        setMessage(
                          `${label} ${failure ? 'restored to planned settings' : 'unavailable for rest of mission'}.`
                        );
                      } catch {
                        setError(
                          'Availability action was not confirmed. Showing confirmed state; refresh or retry. Another operator may have changed it.'
                        );
                      }
                    }}
                  >
                    {failure ? 'Restore' : 'Unavailable for rest of mission'}
                  </button>
                </fieldset>
              );
            })}
          </div>
          {!!view.history.length && (
            <details>
              <summary>Availability history</summary>
              <ul className="space-y-1 text-sm">
                {view.history.map((entry) => (
                  <li key={entry.id} className="break-words">
                    {
                      rfTransports.find((item) => item.key === entry.transport)
                        ?.label
                    }{' '}
                    · {entry.unavailable ? 'Unavailable' : 'Restored'} ·{' '}
                    {entry.effective_at}
                    {entry.simulation_run_id ? ' · Simulation' : ' · Live'}
                    {entry.reason ? ` · ${entry.reason}` : ''}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      {(availability.isError || error) && (
        <p role="alert">
          {error ||
            'Availability could not be refreshed. Last confirmed state is shown.'}
        </p>
      )}
      <button
        className="ws-button"
        disabled={availability.isSaving}
        onClick={() => void availability.refetch()}
      >
        Refresh availability
      </button>
      {availability.isSaving && <p role="status">Saving availability…</p>}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
