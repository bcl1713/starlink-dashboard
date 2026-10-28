import { UtcDateTime } from './UtcDateTime';
import type {
  ReportTime,
  TransportServiceRow as Row,
  TransportValue,
} from '@/types/operatorTransport';
import { emptyReportTime, replaceApplication } from './transportForms';
import { issueButton, issueField } from './issueForms';

export function TransportReportTime({
  label,
  time,
  onChange,
}: {
  label: string;
  time: ReportTime;
  onChange: (t: ReportTime) => void;
}) {
  return (
    <div className="grid min-w-0 gap-2 sm:grid-cols-2">
      <UtcDateTime
        label={label}
        value={time.at}
        onChange={(value) => {
          const at = value ? new Date(value).toISOString() : null;
          onChange({
            at,
            precision: at
              ? time.precision === 'unknown'
                ? 'exact'
                : time.precision
              : 'unknown',
          });
        }}
      />
      <label>
        {label} precision
        <select
          aria-label={`${label} precision`}
          className={issueField}
          value={time.precision}
          onChange={(e) =>
            onChange({
              at: e.target.value === 'unknown' ? null : time.at,
              precision: e.target.value as ReportTime['precision'],
            })
          }
        >
          <option value="unknown">Unknown</option>
          <option value="exact">Exact</option>
          <option value="approximate">Approximate</option>
        </select>
      </label>
    </div>
  );
}
const transports = ['unknown', 'Starshield', 'Ka', 'X'] as const;
export function TransportServiceRow({
  row,
  index,
  onChange,
  onCheck,
  onRemove,
}: {
  row: Row;
  index: number;
  onChange: (row: Row) => void;
  onCheck: (row: Row) => void;
  onRemove: () => void;
}) {
  const n = index + 1;
  function transport(
    label: string,
    value: TransportValue,
    change: (v: TransportValue) => void
  ) {
    return (
      <label>
        {label}
        <select
          aria-label={label}
          className={issueField}
          value={value}
          onChange={(e) => change(e.target.value as TransportValue)}
        >
          {[...new Set([...transports, value])].map((t) => (
            <option key={t} value={t}>
              {t === 'X' ? 'X-band' : t === 'unknown' ? 'Unknown' : t}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <fieldset className="min-w-0 space-y-3 rounded-lg border p-3">
      <legend>Service {n}</legend>
      <label>
        Service {n}
        <input
          className={issueField}
          maxLength={200}
          placeholder="Secure voice, VTC, IPTV…"
          value={row.service}
          onChange={(e) => onChange({ ...row, service: e.target.value })}
        />
      </label>
      <div className="grid min-w-0 gap-4 sm:grid-cols-2">
        <div>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              checked={!!row.applied}
              onChange={(e) =>
                onChange(
                  replaceApplication(
                    row,
                    e.target.checked
                      ? { transport: 'unknown', time: emptyReportTime() }
                      : null
                  )
                )
              }
            />
            Reported Applied {n}
          </label>
          {row.applied && (
            <div className="space-y-2">
              {transport(`Applied transport ${n}`, row.applied.transport, (v) =>
                onChange(
                  replaceApplication(row, {
                    ...row.applied!,
                    transport: v,
                    transport_id: null,
                  })
                )
              )}
              <TransportReportTime
                label={`Applied time ${n}`}
                time={row.applied.time}
                onChange={(time) =>
                  onChange(replaceApplication(row, { ...row.applied!, time }))
                }
              />
            </div>
          )}
        </div>
        <div>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              checked={!!row.requested}
              onChange={(e) =>
                onChange({
                  ...row,
                  requested: e.target.checked
                    ? { transport: 'unknown', time: emptyReportTime() }
                    : null,
                })
              }
            />
            Requested {n}
          </label>
          {row.requested && (
            <div className="space-y-2">
              {transport(
                `Requested transport ${n}`,
                row.requested.transport,
                (v) =>
                  onChange({
                    ...row,
                    requested: {
                      ...row.requested!,
                      transport: v,
                      transport_id: null,
                    },
                  })
              )}
              <TransportReportTime
                label={`Requested time ${n}`}
                time={row.requested.time}
                onChange={(time) =>
                  onChange({ ...row, requested: { ...row.requested!, time } })
                }
              />
            </div>
          )}
        </div>
        <div>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              checked={!!row.intended}
              onChange={(e) =>
                onChange({
                  ...row,
                  intended: e.target.checked ? { transport: 'unknown' } : null,
                })
              }
            />
            Intended {n}
          </label>
          {row.intended &&
            transport(`Intended transport ${n}`, row.intended.transport, (v) =>
              onChange({ ...row, intended: { transport: v } })
            )}
        </div>
        <div>
          <label className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              checked={!!row.checked}
              onChange={(e) =>
                onCheck({
                  ...row,
                  checked: e.target.checked
                    ? { result: 'unknown', time: emptyReportTime(), note: '' }
                    : null,
                })
              }
            />
            Operator Checked {n}
          </label>
          {row.checked && (
            <div className="space-y-2">
              <p className="text-sm">
                Operator-reported check; actual routing unknown.
              </p>
              <label>
                Check result {n}
                <select
                  aria-label={`Check result ${n}`}
                  className={issueField}
                  value={row.checked.result}
                  onChange={(e) =>
                    onCheck({
                      ...row,
                      checked: {
                        ...row.checked!,
                        result: e.target.value as NonNullable<
                          Row['checked']
                        >['result'],
                      },
                    })
                  }
                >
                  <option value="unknown">Unknown</option>
                  <option value="satisfactory">Satisfactory</option>
                  <option value="issue_reported">Issue reported</option>
                </select>
              </label>
              <TransportReportTime
                label={`Checked time ${n}`}
                time={row.checked.time}
                onChange={(time) =>
                  onCheck({ ...row, checked: { ...row.checked!, time } })
                }
              />
              <label>
                Check note {n}
                <textarea
                  className={issueField}
                  maxLength={8000}
                  value={row.checked.note}
                  onChange={(e) =>
                    onCheck({
                      ...row,
                      checked: { ...row.checked!, note: e.target.value },
                    })
                  }
                />
              </label>
            </div>
          )}
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Changing Reported Applied clears the prior check. Earlier reports remain
        in history.
      </p>
      <button type="button" className={issueButton} onClick={onRemove}>
        Remove service {n}
      </button>
    </fieldset>
  );
}
