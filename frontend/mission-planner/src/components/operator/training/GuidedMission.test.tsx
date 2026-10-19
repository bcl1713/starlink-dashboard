/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GuidedMission } from './GuidedMission';
const identity = {
  fixtureVersion: 1,
  origin: 'http://localhost:4567',
  storeId: 'private',
  epoch: 'one',
  missionId: 'fictional',
};
const evidence = { available: true, fresh: true, outcomes: [] };
afterEach(() => {
  cleanup();
  localStorage.clear();
});
it('offers real controls without treating Next or Skip as completion', () => {
  const open = vi.fn();
  render(
    <GuidedMission
      identity={identity}
      evidence={evidence}
      onOpenTarget={open}
      onDismiss={() => {}}
    />
  );
  expect(screen.getByText('Private training · Simulation')).toBeTruthy();
  expect(
    screen
      .getByRole('link', { name: 'Read this procedure' })
      .getAttribute('href')
  ).toBe('/operator-help/guide.html#context');
  expect(
    screen.getByRole('list', { name: 'Lesson outcome evidence' }).textContent
  ).toContain('private context read · Needs evidence');
  fireEvent.click(screen.getByRole('button', { name: 'Open lesson controls' }));
  expect(open).toHaveBeenCalledWith('T01');
  expect(screen.queryByRole('button', { name: 'Next lesson' })).toBeNull();
  fireEvent.click(
    screen.getByRole('button', { name: 'Resume guide instructions' })
  );
  fireEvent.click(screen.getByRole('button', { name: 'Next lesson' }));
  expect(screen.getByRole('heading', { name: /T02/ })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Back' }));
  expect(screen.getByText('Incomplete')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Skip lesson' }));
  fireEvent.click(screen.getByRole('button', { name: 'Back' }));
  expect(screen.getByText('Skipped')).toBeTruthy();
});
it('resumes navigation while preserving ordinary operator drafts and reset semantics', () => {
  localStorage.setItem('operator-drafts', 'retained');
  const { unmount } = render(
    <GuidedMission
      identity={identity}
      evidence={evidence}
      onOpenTarget={() => {}}
      onDismiss={() => {}}
    />
  );
  fireEvent.click(screen.getByRole('button', { name: 'Next lesson' }));
  unmount();
  render(
    <GuidedMission
      identity={identity}
      evidence={evidence}
      onOpenTarget={() => {}}
      onDismiss={() => {}}
    />
  );
  expect(screen.getByRole('heading', { name: /T02/ })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Reset guide progress' }));
  expect(screen.getByRole('heading', { name: /T01/ })).toBeTruthy();
  expect(localStorage.getItem('operator-drafts')).toBe('retained');
  expect(
    screen.getByText(/Reset mission stops the owned training instance/)
  ).toBeTruthy();
});
it('a changed store epoch starts separate progress and unavailable evidence is explicit', () => {
  const props = {
    identity,
    evidence,
    onOpenTarget: () => {},
    onDismiss: () => {},
  };
  const { rerender } = render(<GuidedMission {...props} />);
  fireEvent.click(screen.getByRole('button', { name: 'Next lesson' }));
  rerender(
    <GuidedMission
      {...props}
      identity={{ ...identity, epoch: 'two' }}
      evidence={{ ...evidence, available: false }}
    />
  );
  expect(screen.getByRole('heading', { name: /T01/ })).toBeTruthy();
  expect(screen.getByText('Evidence unavailable')).toBeTruthy();
});
it('reports a failed evidence check separately from progress storage and permits a real retry', async () => {
  const check = vi
    .fn()
    .mockRejectedValueOnce(new Error('History unavailable'))
    .mockResolvedValue(undefined);
  render(
    <GuidedMission
      identity={identity}
      evidence={evidence}
      onOpenTarget={() => {}}
      onDismiss={() => {}}
      onCheckEvidence={check}
    />
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Check current evidence' })
  );
  expect(
    await screen.findByText(/Evidence check failed: History unavailable/)
  ).toBeTruthy();
  expect(screen.getByText('Evidence unavailable')).toBeTruthy();
  expect(screen.queryByText(/Guide progress could not be saved/)).toBeNull();
  expect(check.mock.calls[0][1]).toBe('T01');
  fireEvent.click(
    screen.getByRole('button', { name: 'Check current evidence' })
  );
  expect(await screen.findByText('Incomplete')).toBeTruthy();
});

it('distinguishes imported archive tooling evidence from current reads and human observations', async () => {
  const props = {
    identity,
    evidence: {
      available: true,
      fresh: true,
      outcomes: ['export-downloaded'],
      toolingOutcomes: ['export-downloaded'],
    },
    onOpenTarget: () => {},
    onDismiss: () => {},
  };
  render(<GuidedMission {...props} />);
  fireEvent.change(screen.getByRole('combobox', { name: 'Lesson' }), {
    target: { value: 'T10' },
  });
  expect(
    screen.getByRole('list', { name: 'Lesson outcome evidence' }).textContent
  ).toContain('export downloaded · Verified from imported tooling evidence');
  expect(screen.getByText('Incomplete')).toBeTruthy();
});

it('retains an explicit offline browser read while leaving backend evidence unavailable', async () => {
  const read = {
    identity,
    namespace: 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e',
    observedAt: 1,
    journalH: 0,
    online: false,
    drafts: [],
  };
  const check = vi
    .fn()
    .mockResolvedValueOnce({
      clientObservations: [read],
      unavailableReason:
        'Offline: retain the draft and reconnect before checking backend evidence.',
    })
    .mockResolvedValue(undefined);
  render(
    <GuidedMission
      identity={identity}
      evidence={evidence}
      onOpenTarget={() => {}}
      onDismiss={() => {}}
      onCheckEvidence={check}
    />
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Check current evidence' })
  );
  expect((await screen.findByRole('alert')).textContent).toContain(
    'Offline: retain the draft'
  );
  expect(screen.getByText('Evidence unavailable')).toBeTruthy();
  fireEvent.click(
    screen.getByRole('button', { name: 'Check current evidence' })
  );
  await screen.findByText('Incomplete');
  expect(check.mock.calls[1][0].clientObservations).toEqual([read]);
});
