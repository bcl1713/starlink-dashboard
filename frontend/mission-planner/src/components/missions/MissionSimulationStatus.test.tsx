/** @vitest-environment jsdom */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { completedStatus, runningStatus } from '@/test/simulation-run-fixtures';
import { useSimulationRun } from '@/hooks/api/useSimulationRun';
import { MissionSimulationStatus } from './MissionSimulationStatus';
vi.mock('@/hooks/api/useSimulationRun', () => ({ useSimulationRun: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
const legs = [{ id: 'leg-1', name: 'Training leg' }];
it.each(['running', 'completed', 'cancelled', 'failed'] as const)(
  'keeps confirmed %s status visible in both mission consumers',
  (state) => {
    const status = state === 'completed' ? completedStatus() : runningStatus();
    status.state = state;
    if (state !== 'running') status.run!.finished_at = status.served_at;
    if (state === 'failed')
      status.run!.error = {
        code: 'publication_failed',
        message: 'Collection failed',
      };
    vi.mocked(useSimulationRun).mockReturnValue({
      data: status,
      isError: false,
    } as never);
    render(
      <>
        <MissionSimulationStatus missionId="mission-1" legs={legs} />
        <MissionSimulationStatus missionId="mission-1" legs={legs} />
      </>
    );
    expect(screen.getAllByLabelText('Simulation run')).toHaveLength(2);
    expect(screen.getAllByText('Leg: Training leg')).toHaveLength(2);
    expect(screen.getAllByLabelText('Simulation run')[0]).toHaveTextContent(
      state[0].toUpperCase() + state.slice(1)
    );
  }
);
it('retains confirmed running status and warns on failed refresh', () => {
  vi.mocked(useSimulationRun).mockReturnValue({
    data: runningStatus(),
    isError: true,
  } as never);
  render(<MissionSimulationStatus missionId="mission-1" legs={legs} />);
  expect(screen.getByLabelText('Simulation run')).toHaveTextContent(
    'Refresh unavailable'
  );
});
it('does not attribute another mission run to this mission', () => {
  vi.mocked(useSimulationRun).mockReturnValue({
    data: runningStatus(),
    isError: false,
  } as never);
  render(<MissionSimulationStatus missionId="mission-2" legs={legs} />);
  expect(screen.queryByLabelText('Simulation run')).toBeNull();
});
