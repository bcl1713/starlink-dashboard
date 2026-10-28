import type { RecordPage, SavedRecord } from '@/types/operator';
import { IssueFollowups } from '../IssueFollowups';
import { operatorUtc } from '../issueForms';
export type IssueStatus = 'open' | 'monitoring' | 'resolved' | 'reopened';
export function IssuesView({
  pages,
  incomplete,
  unavailable,
  disabled,
  onCreate,
  onCreateCapability,
  onEdit,
  onAction,
  onHistory,
  onActivity,
  onTransition,
}: {
  pages: RecordPage[];
  incomplete: boolean;
  unavailable: boolean;
  disabled: boolean;
  onCreate: () => void;
  onCreateCapability?: () => void;
  onEdit: (record: SavedRecord) => void;
  onAction: (record: SavedRecord, status: IssueStatus) => void;
  onHistory: (id: string) => void;
  onActivity: (id: string) => void;
  onTransition: (record: SavedRecord) => void;
}) {
  const issues = pages
    .flatMap((page) => page.items)
    .filter((item) => item.record.record_type === 'issue');
  function rows(group: typeof issues) {
    return group.map((item) => {
      const record = item.record;
      if (record.payload.entry_type !== 'issue') return null;
      const payload = record.payload;
      return (
        <article
          className="ws-record"
          key={record.record_id}
          aria-label={`Issue ${payload.title}`}
        >
          <h3>{payload.title}</h3>
          <p>
            {record.deleted ? 'Removed' : payload.status} · Priority{' '}
            {payload.priority ?? 'unspecified'} · Mitigation{' '}
            {payload.mitigation ?? 'unknown'}
          </p>
          <p>
            Follow-Up {item.follow_up?.state ?? 'unknown'} ·{' '}
            {operatorUtc(payload.follow_up_at)}
          </p>
          <p className="ws-meta">
            Operator reported · Recorded {operatorUtc(record.recorded_at)} ·{' '}
            {record.scope.replaceAll('_', ' ')}
          </p>
          <div className="flex flex-wrap gap-2">
            {!record.deleted && (
              <>
                <button
                  className="ws-button"
                  disabled={disabled}
                  onClick={() => onEdit(record)}
                >
                  Add Update / Follow Up
                </button>
                {payload.status === 'resolved' ? (
                  <button
                    className="ws-button"
                    disabled={disabled}
                    onClick={() => onAction(record, 'reopened')}
                  >
                    Reopen
                  </button>
                ) : (
                  <>
                    <button
                      className="ws-button"
                      disabled={disabled}
                      onClick={() =>
                        onAction(
                          record,
                          payload.status === 'monitoring'
                            ? 'open'
                            : 'monitoring'
                        )
                      }
                    >
                      {payload.status === 'monitoring'
                        ? 'Return To Open'
                        : 'Monitor'}
                    </button>
                    <button
                      className="ws-button"
                      disabled={disabled}
                      onClick={() => onAction(record, 'resolved')}
                    >
                      Resolve
                    </button>
                  </>
                )}
              </>
            )}
            <button
              className="ws-button"
              onClick={() => onActivity(record.record_id)}
            >
              Issue Activity
            </button>
            <button
              className="ws-button"
              onClick={() => onHistory(record.record_id)}
            >
              Audit History
            </button>
            <button
              className="ws-button"
              disabled={disabled}
              onClick={() => onTransition(record)}
            >
              {record.deleted ? 'Restore Issue Record' : 'Remove Issue Record'}
            </button>
          </div>
        </article>
      );
    });
  }
  return (
    <section aria-label="Issues" id="operator-issues">
      <h2>Issues</h2>
      <p>
        Exceptions, workarounds and check-ins. Follow-Ups reflect the current
        snapshot.
      </p>
      <button className="ws-button" disabled={disabled} onClick={onCreate}>
        New Issue
      </button>
      <IssueFollowups
        pages={pages}
        incomplete={incomplete}
        unavailable={unavailable}
      />
      {!issues.length && (
        <p>
          No issues recorded. Log a Problem from its description; add details
          when known.
        </p>
      )}
      {rows(
        issues.filter(
          (item) =>
            !item.record.deleted &&
            item.record.payload.entry_type === 'issue' &&
            item.record.payload.status !== 'resolved'
        )
      )}
      <details>
        <summary className="min-h-11">Resolved Issues</summary>
        {rows(
          issues.filter(
            (item) =>
              !item.record.deleted &&
              item.record.payload.entry_type === 'issue' &&
              item.record.payload.status === 'resolved'
          )
        )}
      </details>
      <details>
        <summary className="min-h-11">Removed Issue Records</summary>
        {rows(issues.filter((item) => item.record.deleted))}
      </details>
      <section aria-label="Manual Capabilities">
        <h2>Manual Capabilities</h2>
        <p>
          Functional Capability and backup availability are independent operator
          observations.
        </p>
        {onCreateCapability && (
          <button
            className="ws-button"
            disabled={disabled}
            onClick={onCreateCapability}
          >
            Record Manual Assessment
          </button>
        )}
        {pages
          .flatMap((page) => page.items)
          .map(
            ({ record }) =>
              record.payload.entry_type === 'capability_assessment' && (
                <article className="ws-record" key={record.record_id}>
                  <h3>
                    {record.payload.title}
                    {record.deleted ? ' · Removed' : ''}
                  </h3>
                  <p>
                    Functional: {record.payload.functional_status} · observed{' '}
                    {operatorUtc(record.payload.functional_observed_at)} ·{' '}
                    {record.payload.functional_time_precision}
                  </p>
                  <p>
                    Redundancy: {record.payload.redundancy_status} · observed{' '}
                    {operatorUtc(record.payload.redundancy_observed_at)} ·{' '}
                    {record.payload.redundancy_time_precision}
                  </p>
                  <p>{record.payload.note}</p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="ws-button"
                      disabled={disabled || record.deleted}
                      onClick={() => onEdit(record)}
                    >
                      Assess Capability
                    </button>
                    <button
                      className="ws-button"
                      onClick={() => onHistory(record.record_id)}
                    >
                      Assessment History
                    </button>
                    <button
                      className="ws-button"
                      disabled={disabled}
                      onClick={() => onTransition(record)}
                    >
                      {record.deleted
                        ? 'Restore Assessment Record'
                        : 'Remove Assessment Record'}
                    </button>
                  </div>
                </article>
              )
          )}
      </section>
    </section>
  );
}
