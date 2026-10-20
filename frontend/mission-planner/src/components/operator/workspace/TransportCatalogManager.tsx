import { useState } from 'react';
import { createClientId } from '@/lib/clientId';
import type {
  CatalogItem,
  TransportCatalog,
} from '@/services/transportCatalog';

export function TransportCatalogManager({
  catalog,
  kind,
  saving,
  onSave,
  onClose,
}: {
  catalog: TransportCatalog;
  kind: 'services' | 'transports';
  saving: boolean;
  onSave: (catalog: TransportCatalog) => Promise<boolean>;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  async function save(items: CatalogItem[]) {
    if (
      items.some((i) => !i.name.trim()) ||
      new Set(items.map((i) => i.name.trim().toLocaleLowerCase())).size !==
        items.length
    ) {
      setError('Use a unique, nonempty name.');
      return;
    }
    setError('');
    await onSave({ ...catalog, [kind]: items });
  }
  return (
    <section
      aria-label={`Manage ${kind}`}
      className="space-y-3 rounded-xl border border-slate-600 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3>Manage {kind}</h3>
        <button className="ws-button" onClick={onClose}>
          Done
        </button>
      </div>
      <p className="ws-meta">
        Shared across missions. Archived entries remain in history.
      </p>
      <form
        className="flex min-w-0 flex-wrap gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          const next = name.trim();
          if (!next) return;
          if (await onSaveUnique(next)) setName('');
        }}
      >
        <label className="min-w-0 flex-1">
          New {kind === 'services' ? 'service' : 'transport'}
          <input
            maxLength={200}
            className="ws-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <button
          className="ws-button self-end"
          disabled={saving || !name.trim()}
        >
          Add
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {catalog[kind].map((item) => (
        <CatalogRow
          key={item.id}
          item={item}
          saving={saving}
          onSave={(updated) =>
            save(catalog[kind].map((i) => (i.id === item.id ? updated : i)))
          }
        />
      ))}
    </section>
  );
  async function onSaveUnique(next: string) {
    if (
      catalog[kind].some(
        (i) => i.name.toLocaleLowerCase() === next.toLocaleLowerCase()
      )
    ) {
      setError('That name already exists, including archived entries.');
      return false;
    }
    setError('');
    return onSave({
      ...catalog,
      [kind]: [
        ...catalog[kind],
        { id: createClientId(), name: next, enabled: true, archived: false },
      ],
    });
  }
}
function CatalogRow({
  item,
  saving,
  onSave,
}: {
  item: CatalogItem;
  saving: boolean;
  onSave: (item: CatalogItem) => Promise<void>;
}) {
  const [name, setName] = useState(item.name);
  return (
    <div className="rounded border border-slate-600 p-3 space-y-2">
      <form
        className="flex min-w-0 flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void onSave({ ...item, name: name.trim() });
        }}
      >
        <label className="min-w-0 flex-1">
          Name
          <input
            className="ws-field"
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <button
          className="ws-button self-end"
          disabled={saving || name.trim() === item.name || !name.trim()}
        >
          Rename
        </button>
      </form>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex min-h-11 items-center gap-2">
          <input
            type="checkbox"
            checked={item.enabled}
            disabled={saving || item.archived}
            onChange={(e) =>
              void onSave({ ...item, enabled: e.target.checked })
            }
          />
          Enabled
        </label>
        <span>
          {item.archived ? 'Archived' : item.enabled ? 'Available' : 'Disabled'}
        </span>
        <button
          className="ws-button"
          disabled={saving}
          onClick={() => void onSave({ ...item, archived: !item.archived })}
        >
          {item.archived ? 'Restore' : 'Archive'}
        </button>
      </div>
    </div>
  );
}
