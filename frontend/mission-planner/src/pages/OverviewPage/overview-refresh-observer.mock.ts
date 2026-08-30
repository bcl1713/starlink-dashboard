import { vi } from 'vitest';

import type {
  OverviewRefreshReason,
  UseOverviewRefreshOptions,
} from './useOverviewRefresh';

const overviewRefreshObserver = vi.hoisted(() => ({
  enabled: false,
  scheduled: [] as Promise<void>[],
  manual: [] as Promise<void>[],
  reset() {
    this.enabled = false;
    this.scheduled = [];
    this.manual = [];
  },
}));

export function getOverviewRefreshObserver() {
  return overviewRefreshObserver;
}

vi.mock('./useOverviewRefresh', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./useOverviewRefresh')>();
  return {
    ...actual,
    useOverviewRefresh(options: UseOverviewRefreshOptions) {
      const observedOptions: UseOverviewRefreshOptions = {
        ...options,
        onRefresh(reason: OverviewRefreshReason) {
          const promise = options.onRefresh(reason);
          if (overviewRefreshObserver.enabled) {
            if (reason === 'scheduled') {
              overviewRefreshObserver.scheduled.push(promise);
            } else {
              overviewRefreshObserver.manual.push(promise);
            }
          }
          return promise;
        },
      };
      return actual.useOverviewRefresh(observedOptions);
    },
  };
});
