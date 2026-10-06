import { describe, expect, it } from 'vitest';
import type { StatusResponse } from '../services/status';
import {
  deriveOverviewLinkState,
  type OverviewLinkStateInput,
} from './overview-link-state';

function fixture(): OverviewLinkStateInput {
  return {
    settings: {
      starshield_link_enabled: true,
      x_band_link_enabled: true,
      orbital_traffic_enabled: false,
      aircraft_history_enabled: true,
      country_borders_enabled: false,
      state_borders_enabled: false,
    },
    status: {
      timestamp: '2026-10-03T12:00:00.000Z',
      position: { latitude: 30, longitude: -100, altitude: 35_000 },
      ground_entry_point: { latitude: 40, longitude: -75 },
      network: {
        throughput_up_mbps: 10,
        throughput_down_mbps: 100,
        latency_ms: 50,
        packet_loss_percent: 10,
      },
      metric_availability: {
        throughput_up_mbps: true,
        throughput_down_mbps: true,
        latency_ms: true,
        packet_loss_percent: true,
      },
    },
    nowMs: Date.parse('2026-10-03T12:00:04.000Z'),
    statusRequestFailed: false,
    hasTrafficGeometry: true,
    hasXBandGeometry: true,
    selectionState: 'normal',
    selectionRequestFailed: false,
  };
}

function assertActivity(
  input: OverviewLinkStateInput,
  starshield: boolean,
  xBand: boolean
) {
  const state = deriveOverviewLinkState(input);
  expect(state.starshieldFlow.forward.enabled).toBe(starshield);
  expect(state.starshieldFlow.reverse.enabled).toBe(starshield);
  expect(state.xBandFlow.forward.enabled).toBe(xBand);
  expect(state.xBandFlow.reverse.enabled).toBe(xBand);
  return state;
}

// Catch shared toggle gates, network-dependent GPS age, stale cached emission,
// selection errors affecting measured traffic, and fabricated availability.
describe('independent Overview link state', () => {
  it.each([
    [true, true],
    [true, false],
    [false, true],
    [false, false],
  ])(
    'respects confirmed settings Starshield=%s X-band=%s',
    (starshield, xBand) => {
      const input = fixture();
      input.settings = {
        starshield_link_enabled: starshield,
        x_band_link_enabled: xBand,
        orbital_traffic_enabled: false,
        aircraft_history_enabled: true,
        country_borders_enabled: false,
        state_borders_enabled: false,
      };
      const state = assertActivity(input, starshield, xBand);
      expect(state.starshieldVisible).toBe(starshield);
      expect(state.xBandVisible).toBe(xBand);
    }
  );

  it('hides both links until settings are confirmed', () => {
    const state = assertActivity(
      { ...fixture(), settings: undefined },
      false,
      false
    );
    expect(state.starshieldVisible).toBe(false);
    expect(state.xBandVisible).toBe(false);
  });

  it('omits only the Starshield arc when PoP geometry is unavailable', () => {
    const input = fixture();
    input.status!.ground_entry_point = null;
    input.hasTrafficGeometry = false;
    const state = assertActivity(input, false, true);
    expect(state.starshieldVisible).toBe(false);
    expect(state.xBandVisible).toBe(true);
  });

  it('omits only X-band when configured geometry is unavailable', () => {
    const state = assertActivity(
      { ...fixture(), hasXBandGeometry: false },
      true,
      false
    );
    expect(state.starshieldVisible).toBe(true);
    expect(state.xBandVisible).toBe(false);
  });

  it.each([
    [9_999, true],
    [10_000, false],
    [-5_000, true],
    [-5_001, false],
  ])(
    'uses original acquisition age %s ms for activity (%s)',
    (ageMs, active) => {
      const input = fixture();
      input.nowMs = Date.parse(input.status!.timestamp) + ageMs;
      const state = assertActivity(input, active, active);
      expect(state.starshieldVisible).toBe(active);
      expect(state.xBandVisible).toBe(true);
    }
  );

  it('stops both activities after status failure despite cached geometry/data', () => {
    const state = assertActivity(
      { ...fixture(), statusRequestFailed: true },
      false,
      false
    );
    expect(state.starshieldVisible).toBe(false);
    expect(state.xBandVisible).toBe(true);
  });

  it.each(['', 'invalid', undefined, null])(
    'fails closed for timestamp %s',
    (timestamp) => {
      const input = fixture();
      input.status!.timestamp = timestamp as never;
      expect(assertActivity(input, false, false).starshieldVisible).toBe(false);
    }
  );

  it.each([NaN, Infinity, -Infinity])(
    'fails closed for observation clock %s',
    (nowMs) => {
      expect(
        assertActivity({ ...fixture(), nowMs }, false, false).starshieldVisible
      ).toBe(false);
    }
  );

  it('has no current activity before any status exists', () => {
    const state = assertActivity(
      { ...fixture(), status: undefined },
      false,
      false
    );
    expect(state.starshieldVisible).toBe(false);
    expect(state.xBandVisible).toBe(true);
  });

  it.each([
    undefined,
    { latitude: NaN, longitude: 0, altitude: 0 },
    { latitude: 91, longitude: 0, altitude: 0 },
    { latitude: -91, longitude: 0, altitude: 0 },
    { latitude: 0, longitude: Infinity, altitude: 0 },
    { latitude: 0, longitude: 181, altitude: 0 },
    { latitude: 0, longitude: -181, altitude: 0 },
    { latitude: 0, longitude: 0 },
    { latitude: 0, longitude: 0, altitude: NaN },
    { latitude: 0, longitude: 0, altitude: Infinity },
  ] satisfies StatusResponse['position'][])(
    'rejects invalid aircraft %j independently of geometry flags',
    (position) => {
      const input = fixture();
      input.status!.position = position;
      const state = assertActivity(input, false, false);
      expect(state.starshieldVisible).toBe(false);
      expect(state.xBandVisible).toBe(true);
    }
  );

  it.each(['warning', null] as const)(
    'stops only X-band in selection state %s',
    (selectionState) => {
      const state = assertActivity(
        { ...fixture(), selectionState },
        true,
        false
      );
      expect(state.starshieldVisible).toBe(true);
      expect(state.xBandVisible).toBe(true);
      expect(state.starshieldFlow).toEqual(
        deriveOverviewLinkState(fixture()).starshieldFlow
      );
    }
  );

  it('stops only X-band after selection/catalog failure with a cached normal link', () => {
    const state = assertActivity(
      { ...fixture(), selectionRequestFailed: true },
      true,
      false
    );
    expect(state.xBandVisible).toBe(true);
    expect(state.starshieldFlow).toEqual(
      deriveOverviewLinkState(fixture()).starshieldFlow
    );
  });

  it.each(['missing network', 'missing flags', 'unavailable network'])(
    'keeps normal X-band active with %s',
    (gap) => {
      const input = fixture();
      if (gap === 'missing network') input.status!.network = undefined;
      if (gap === 'missing flags')
        input.status!.metric_availability = undefined;
      if (gap === 'unavailable network') input.status!.metric_availability = {};
      const state = assertActivity(input, false, true);
      expect(state.starshieldVisible).toBe(true);
      expect(state.xBandVisible).toBe(true);
    }
  );

  it.each(['throughput_up_mbps', 'throughput_down_mbps'] as const)(
    'gates only %s on explicit source availability',
    (field) => {
      for (const flag of [false, undefined, 1, 'true']) {
        const input = fixture();
        input.status!.metric_availability![field] = flag as never;
        const state = deriveOverviewLinkState(input);
        expect(state.starshieldFlow.forward.enabled).toBe(
          field !== 'throughput_up_mbps'
        );
        expect(state.starshieldFlow.reverse.enabled).toBe(
          field !== 'throughput_down_mbps'
        );
        expect(state.starshieldVisible).toBe(true);
        expect(state.xBandFlow.forward.enabled).toBe(true);
        expect(state.xBandFlow.reverse.enabled).toBe(true);
      }
    }
  );

  it.each(['throughput_up_mbps', 'throughput_down_mbps'] as const)(
    'gates only %s for unusable source values',
    (field) => {
      for (const value of [undefined, null, NaN, Infinity, -Infinity, -1, 0]) {
        const input = fixture();
        input.status!.network![field] = value;
        const state = deriveOverviewLinkState(input);
        expect(state.starshieldFlow.forward.enabled).toBe(
          field !== 'throughput_up_mbps'
        );
        expect(state.starshieldFlow.reverse.enabled).toBe(
          field !== 'throughput_down_mbps'
        );
        expect(state.starshieldVisible).toBe(true);
        expect(state.xBandFlow.forward.enabled).toBe(true);
      }
    }
  );

  it.each([false, undefined])(
    'omits unavailable latency/loss modulation with flag %s',
    (flag) => {
      const input = fixture();
      input.status!.metric_availability!.latency_ms = flag;
      input.status!.metric_availability!.packet_loss_percent = flag;
      const state = assertActivity(input, true, true);
      for (const emitter of [
        state.starshieldFlow.forward,
        state.starshieldFlow.reverse,
      ]) {
        expect(emitter).toMatchObject({ size: 9.5, brightness: 3.4 });
        expect(emitter.failure).toBeUndefined();
      }
    }
  );

  it('omits invalid latency/loss while valid throughput still animates', () => {
    const input = fixture();
    input.status!.network!.latency_ms = -1;
    input.status!.network!.packet_loss_percent = 101;
    const state = assertActivity(input, true, true);
    expect(state.starshieldFlow.forward).toMatchObject({
      size: 9.5,
      brightness: 3.4,
    });
    expect(state.starshieldFlow.forward.failure).toBeUndefined();
  });

  it('keeps measured modulation and synthetic activity separate without mutating inputs', () => {
    const input = fixture();
    const before = structuredClone(input);
    const state = assertActivity(input, true, true);
    expect(input).toEqual(before);
    expect(state.starshieldFlow.forward.failure?.probability).toBe(0.1);
    expect(state.starshieldFlow.reverse.rate).toBeGreaterThan(
      state.starshieldFlow.forward.rate
    );
    expect(state.xBandFlow.forward.failure).toBeUndefined();
    expect(state.xBandFlow.reverse.rate).toBeCloseTo(1.2945, 3);
    input.status!.network = {
      throughput_up_mbps: 500,
      throughput_down_mbps: 1,
      latency_ms: 0,
      packet_loss_percent: 100,
    };
    expect(deriveOverviewLinkState(input).xBandFlow).toEqual(state.xBandFlow);
  });
});
