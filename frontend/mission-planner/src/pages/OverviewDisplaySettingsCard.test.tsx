/** @vitest-environment jsdom */
import '@testing-library/jest-dom/vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  createOverviewDisplaySession,
  type OverviewDisplaySession,
} from '@/services/overview-display-session';
import type {
  DisplayAction,
  DisplayResult,
} from '@/services/overview-display-protocol';
import { OverviewTestChannel as Channel } from '@/test/overview-display-channel';
import { OverviewDisplaySettingsCard } from './OverviewDisplaySettingsCard';

let hosts: OverviewDisplaySession[];
beforeEach(() => {
  vi.useFakeTimers();
  Channel.reset();
  hosts = [];
  vi.stubGlobal('BroadcastChannel', Channel);
});
afterEach(() => {
  cleanup();
  hosts.forEach((host) => host.close());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
function display(
  onCommand: (action: DisplayAction) => Promise<DisplayResult> = async () =>
    'accepted',
  actions: DisplayAction[] = ['recenter']
) {
  const session = createOverviewDisplaySession({
    role: 'display',
    onSnapshot: () => {},
    readPeer: () => ({ actions }),
    onCommand,
  });
  hosts.push(session);
  return session;
}
it('no displays offers a separate Overview window and waits for discovery despite a null noopener handle', async () => {
  const open = vi.spyOn(window, 'open').mockReturnValue(null);
  render(<OverviewDisplaySettingsCard />);
  expect(screen.getByRole('button', { name: 'Open Overview' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Open Overview' }));
  expect(open).toHaveBeenCalledWith('/overview', '_blank', 'noopener');
  expect(screen.getByRole('status')).toHaveTextContent('Waiting');
  await act(async () => {
    display();
    await Channel.flush();
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(screen.queryByText(/popup blocking/i)).toBeNull();
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeEnabled();
});
it('blocked popup gives guidance only after three seconds without a new display', async () => {
  vi.spyOn(window, 'open').mockReturnValue(null);
  render(<OverviewDisplaySettingsCard />);
  fireEvent.click(screen.getByRole('button', { name: 'Open Overview' }));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2999);
  });
  expect(screen.queryByRole('alert')).toBeNull();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(screen.getByRole('alert')).toHaveTextContent(/popup blocking/i);
});
it('an existing peer is not proof that a newly requested popup opened', async () => {
  display();
  vi.spyOn(window, 'open').mockReturnValue(null);
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  fireEvent.click(screen.getByRole('button', { name: 'Open Overview' }));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
    await Channel.flush();
  });
  expect(screen.getByRole('alert')).toHaveTextContent(/popup blocking/i);
});
it('single peer is selected and acknowledged recenter does not claim a settled animation', async () => {
  const selected = display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  expect(
    screen.getByRole('combobox', { name: 'Overview display' })
  ).toHaveValue(selected.id);
  fireEvent.click(screen.getByRole('button', { name: 'Recenter view' }));
  expect(screen.getByRole('status')).toHaveTextContent(/waiting/i);
  await act(Channel.flush);
  expect(screen.getByRole('status')).toHaveTextContent(/Recenter accepted/i);
});
it('multiple displays require selection, even if a single peer arrived first', async () => {
  display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  const other = display();
  await act(Channel.flush);
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
  fireEvent.change(screen.getByRole('combobox', { name: 'Overview display' }), {
    target: { value: other.id },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Recenter view' }));
  await act(Channel.flush);
  const commands = Channel.sent.filter((message) => message.type === 'command');
  expect(commands).toHaveLength(1);
  expect(commands[0].target).toBe(other.id);
});
it('closing the selected display never selects another silently', async () => {
  const selected = display(),
    other = display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  fireEvent.change(screen.getByRole('combobox', { name: 'Overview display' }), {
    target: { value: selected.id },
  });
  await act(async () => {
    selected.close();
    await Channel.flush();
  });
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
  expect(
    screen.getByRole('combobox', { name: 'Overview display' })
  ).toHaveValue('');
  expect(screen.getByText(/selected display disconnected/i)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Recenter view' }));
  expect(
    Channel.sent.filter(
      (message) => message.type === 'command' && message.target === other.id
    )
  ).toEqual([]);
  fireEvent.change(screen.getByRole('combobox', { name: 'Overview display' }), {
    target: { value: other.id },
  });
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeEnabled();
});
it('requires explicit choice after loss of the only peer and a replacement arrives', async () => {
  const selected = display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  await act(async () => {
    selected.close();
    await Channel.flush();
  });
  await act(async () => {
    display();
    await Channel.flush();
  });
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
});
it('missing or failed channel leaves Open Overview reachable and explains remote unavailability', async () => {
  vi.stubGlobal('BroadcastChannel', undefined);
  const view = render(<OverviewDisplaySettingsCard />);
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Open Overview' })).toBeEnabled();
  expect(screen.getByText(/remote controls unavailable/i)).toBeVisible();
  view.unmount();
  vi.stubGlobal('BroadcastChannel', Channel);
  display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  Channel.failPost = true;
  fireEvent.click(screen.getByRole('button', { name: 'Recenter view' }));
  expect(screen.getByText(/remote controls unavailable/i)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
});
it('pending commands time out with honest feedback and restore controls', async () => {
  display(() => new Promise(() => {}));
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  fireEvent.click(screen.getByRole('button', { name: 'Recenter view' }));
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
  await act(async () => {
    await Channel.flush();
    await vi.advanceTimersByTimeAsync(3000);
  });
  expect(screen.getByRole('status')).toHaveTextContent(/timed out/i);
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeEnabled();
});
it('keeps recenter available with no remote fullscreen control', async () => {
  display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: 'Fullscreen' })).toBeNull();
});
it('does not send recenter to a display without that capability', async () => {
  display(async () => 'accepted', []);
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeDisabled();
});
it('unmount clears the popup discovery timeout', () => {
  vi.spyOn(window, 'open').mockReturnValue(null);
  const view = render(<OverviewDisplaySettingsCard />);
  fireEvent.click(screen.getByRole('button', { name: 'Open Overview' }));
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it('discovers and recenters a legacy Overview window without exposing fullscreen', async () => {
  const host = display();
  render(<OverviewDisplaySettingsCard />);
  await act(Channel.flush);
  const channel = Channel.instances.find(
    (peer) => !peer.closed && peer !== Channel.instances[0]
  )!;
  act(() =>
    channel.deliver({
      v: 1,
      type: 'presence',
      sender: host.id,
      target: null,
      seq: 100,
      label: host.label,
      actions: ['recenter', 'fullscreen'],
      fullscreen: true,
    } as unknown as import('@/services/overview-display-protocol').OverviewDisplayMessage)
  );
  expect(screen.getByRole('button', { name: 'Recenter view' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: 'Fullscreen' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Recenter view' }));
  await act(Channel.flush);
  expect(screen.getByRole('status')).toHaveTextContent(/Recenter accepted/);
});
