import type { ReactNode } from 'react';
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
  showCaptureActions = true,
  selectedRecordId,
  renderAdvisory,
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
  showCaptureActions?: boolean;
  selectedRecordId?: string | null;
  renderAdvisory?: (call: SavedRecord) => ReactNode;
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
  const displayedConferences = (
    activeOnly ? activeConferences : conferences.filter((r) => !r.deleted)
  ).sort((a, b) => a.record_id.localeCompare(b.record_id));
  const calls = records.filter((r) => r.record_type === 'call');
  const selectedCall = calls.find((r) => r.record_id === selectedRecordId);
  const selectedBridgeId =
    selectedCall?.payload.entry_type === 'call'
      ? selectedCall.payload.conference_id
      : selectedRecordId;
  return (
    <section
      aria-label="Operations"
      className="space-y-4 [&_button]:min-h-11 [&_button]:min-w-11"
    >
      {showCaptureActions && (
        <>
          <h2>Operations</h2>
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
              Schedule
            </button>
            <button
              className="ws-button"
              disabled={disabled}
              onClick={onCreateActualCall}
            >
              Record Completed Call
            </button>
            <button
              className="ws-button"
              disabled={disabled}
              onClick={onCreateConference}
            >
              Create Conference
            </button>
            <button
              className="ws-button"
              disabled={disabled}
              onClick={() => onJoin()}
            >
              Report Customer Joined
            </button>
          </div>
        </>
      )}
      <div className="ws-operations-lanes">
        <section className="ws-conferences-lane" aria-label="Conferences">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2>Conferences</h2>
            {!showCaptureActions && (
              <button
                className="ws-button"
                disabled={disabled}
                onClick={onCreateConference}
              >
                Create Conference
              </button>
            )}
          </div>
          {incomplete && (
            <p role="status">
              Active communications show loaded records only; unread pages may
              contain more sessions.
            </p>
          )}
          {!activeOnly && !conferences.length && (
            <p>
              No conferences recorded. Create a bridge to report its
              configuration and use.
            </p>
          )}
          {displayedConferences.map((record) => (
            <div
              key={record.record_id}
              className="space-y-2"
              data-record-id={record.record_id}
              data-selected={record.record_id === selectedBridgeId}
            >
              <ConferenceCard
                prominentActions={activeConferences.includes(record)}
                calls={calls}
                incomplete={incomplete}
                selected={record.record_id === selectedBridgeId}
                advisory={
                  renderAdvisory &&
                  calls
                    .filter(
                      (call) =>
                        call.payload.entry_type === 'call' &&
                        call.payload.conference_id === record.record_id
                    )
                    .map((call) => (
                      <div key={call.record_id}>{renderAdvisory(call)}</div>
                    ))
                }
                compactActions
                sessionCurrent={isSessionCurrent(record)}
                currentAssociation={currentAssociation}
                activityAssociationLabel={
                  record.scope === 'leg'
                    ? mission?.legs.find((leg) => leg.id === record.leg_id)
                        ?.name
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
            </div>
          ))}
        </section>
        <section className="ws-calls-lane" aria-label="Calls">
          <h2>Calls</h2>
          <CallList
            activeOnly
            selectedRecordId={selectedRecordId}
            renderAdvisory={renderAdvisory}
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
        </section>
      </div>
      <details>
        <summary className="ws-button">
          Customer Intervals And Previous Activity
        </summary>
        {!showCaptureActions && (
          <button
            className="ws-button"
            disabled={disabled}
            onClick={() => onJoin()}
          >
            Report Customer Joined
          </button>
        )}
        <h3>
          {activeOnly ? 'Current Customer Intervals' : 'Customer Intervals'}
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
                ['connected', 'interrupted'].includes(
                  record.payload.state ?? ''
                ))
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
      </details>
    </section>
  );
}
