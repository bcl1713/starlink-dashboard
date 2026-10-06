// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, it, vi } from 'vitest';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { useRef, useState } from 'react';
import { AviationDetails } from './AviationDetails';
import { emptyAviationView, type AviationView } from './aviation-controller';
import {
  inspectionReports,
  type AviationSelection,
} from './aviation-inspection';
import { collection, NOW, station } from './fixtures';
import { parseAviationFeatures } from '@/services/aviation-features';
import { OverviewAdsbDetails } from '../adsb/OverviewAdsbDetails';
import { projectAdsbContacts } from '../adsb/overview-adsb-state';
import { ADSB_NOW, adsbContact, adsbSettings } from '@/test/adsb-fixtures';
afterEach(cleanup);
const first = station(),
  second = station();
first.id = 'first';
first.properties.station_id = 'KJFK';
first.properties.raw_text = 'KJFK original observation';
second.id = 'second';
second.properties.station_id = 'KLGA';
second.properties.wind_speed_mps = 12;
second.properties.raw_text = 'KLGA original observation';
const view: AviationView = {
  ...emptyAviationView,
  now: NOW + 123,
  layers: {
    ...emptyAviationView.layers,
    metar: {
      state: 'stale',
      data: parseAviationFeatures(
        {
          ...collection([first, second]),
          retrieved_at_ms: NOW + 123,
          feed_completeness: 'partial',
          omitted_features: 4,
        },
        'metar'
      ),
    },
  },
};
function Harness({
  current = view,
  aircraft = false,
}: {
  current?: AviationView;
  aircraft?: boolean;
}) {
  const candidates = inspectionReports(current).map((r) => r.selection);
  const [selected, setSelected] = useState<AviationSelection | null>(
    aircraft ? null : (candidates[0] ?? null)
  );
  const [showAircraft, setShowAircraft] = useState(aircraft);
  const focus = useRef<HTMLButtonElement | null>(null);
  return (
    <>
      <button
        ref={focus}
        onClick={() => {
          setShowAircraft(false);
          setSelected(candidates[0]);
        }}
      >
        Open report
      </button>
      <OverviewAdsbDetails
        contact={
          showAircraft
            ? projectAdsbContacts([adsbContact()], adsbSettings(), ADSB_NOW)[0]
            : null
        }
        onClose={() => setShowAircraft(false)}
        returnFocusRef={focus}
        portalContainer={document.body}
      />
      <AviationDetails
        view={current}
        candidates={candidates}
        selection={selected}
        onSelectionChange={setSelected}
        onClose={() => setSelected(null)}
        returnFocusRef={focus}
        portalContainer={document.body}
      />
    </>
  );
}
it.each([false, true])(
  'keeps a new weather report open while the previous weather/aircraft popup finishes restoring focus (aircraft: %s)',
  async (aircraft) => {
    vi.useFakeTimers();
    try {
      render(<Harness aircraft={aircraft} />);
      fireEvent.click(
        screen.getByRole('button', {
          name: aircraft ? 'Close' : 'Close weather report',
        })
      );
      fireEvent.click(screen.getByRole('button', { name: 'Open report' }));
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      await act(async () => {
        vi.advanceTimersByTime(1);
      });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Close weather report' })
      ).toHaveFocus();
      fireEvent.click(
        screen.getByRole('button', { name: 'Close weather report' })
      );
      await act(async () => {
        vi.advanceTimersByTime(1);
      });
      expect(screen.getByRole('button', { name: 'Open report' })).toHaveFocus();
    } finally {
      cleanup();
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    }
  }
);
it('opens only the selected observation and lets overlapping reports be selected by keyboard', () => {
  render(<Harness />);
  const popup = screen.getByRole('dialog');
  expect(popup).toHaveTextContent('KJFK METAR observation');
  expect(popup).not.toHaveTextContent('KLGA original observation');
  expect(popup).toHaveTextContent('2026-10-06T12:00:00.123 UTC');
  expect(popup).toHaveTextContent('4 omitted');
  fireEvent.change(screen.getByLabelText('Weather report'), {
    target: { value: 'metar:second' },
  });
  expect(popup).toHaveTextContent('KLGA METAR observation');
  expect(popup).toHaveTextContent('12 m/s');
  expect(popup).not.toHaveTextContent('KJFK original observation');
  fireEvent.click(screen.getByRole('button', { name: 'Close weather report' }));
  expect(screen.queryByRole('dialog')).toBeNull();
});
it.each([
  { ...view, now: NOW + 3600000 },
  { ...view, layers: { ...view.layers, metar: { state: 'off' as const } } },
])('closes a selected report when it is no longer admitted', (unavailable) => {
  const { rerender } = render(<Harness />);
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  rerender(<Harness current={unavailable} />);
  expect(screen.queryByRole('dialog')).toBeNull();
  rerender(<Harness current={view} />);
  // A returning snapshot must not reopen the dismissed selection.
  expect(screen.queryByRole('dialog')).toBeNull();
});
