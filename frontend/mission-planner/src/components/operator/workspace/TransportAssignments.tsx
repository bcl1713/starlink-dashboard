import { transportLabel } from '../transportLabel';
import {
  catalogTransportKey,
  type TransportEligibility,
} from '@/services/transportAvailability';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  readTransportCatalog,
  saveTransportCatalog,
  type TransportCatalog,
  type CatalogItem,
} from '@/services/transportCatalog';
import { readOperatorRecords } from '@/services/operator';
import type { SavedRecord } from '@/types/operator';
import { TransportCatalogManager } from './TransportCatalogManager';
import { latestAssignment } from './transportAssignments';

export function TransportAssignments({
  records,
  legId,
  disabled,
  onApply,
  missionId,
  identity,
  availability,
}: {
  missionId?: string;
  identity?: string | null;
  availability?: TransportEligibility;
  records: SavedRecord[];
  legId: string | null;
  disabled: boolean;
  onApply: (service: CatalogItem, transport: CatalogItem) => Promise<void>;
}) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['operator-transport-catalog'],
    queryFn: readTransportCatalog,
    retry: false,
  });
  const reports = useQuery({
    queryKey: [
      'operator-records',
      missionId,
      identity,
      'transport-assignments',
    ],
    enabled: !!missionId && !!identity,
    retry: false,
    queryFn: async () => {
      const result: SavedRecord[] = [];
      let cursor: string | undefined;
      do {
        const page = await readOperatorRecords(
          {
            mission_id: missionId!,
            record_type: 'transport_decision',
            include_removed: true,
          },
          cursor
        );
        result.push(...page.items.map((i) => i.record));
        cursor = page.cursor ?? undefined;
      } while (cursor);
      return result;
    },
  });
  const merged = new Map((reports.data ?? []).map((r) => [r.record_id, r]));
  for (const record of records) {
    if (
      !merged.has(record.record_id) ||
      merged.get(record.record_id)!.version < record.version
    )
      merged.set(record.record_id, record);
  }
  const assignments = [...merged.values()];
  const [manage, setManage] = useState<'services' | 'transports' | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  async function save(catalog: TransportCatalog) {
    setSaving(true);
    setError('');
    try {
      const accepted = await saveTransportCatalog(catalog);
      client.setQueryData(['operator-transport-catalog'], accepted);
      return true;
    } catch {
      setError(
        'Catalog could not be saved. Refresh and try again; another operator may have changed it.'
      );
      return false;
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap gap-2">
        <button className="ws-button" onClick={() => setManage('services')}>
          Manage services
        </button>
        <button className="ws-button" onClick={() => setManage('transports')}>
          Manage transports
        </button>
      </div>
      {(query.isError || error) && (
        <div role="alert">
          {error || 'Catalog unavailable.'}
          <button
            className="ws-button"
            onClick={() => {
              setError('');
              void query.refetch();
            }}
          >
            Refresh catalog
          </button>
        </div>
      )}
      {saving && <p role="status">Saving catalog…</p>}
      {manage && query.data && (
        <TransportCatalogManager
          key={manage}
          catalog={query.data}
          kind={manage}
          saving={saving}
          onSave={save}
          onClose={() => setManage(null)}
        />
      )}
      {reports.isError && (
        <p role="alert">
          Assignments could not be refreshed.{' '}
          <button className="ws-button" onClick={() => void reports.refetch()}>
            Refresh assignments
          </button>
        </p>
      )}
      {query.isPending && <p role="status">Loading services…</p>}
      {query.data && (
        <div className="grid min-w-0 gap-3 lg:grid-cols-2">
          {query.data.services
            .filter((s) => s.enabled && !s.archived)
            .map((service) => (
              <AssignmentCard
                key={service.id}
                service={service}
                catalog={query.data!}
                availability={availability}
                assignment={latestAssignment(assignments, service, legId)}
                disabled={
                  disabled ||
                  query.isError ||
                  (!!missionId && (!reports.data || reports.isError))
                }
                onApply={onApply}
              />
            ))}
          {!query.data.services.some((s) => s.enabled && !s.archived) && (
            <p>Add or enable a service in Manage services.</p>
          )}
        </div>
      )}
    </div>
  );
}
function AssignmentCard({
  service,
  catalog,
  availability,
  assignment,
  disabled,
  onApply,
}: {
  service: CatalogItem;
  catalog: TransportCatalog;
  availability?: TransportEligibility;
  assignment: ReturnType<typeof latestAssignment>;
  disabled: boolean;
  onApply: (service: CatalogItem, transport: CatalogItem) => Promise<void>;
}) {
  const current =
    assignment?.transport_id ??
    (assignment &&
      catalog.transports.find(
        (t) => t.id === assignment.transport || t.name === assignment.transport
      )?.id) ??
    '';
  const [draft, setDraft] = useState<{ base: string; value: string } | null>(
    null
  );
  const selected = draft?.base === current ? draft.value : current;
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const usable = (id: string) => {
    const key = catalogTransportKey(id);
    return !key || availability?.[key] !== false;
  };
  const choices = catalog.transports.filter(
    (t) => t.enabled && !t.archived && usable(t.id)
  );
  const previous = catalog.transports.find((t) => t.id === current);
  return (
    <article
      aria-label={service.name}
      className="min-w-0 space-y-3 rounded-xl border border-slate-600 p-4"
    >
      <h3 className="break-words text-lg font-semibold">{service.name}</h3>
      <p className="break-words">
        Current reported transport:{' '}
        <strong>{assignment?.transport ?? 'Not Reported'}</strong>
        {current && !usable(current) && ' (unavailable for this mission)'}
        {previous?.archived
          ? ' (archived)'
          : previous && !previous.enabled
            ? ' (disabled)'
            : ''}
      </p>
      <form
        className="flex min-w-0 items-end gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          const transport = choices.find((t) => t.id === selected);
          if (!transport || pending) return;
          setPending(true);
          setSaved(false);
          setError('');
          try {
            await onApply(service, transport);
            setDraft(null);
            setSaved(true);
          } catch (err) {
            setError(
              err instanceof Error
                ? err.message
                : 'Assignment could not be saved.'
            );
          } finally {
            setPending(false);
          }
        }}
      >
        <label className="min-w-0 flex-1">
          Transport
          <select
            className="ws-field w-full min-w-0"
            value={selected}
            disabled={pending || disabled}
            onChange={(e) => setDraft({ base: current, value: e.target.value })}
          >
            <option value="">Select transport</option>
            {current && !choices.some((t) => t.id === current) && (
              <option value={current} disabled>
                {assignment?.transport} (unavailable)
              </option>
            )}
            {choices.map((t) => (
              <option key={t.id} value={t.id}>
                {[
                  'Ka',
                  'Ka-band',
                  'Ka Band',
                  'KA',
                  'X',
                  'X-band',
                  'Starlink',
                  'Starshield',
                ].includes(t.name)
                  ? transportLabel(t.id)
                  : t.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="ws-button ws-primary shrink-0"
          disabled={
            disabled || pending || !choices.some((t) => t.id === selected)
          }
        >
          {pending ? 'Saving…' : 'Apply'}
        </button>
      </form>
      {saved && <p role="status">Assignment saved.</p>}
      {pending && <p role="status">Saving assignment…</p>}
      {error && (
        <p role="alert" className="break-words">
          {error}
        </p>
      )}
    </article>
  );
}
