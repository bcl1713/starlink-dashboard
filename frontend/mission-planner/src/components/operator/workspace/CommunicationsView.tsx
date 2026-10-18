import type { ReadRecord, SavedRecord } from '@/types/operator';
import { CallList } from '../CallList';
import { ConferenceCard } from '../ConferenceCard';
import { ParticipationRow } from '../ParticipationRow';
import type { ConferenceAction } from '../conferenceCommands';

export function CommunicationsView({
  items,
  disabled,
  incomplete,
  asOf,
  onCreateCall,
  onCreateActualCall,
  onCreateConference,
  onJoin,
  onEdit,
  onHistory,
  onTransition,
  onConferenceAction,
  onCustomerAction,
}: {
  items: ReadRecord[];
  disabled: boolean;
  incomplete: boolean;
  asOf?: string;
  onCreateCall: () => void;
  onCreateActualCall: () => void;
  onCreateConference: () => void;
  onJoin: (conference?: SavedRecord) => void;
  onEdit: (record: SavedRecord) => void;
  onHistory: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
  onConferenceAction: (record: SavedRecord, action: ConferenceAction) => void;
  onCustomerAction: (
    record: SavedRecord,
    action: 'left' | 'interrupted' | 'restore'
  ) => void;
}) {
  const records = items.map((item) => item.record);
  const conferences = records.filter(
    (record) => record.record_type === 'conference'
  );
  const customers = records.filter(
    (record) => record.record_type === 'participation'
  );
  return (
    <section
      aria-label="Communications"
      className="space-y-4 [&_button]:min-h-11 [&_button]:min-w-11"
    >
      <h2>Communications</h2>
      <p>
        Calls record customer requirements. Conferences record reusable bridges.
        Report each customer joining and leaving independently.
      </p>
      <p className="ws-meta">Reports do not control communications hardware.</p>
      <div className="flex flex-wrap gap-2">
        <button
          className="ws-button"
          disabled={disabled}
          onClick={onCreateCall}
        >
          Create call
        </button>
        <button
          className="ws-button"
          disabled={disabled}
          onClick={onCreateActualCall}
        >
          Record completed call
        </button>
        <button
          className="ws-button"
          disabled={disabled}
          onClick={onCreateConference}
        >
          Create conference
        </button>
        <button
          className="ws-button"
          disabled={disabled}
          onClick={() => onJoin()}
        >
          Report customer joined
        </button>
      </div>
      <CallList
        items={items}
        disabled={disabled}
        incomplete={incomplete}
        asOf={asOf}
        onEdit={onEdit}
        onHistory={onHistory}
        onTransition={onTransition}
      />
      <h3>Conferences</h3>
      {!conferences.length && (
        <p>
          No conferences recorded. Create a bridge to report its configuration
          and use.
        </p>
      )}
      {conferences.map((record) => (
        <div key={record.record_id} className="space-y-2">
          <ConferenceCard
            record={record}
            participations={customers}
            disabled={disabled}
            onAction={(action) => onConferenceAction(record, action)}
            onEdit={() => onEdit(record)}
            onJoin={() => onJoin(record)}
            onHistory={() => onHistory(record.record_id)}
            onRemove={() => onTransition(record)}
          />
          {!record.deleted && (
            <button
              className="ws-button"
              disabled={disabled}
              onClick={() => onJoin(record)}
            >
              Reuse conference
            </button>
          )}
        </div>
      ))}
      <h3>Customer intervals</h3>
      {!customers.length && (
        <p>
          No customer intervals recorded. A conference state alone does not
          report a connected customer.
        </p>
      )}
      {customers.map((record) => (
        <ParticipationRow
          key={record.record_id}
          record={record}
          conference={
            record.payload.entry_type === 'participation'
              ? conferences.find(
                  (conference) =>
                    conference.record_id ===
                    (record.payload.entry_type === 'participation'
                      ? record.payload.conference_id
                      : null)
                )
              : undefined
          }
          call={
            record.payload.entry_type === 'participation'
              ? records.find(
                  (call) =>
                    call.record_id ===
                    (record.payload.entry_type === 'participation'
                      ? record.payload.call_id
                      : null)
                )
              : undefined
          }
          disabled={disabled}
          onAction={(action) => onCustomerAction(record, action)}
          onEdit={() => onEdit(record)}
          onHistory={() => onHistory(record.record_id)}
          onRemove={() => onTransition(record)}
        />
      ))}
    </section>
  );
}
