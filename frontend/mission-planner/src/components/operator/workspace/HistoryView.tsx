import { useState } from 'react';
import type { ReadRecord, SavedRecord } from '@/types/operator';
import { JournalList } from '../JournalList';
import type { EditorMission } from './WorkspaceEditor';
export function HistoryView({
  items,
  incomplete,
  disabled,
  onEdit,
  onHistory,
  onTransition,
  mission,
  notesOnly = false,
}: {
  items: ReadRecord[];
  incomplete: boolean;
  disabled: boolean;
  onEdit: (record: SavedRecord) => void;
  onHistory: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
  mission?: EditorMission;
  notesOnly?: boolean;
}) {
  const [search, setSearch] = useState('');
  const [type, setType] = useState('');
  const [scope, setScope] = useState('');
  const eligible = items.filter(
    ({ record }) =>
      !notesOnly ||
      ['note', 'call_observation'].includes(record.payload.entry_type)
  );
  const filtered = eligible.filter(
    ({ record }) =>
      (!type || record.payload.entry_type === type) &&
      (!scope || record.scope === scope) &&
      [record.payload.title, record.payload.note].some((text) =>
        text.toLocaleLowerCase().includes(search.toLocaleLowerCase())
      )
  );
  return (
    <section aria-label={notesOnly ? 'Notes' : 'History'} className="space-y-3">
      <h2>{notesOnly ? 'Notes and observations' : 'History'}</h2>
      <p>
        Open a record’s history for immutable revisions, provenance and
        removals.
      </p>
      <div className="ws-draft-context">
        <label>
          Search loaded records
          <input
            className="ws-field"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label>
          Record type
          <select
            className="ws-field"
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            <option value="">All loaded types</option>
            {[
              ...new Set(
                eligible.map(({ record }) => record.payload.entry_type)
              ),
            ].map((type) => (
              <option key={type} value={type}>
                {type.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </label>
        <label>
          Scope filter
          <select
            className="ws-field"
            value={scope}
            onChange={(event) => setScope(event.target.value)}
          >
            <option value="">All scopes</option>
            {['mission', 'preflight', 'leg', 'between_legs', 'postflight'].map(
              (scope) => (
                <option key={scope} value={scope}>
                  {scope.replaceAll('_', ' ')}
                </option>
              )
            )}
          </select>
        </label>
      </div>
      <p className="ws-meta">
        Search covers loaded records only.
        {incomplete
          ? ' More pages or unavailable records may change these results.'
          : ''}
      </p>
      <JournalList
        items={filtered}
        disabled={disabled}
        onEdit={onEdit}
        onHistory={onHistory}
        onTransition={onTransition}
        context={mission}
      />
    </section>
  );
}
