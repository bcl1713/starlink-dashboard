/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { popForecast } from '@/test/pop-fixtures';
import { PopTransitionMarkers } from './PopTransitionMarkers';
import { TimelinePreviewSection } from './TimelinePreviewSection';
import type { Timeline } from '@/services/timeline';
afterEach(cleanup);
const startUtc = '2035-03-01T23:50:00Z',
  endUtc = '2035-03-02T00:10:00Z';
it('clips outlined ten-minute markers without changing UTC evidence or adding row text', () => {
  const forecast = popForecast(),
    onSelect = vi.fn();
  const { rerender } = render(
    <PopTransitionMarkers
      forecast={forecast}
      startUtc={startUtc}
      endUtc={endUtc}
      onSelect={onSelect}
    />
  );
  const marker = screen.getByRole('button', {
    name: /Los Angeles.*Dallas.*UTC/,
  });
  expect(marker.textContent).toBe('');
  expect(marker.style.left).toBe('25%');
  expect(marker.style.width).toBe('50%');
  expect(marker.className).toContain('border-2');
  marker.focus();
  expect(document.activeElement).toBe(marker);
  fireEvent.click(marker);
  expect(onSelect).toHaveBeenCalledWith(forecast.transitions[0]);
  rerender(
    <PopTransitionMarkers
      forecast={forecast}
      startUtc="2035-03-02T00:00:00Z"
      endUtc={endUtc}
      onSelect={onSelect}
    />
  );
  expect(marker.style.left).toBe('0%');
  expect(marker.style.width).toBe('50%');
  expect(forecast.transitions[0].window_start_utc).toBe('2035-03-01T23:55:00Z');
});
it('handles absent, invalid and zero-duration bounds and keeps overlaps selectable', () => {
  const forecast = popForecast();
  forecast.transitions.push({
    ...forecast.transitions[0],
    crossing: { ...forecast.transitions[0].crossing, id: 'second' },
  });
  const { rerender } = render(
    <PopTransitionMarkers
      forecast={forecast}
      startUtc={startUtc}
      endUtc={endUtc}
      onSelect={vi.fn()}
    />
  );
  expect(screen.getAllByRole('button')).toHaveLength(2);
  expect(screen.getAllByRole('button')[0].style.top).not.toBe(
    screen.getAllByRole('button')[1].style.top
  );
  rerender(
    <PopTransitionMarkers
      forecast={forecast}
      startUtc={startUtc}
      endUtc={startUtc}
      onSelect={vi.fn()}
    />
  );
  expect(screen.queryByRole('button')).toBeNull();
  rerender(
    <PopTransitionMarkers
      startUtc="invalid"
      endUtc={endUtc}
      onSelect={vi.fn()}
    />
  );
  expect(screen.queryByRole('button')).toBeNull();
});
it.each(['available', 'unavailable'])(
  'preserves SOF, real outages and equal caution with Ka/X %s',
  (otherState) => {
    const timeline: Timeline = {
      mission_leg_id: 'one',
      created_at: startUtc,
      pop_forecast: popForecast(),
      segments: [
        {
          id: 'one',
          start_time: startUtc,
          end_time: endUtc,
          status: 'sof',
          reasons: ['SOF restriction'],
          ku_state: 'unavailable',
          ka_state: otherState,
          x_state: otherState,
        },
      ],
    };
    const original = structuredClone(timeline);
    const { container } = render(
      <TimelinePreviewSection timeline={timeline} isCalculating={false} />
    );
    expect(screen.getByText('SOF restriction')).not.toBeNull();
    expect(screen.getByText('Ku: UNAVAILABLE')).not.toBeNull();
    expect(screen.getByText('ADVISORY')).not.toBeNull();
    const marker = screen.getByRole('button', {
      name: /Los Angeles.*Dallas.*UTC/,
    });
    fireEvent.click(marker);
    expect(
      screen.getByText(/Estimated crossing.*2035-03-02 00:00:00/)
    ).not.toBeNull();
    expect(
      screen.getByText(/PoP transitions may briefly interrupt calls/)
    ).not.toBeNull();
    expect(container.querySelector('[data-pop-track]')?.textContent).toBe('');
    expect(timeline).toEqual(original);
  }
);
it('provides a full-width keyboard/mobile selector outside the track and resets selection on revision', () => {
  const forecast = popForecast();
  forecast.transitions.push({
    ...forecast.transitions[0],
    crossing: {
      ...forecast.transitions[0].crossing,
      id: 'second',
      to_city: 'Tokyo',
    },
    crossing_utc: '2035-03-02T00:01:00Z',
  });
  const timeline: Timeline = {
    mission_leg_id: 'one',
    created_at: startUtc,
    pop_forecast: forecast,
    segments: [
      {
        id: 'one',
        start_time: startUtc,
        end_time: endUtc,
        status: 'nominal',
        ku_state: 'available',
      },
    ],
  };
  const { container, rerender } = render(
    <TimelinePreviewSection timeline={timeline} isCalculating={false} />
  );
  const selector = screen.getByRole('combobox', {
    name: 'PoP transition details',
  });
  expect(selector.closest('[data-pop-track]')).toBeNull();
  selector.focus();
  expect(document.activeElement).toBe(selector);
  fireEvent.change(selector, { target: { value: 'second' } });
  expect(
    screen.getByText(/Estimated crossing UTC 2035-03-02 00:01:00/)
  ).not.toBeNull();
  expect(container.querySelector('[data-pop-track]')?.textContent).toBe('');
  rerender(
    <TimelinePreviewSection
      timeline={{ ...timeline, pop_forecast: popForecast('new-route') }}
      isCalculating={false}
    />
  );
  expect(
    screen.getByText(/Estimated crossing UTC 2035-03-02 00:00:00/)
  ).not.toBeNull();
});
it('leaves old missing forecast payloads safe and shows an explicit ID when catalog city is absent', () => {
  const forecast = popForecast();
  delete forecast.transitions[0].crossing.from_city;
  render(
    <PopTransitionMarkers
      forecast={forecast}
      startUtc={startUtc}
      endUtc={endUtc}
      onSelect={() => {}}
    />
  );
  expect(
    screen.getByRole('button', { name: /PoP los-angeles.*Dallas/ })
  ).not.toBeNull();
});
