import { useState } from 'react';
import type { TrainingIdentity } from './trainingProgress';
import {
  decodeArchiveObservation,
  type ArchiveObservation,
} from './trainingArchiveEvidence';

type Zip = ArchiveObservation['zip'];
export function TrainingArchiveFiles({
  identity,
  checking,
  retained,
  onCheck,
}: {
  identity: TrainingIdentity;
  checking: boolean;
  retained: readonly ArchiveObservation[];
  onCheck: (values: ArchiveObservation[]) => Promise<void>;
}) {
  const [zip, setZip] = useState<Zip | null>(null);
  const [reports, setReports] = useState<unknown[]>([]);
  const [reading, setReading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [reportNames, setReportNames] = useState<string[]>([]);
  async function readZip(file: File | undefined) {
    setError(null);
    setZip(null);
    if (!file) return;
    setReading((n) => n + 1);
    try {
      if (file.size <= 0 || file.size > 64 * 1024 * 1024)
        throw new Error('Select the original private ZIP, up to 64 MiB.');
      if (!globalThis.crypto?.subtle)
        throw new Error(
          'This browser cannot compute the ZIP digest here. Use the private HTTPS or loopback origin.'
        );
      const bytes = await file.arrayBuffer(),
        header = new Uint8Array(bytes);
      if (
        header[0] !== 0x50 ||
        header[1] !== 0x4b ||
        header[2] !== 3 ||
        header[3] !== 4
      )
        throw new Error('Select the original Missions ZIP.');
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const sha256 = Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, '0')
      ).join('');
      setZip({ name: file.name, size: file.size, sha256 });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Could not read the original ZIP.'
      );
    } finally {
      setReading((n) => n - 1);
    }
  }
  async function readReports(files: FileList | null) {
    setError(null);
    setReports([]);
    setReportNames([]);
    if (!files?.length) return;
    setReading((n) => n + 1);
    try {
      if (files.length > 2)
        throw new Error(
          'Select the empty and nonempty import reports, up to two files.'
        );
      const values = [];
      for (const file of Array.from(files)) {
        if (file.size > 4 * 1024 * 1024)
          throw new Error('A private evidence report must be at most 4 MiB.');
        const report: unknown = JSON.parse(await file.text());
        // Structural/context validation now; actual artifact/history checks happen
        // only in the parent's explicit fresh backend evidence check.
        decodeArchiveObservation(
          {
            report,
            zip: {
              name: 'not-yet-selected.zip',
              size: 1,
              sha256: '0'.repeat(64),
            },
          },
          identity
        );
        values.push(report);
      }
      setReports(values);
      setReportNames(Array.from(files, (file) => file.name));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Could not read private evidence reports.'
      );
    } finally {
      setReading((n) => n - 1);
    }
  }
  async function checkSelected() {
    if (!zip || !reports.length || reading || checking) return;
    setError(null);
    try {
      await onCheck(
        reports.map((report) =>
          decodeArchiveObservation({ report, zip }, identity)
        )
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Could not check selected archive evidence.'
      );
    }
  }
  return (
    <fieldset
      className="min-w-0 space-y-3 rounded border p-3 [overflow-wrap:anywhere]"
      disabled={checking || reading > 0}
    >
      <legend>Original archive evidence</legend>
      <p>
        Use the private archive baseline/check commands in this procedure, then
        select the unchanged Missions download and the generated empty/nonempty
        import reports. Files stay in this browser; checking compares the
        reported source revisions with fresh backend history.
      </p>
      <label className="block">
        Original Missions ZIP
        <input
          className="ws-field min-w-0 max-w-full"
          type="file"
          accept=".zip,application/zip"
          onChange={(event) => void readZip(event.target.files?.[0])}
        />
      </label>
      <label className="block">
        Private archive evidence JSON
        <input
          className="ws-field min-w-0 max-w-full"
          type="file"
          accept=".json,application/json"
          multiple
          onChange={(event) => void readReports(event.target.files)}
        />
      </label>
      {zip && (
        <p>
          Selected ZIP: {zip.name} · {zip.size} bytes.
        </p>
      )}
      {reportNames.length > 0 && (
        <p>Selected reports: {reportNames.join(', ')}.</p>
      )}
      {retained.length > 0 && (
        <p>
          Retained tooling observations:{' '}
          {retained.map((item) => item.report.label).join(', ')} ·{' '}
          {retained[0].zip.name}. Check current evidence to revalidate them
          after reload.
        </p>
      )}
      <button
        className="ws-button"
        disabled={!zip || !reports.length || reading > 0 || checking}
        onClick={() => void checkSelected()}
      >
        Check selected archive evidence
      </button>
      {error && <p role="alert">{error}</p>}
      <p>
        These facts do not establish human PDF review or a client-visible
        network failure. Record those observations separately after performing
        them.
      </p>
    </fieldset>
  );
}
