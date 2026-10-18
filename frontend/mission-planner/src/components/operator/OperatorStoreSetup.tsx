import { useState } from 'react';
import { operatorFailure, provisionOperatorStore } from '@/services/operator';
import type { OperatorHealth } from '@/types/operator';

export function OperatorStoreSetup({
  health,
  error,
  refresh,
}: {
  health?: OperatorHealth;
  error?: unknown;
  refresh: () => unknown;
}) {
  const [working, setWorking] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  if (health?.ready) return null;
  const code =
    health?.enabled === false || operatorFailure(error).status === 404
      ? 'operator_disabled'
      : (health?.error_code ?? 'store_unavailable');
  const description: Record<string, string> = {
    operator_disabled:
      'Operator is disabled for this deployment. Enable OPERATOR_ENABLED in the deployment configuration, then restart the application.',
    store_initialization_required:
      'This source has no Operator journal yet. Initialize its new journal to create calls, conferences, issues and notes. Existing journals are never reset by this action.',
    simulation_run_required:
      'Choose and start a simulation in Missions before initializing its Operator journal. A configured nonproduction training instance may supply its explicit simulation namespace.',
    store_recovery_required:
      'Journal files or recovery artifacts already exist. Initialization is blocked. Follow the recovery procedure; do not delete or replace the store to make this message disappear.',
    store_corrupt:
      'The existing journal failed its integrity checks. Preserve it and follow the recovery procedure. Initialization is blocked.',
    store_mode_mismatch:
      'The existing journal belongs to a different live or simulation source. Check the deployment and active simulation run; this action cannot change its identity.',
    store_identity_mismatch:
      'The journal database and durable identity do not match. Preserve both and follow the recovery procedure.',
    invalid_configuration:
      'Operator configuration is invalid. Check the deployment settings before retrying.',
  };
  return (
    <section
      className="space-y-3 rounded-xl border border-amber-400/50 p-4"
      aria-label="Operator store setup"
    >
      <h2 className="text-lg font-semibold">
        {code === 'store_initialization_required'
          ? 'Set up this Operator journal'
          : code === 'operator_disabled'
            ? 'Operator is disabled'
            : 'Operator store needs attention'}
      </h2>
      <p>
        {description[code] ??
          'The Operator store is unavailable. Check the service and durable storage, then recheck. Your retained drafts remain available.'}
      </p>
      {health && (
        <p className="break-words text-sm">
          Source: {health.source_mode}
          {health.simulation_run_id
            ? ` · simulation run ${health.simulation_run_id}`
            : ''}
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        Missing ETA, PoP or other optional model inputs affect their advisories.
        They do not disable journal actions once this store is ready.
      </p>
      {failure && <p role="alert">{failure}</p>}
      <div className="flex flex-wrap gap-2">
        {code === 'store_initialization_required' && health && (
          <button
            className="min-h-11 rounded border px-3 disabled:opacity-50"
            disabled={working}
            onClick={async () => {
              setWorking(true);
              setFailure(null);
              try {
                await provisionOperatorStore(health);
                await refresh();
              } catch (error) {
                const value = operatorFailure(error);
                setFailure(
                  `${value.message} · ${value.code}. Recheck the current source before trying again.`
                );
              } finally {
                setWorking(false);
              }
            }}
          >
            {working
              ? 'Initializing journal…'
              : `Initialize ${health.source_mode} journal`}
          </button>
        )}
        <button
          className="min-h-11 rounded border px-3"
          disabled={working}
          onClick={() => void refresh()}
        >
          Recheck store
        </button>
        <a
          className="inline-flex min-h-11 items-center px-3 underline"
          href="/operator-help/setup.html"
          target="_blank"
          rel="noreferrer"
        >
          Operator setup and recovery
        </a>
      </div>
      <p className="text-xs text-muted-foreground">Diagnostic: {code}</p>
    </section>
  );
}
