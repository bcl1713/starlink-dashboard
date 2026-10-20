import type { ReadRecord, SavedRecord } from '@/types/operator';
import { CallList } from '../CallList';
import { ConferenceCard } from '../ConferenceCard';
import { ParticipationRow } from '../ParticipationRow';
import type { CallAction } from '../callCommands';
import {
  sessionOutsideContext,
  type ConferenceAction,
} from '../conferenceCommands';
import type { CallAssociation } from '../callAssociation';
import type { AssociationMission } from '../useMissionAssociation';

export function CommunicationsView({
  items,
  activeOnly = false,
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
  onCallAction,
  currentAssociation,
  mission,
  isSessionCurrent = () => true,
}: {
  isSessionCurrent?: (record: SavedRecord) => boolean;
  items: ReadRecord[];
  activeOnly?: boolean;
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
  currentAssociation?: CallAssociation | null;
  mission?: AssociationMission;
  onCallAction?: (record: SavedRecord, intent: CallAction) => void;
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
  const activeConferences = conferences.filter(
    (record) =>
      !record.deleted &&
      record.payload.entry_type === 'conference' &&
      ['preparing', 'established', 'interrupted'].includes(
        record.payload.status ?? ''
      ) &&
      isSessionCurrent(record) &&
      !sessionOutsideContext(record, currentAssociation)
  );
  const displayedConferences = activeOnly
    ? activeConferences
    : [
        ...activeConferences,
        ...conferences.filter((record) => !activeConferences.includes(record)),
      ];
  return (
    <section
      aria-label={activeOnly ? 'Active communications' : 'Communications'}
      className="space-y-4 [&_button]:min-h-11 [&_button]:min-w-11"
    >
      {!activeOnly && (
        <>
          <h2>Communications</h2>
          <p>
            Calls record customer requirements. Conferences record reusable
            bridges. Report each customer joining and leaving independently.
          </p>
          <p className="ws-meta">
            Reports do not control communications hardware.
          </p>
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
        </>
      )}
      <h2>Active Calls</h2>
      <CallList
        activeOnly
        items={items}
        disabled={disabled}
        incomplete={incomplete}
        asOf={asOf}
        onEdit={onEdit}
        onHistory={onHistory}
        onTransition={onTransition}
        onCallAction={onCallAction}
        onConferenceAction={onConferenceAction}
        currentAssociation={currentAssociation}
        isSessionCurrent={isSessionCurrent}
        onCustomerAction={onCustomerAction}
      />
      <h2>Active Bridges</h2>
      {!activeConferences.length && (
        <p>No current active bridge sessions reported.</p>
      )}
      {incomplete && (
        <p role="status">
          Active communications show loaded records only; unread pages may
          contain more sessions.
        </p>
      )}
      {!activeOnly && !conferences.length && (
        <p>
          No conferences recorded. Create a bridge to report its configuration
          and use.
        </p>
      )}
      {displayedConferences.map((record) => (
        <div key={record.record_id} className="space-y-2">
          {!activeOnly &&
            !activeConferences.includes(record) &&
            conferences.filter((r) => !activeConferences.includes(r))[0] ===
              record && (
              <h3>Reusable bridge definitions and previous sessions</h3>
            )}
          <ConferenceCard
            prominentActions={activeConferences.includes(record)}
            compactActions
            sessionCurrent={isSessionCurrent(record)}
            currentAssociation={currentAssociation}
            activityAssociationLabel={
              record.scope === 'leg'
                ? mission?.legs.find((leg) => leg.id === record.leg_id)?.name
                : undefined
            }
            record={record}
            participations={customers}
            disabled={disabled}
            onAction={(action) => onConferenceAction(record, action)}
            onEdit={() => onEdit(record)}
            onJoin={() => onJoin(record)}
            onHistory={() => onHistory(record.record_id)}
            onRemove={() => onTransition(record)}
          />
          {!record.deleted &&
            record.payload.entry_type === 'conference' &&
            record.payload.status === 'established' &&
            isSessionCurrent(record) &&
            !sessionOutsideContext(record, currentAssociation) && (
              <button
                className="ws-button"
                disabled={disabled}
                onClick={() => onJoin(record)}
              >
                Use this session for another customer
              </button>
            )}
        </div>
      ))}
      <h3>
        {activeOnly ? 'Current customer intervals' : 'Customer intervals'}
      </h3>
      {!customers.length && (
        <p>
          No customer intervals recorded. A conference state alone does not
          report a connected customer.
        </p>
      )}
      {customers
        .filter(
          (record) =>
            !activeOnly ||
            (!record.deleted &&
              isSessionCurrent(record) &&
              record.payload.entry_type === 'participation' &&
              ['connected', 'interrupted'].includes(record.payload.state ?? ''))
        )
        .map((record) => (
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
      {!activeOnly && (
        <CallList
          archivedOnly
          items={items}
          disabled={disabled}
          incomplete={false}
          asOf={asOf}
          onEdit={onEdit}
          onHistory={onHistory}
          onTransition={onTransition}
          onCallAction={onCallAction}
          onConferenceAction={onConferenceAction}
          currentAssociation={currentAssociation}
          isSessionCurrent={isSessionCurrent}
          onCustomerAction={onCustomerAction}
        />
      )}
    </section>
  );
}
