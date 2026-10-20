/** @vitest-environment jsdom */
import { webcrypto, createHash } from 'node:crypto';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { TrainingArchiveFiles } from './TrainingArchiveFiles';
import {
  identity,
  namespace,
  records,
  observation,
} from '@/test/training-archive-fixtures';
import { collectArchiveEvidence } from './trainingArchiveEvidence';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function file(name: string, body: string) {
  const value = new File([body], name);
  Object.defineProperties(value, {
    text: { value: async () => body },
    arrayBuffer: { value: async () => new TextEncoder().encode(body).buffer },
  });
  return value;
}
it('hashes actual selected bytes and forwards distinct report files without marking human outcomes', async () => {
  vi.stubGlobal('crypto', webcrypto);
  const payload = 'PK\u0003\u0004fictional original bytes';
  const digest = createHash('sha256').update(payload).digest('hex');
  const facts = ['empty', 'nonempty'].map((label) => {
    const item = observation(label as 'empty' | 'nonempty');
    item.report.inspection.zipSha256 = digest;
    item.report.preparations[1].artifact = {
      sha256: digest,
      size: payload.length,
    };
    return file(`${label}.json`, JSON.stringify(item.report));
  });
  const check = vi.fn(async (values) => {
    expect(
      collectArchiveEvidence(identity, namespace, 2, records, values)
    ).toContain('archive-imported-isolated');
  });
  render(
    <TrainingArchiveFiles
      identity={identity}
      checking={false}
      retained={[]}
      onCheck={check}
    />
  );
  fireEvent.change(screen.getByLabelText('Original Missions ZIP'), {
    target: { files: [file('original.zip', payload)] },
  });
  fireEvent.change(screen.getByLabelText('Private archive evidence JSON'), {
    target: { files: facts },
  });
  const button = screen.getByRole('button', {
    name: 'Check selected archive evidence',
  });
  await waitFor(() =>
    expect((button as HTMLButtonElement).disabled).toBe(false)
  );
  fireEvent.click(button);
  await waitFor(() => expect(check).toHaveBeenCalledTimes(1));
  expect(check.mock.calls[0][0][0].zip.sha256).toBe(digest);
  expect(screen.queryByText('Passed')).toBeNull();
});
it('rejects foreign tool reports and unavailable hashing without dispatching evidence', async () => {
  const check = vi.fn();
  const report = structuredClone(observation('empty').report);
  report.identity.epoch = 'foreign';
  render(
    <TrainingArchiveFiles
      identity={identity}
      checking={false}
      retained={[]}
      onCheck={check}
    />
  );
  fireEvent.change(screen.getByLabelText('Private archive evidence JSON'), {
    target: { files: [file('foreign.json', JSON.stringify(report))] },
  });
  await waitFor(() =>
    expect(screen.getByRole('alert').textContent).toContain(
      'another private source'
    )
  );
  vi.stubGlobal('crypto', {});
  fireEvent.change(screen.getByLabelText('Original Missions ZIP'), {
    target: { files: [file('original.zip', 'PK\u0003\u0004data')] },
  });
  await waitFor(() =>
    expect(screen.getByRole('alert').textContent).toContain('compute')
  );
  expect(check).not.toHaveBeenCalled();
});
