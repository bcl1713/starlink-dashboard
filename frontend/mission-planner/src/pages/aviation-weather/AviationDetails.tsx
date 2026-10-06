import { useEffect, useMemo, type RefObject } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { AviationView } from './aviation-controller';
import { AviationReport } from './AviationReport';
import {
  aviationReportLabel,
  aviationSelectionKey,
  inspectionReports,
  type AviationSelection,
} from './aviation-inspection';
import './AviationWeather.css';

export function AviationDetails({
  view,
  candidates,
  selection,
  onSelectionChange,
  onClose,
  returnFocusRef,
  portalContainer,
}: {
  view: AviationView;
  candidates: readonly AviationSelection[];
  selection: AviationSelection | null;
  onSelectionChange: (selection: AviationSelection) => void;
  onClose: () => void;
  returnFocusRef: RefObject<HTMLElement | null>;
  portalContainer: HTMLElement | null;
}) {
  const reports = useMemo(
    () =>
      new Map(
        inspectionReports(view).map((r) => [
          aviationSelectionKey(r.selection),
          r,
        ])
      ),
    [view]
  );
  const selected = selection
    ? reports.get(aviationSelectionKey(selection))
    : undefined;
  const choices = candidates.flatMap((c) => {
    const report = reports.get(aviationSelectionKey(c));
    return report ? [report] : [];
  });
  useEffect(() => {
    if (selection && !selected) onClose();
  }, [selection, selected, onClose]);
  const item = selected ? view.layers[selected.selection.layer] : undefined;
  const data = item?.data;
  return (
    <Dialog.Root
      modal={false}
      open={!!selected}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal container={portalContainer}>
        <Dialog.Content
          className="aviation-details"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            (returnFocusRef.current?.isConnected
              ? returnFocusRef.current
              : portalContainer
            )?.focus();
          }}
        >
          <div className="aviation-details-header">
            <Dialog.Title>
              {selected
                ? aviationReportLabel(selected.feature)
                : 'Weather report'}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close weather report"
              className="aviation-details-close"
            >
              ×
            </Dialog.Close>
          </div>
          <Dialog.Description>
            Selected weather report · {item?.state}.{' '}
            {selected?.feature.geometry
              ? 'Its map feature is highlighted.'
              : 'No reported location; this advisory has no map shading.'}
          </Dialog.Description>
          {choices.length > 1 && (
            <label className="aviation-report-choice">
              Weather report
              <select
                aria-label="Weather report"
                value={selection ? aviationSelectionKey(selection) : ''}
                onChange={(event) => {
                  const choice = choices.find(
                    (r) =>
                      aviationSelectionKey(r.selection) === event.target.value
                  );
                  if (choice) onSelectionChange(choice.selection);
                }}
              >
                {choices.map((r) => (
                  <option
                    key={aviationSelectionKey(r.selection)}
                    value={aviationSelectionKey(r.selection)}
                  >
                    {aviationReportLabel(r.feature)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {selected && (
            <AviationReport feature={selected.feature} now={view.now} />
          )}
          {data && (
            <div className="aviation-report-source">
              <p>
                Source AWC · retrieved{' '}
                {new Date(data.retrieved_at_ms)
                  .toISOString()
                  .replace(/Z$/, ' UTC')}
              </p>
              <p>
                Coverage {data.feed_completeness} · {data.omitted_features}{' '}
                omitted · missing reports mean unknown weather
              </p>
              {item?.product?.attribution?.map((a) => (
                <a
                  key={a.url}
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {a.label}
                </a>
              ))}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
