/** @vitest-environment jsdom */
import React from "react";
import { renderHook, waitFor, cleanup } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import axios from "axios";
import apiClient from "@app/services/api-client";
import { overviewHistoryApi } from "@app/services/overview-history";
import { useOverviewHistory } from "@app/hooks/api/useOverviewHistory";
import { diagnostic } from "../../browser-probe";
const original = apiClient.defaults.adapter;
const h = () => ({
  window_seconds: 30,
  start_timestamp_seconds: 0,
  end_timestamp_seconds: 30,
  step_seconds: 1,
  series: { m: [[30, 3]] },
});
afterEach(() => {
  cleanup();
  apiClient.defaults.adapter = original;
  vi.restoreAllMocks();
});
it("real Axios keeps the signal/path/payload and only adds the diagnostic header", async () => {
  const controller = new AbortController(),
    data = h();
  let config: any;
  apiClient.defaults.adapter = async (c) => {
    config = c;
    return { config: c, data, status: 200, statusText: "OK", headers: {} };
  };
  expect(
    await overviewHistoryApi.get(controller.signal, "synthetic-test/p/r1"),
  ).toBe(data);
  expect(config.signal).toBe(controller.signal);
  expect(config.url).toBe("/api/overview-history");
  expect(config.data).toBeUndefined();
  expect(config.headers.get("x-diagnostic-id")).toBe("synthetic-test/p/r1");
  expect(diagnostic!.association(data)).toBe("synthetic-test/p/r1");
});
it("real service propagates cancellation and post-interceptor error once", async () => {
  const controller = new AbortController();
  let reject!: (e: any) => void;
  apiClient.defaults.adapter = () => new Promise((_, r) => (reject = r));
  const request = overviewHistoryApi.get(controller.signal, "cancel");
  await Promise.resolve();
  controller.abort();
  reject(new axios.CanceledError("cancel"));
  await expect(request).rejects.toBeInstanceOf(axios.CanceledError);
  const log = vi.spyOn(console, "error").mockImplementation(() => {});
  let calls = 0;
  apiClient.defaults.adapter = async () => {
    calls++;
    throw Error("offline failure");
  };
  await expect(overviewHistoryApi.get(undefined, "error")).rejects.toThrow(
    "offline failure",
  );
  expect(calls).toBe(1);
  expect(log).toHaveBeenCalledTimes(1);
});
it("actual Query structural sharing preserves old object identity without attributing it to a fresh response", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: 0 } },
  });
  const responses: any[] = [];
  apiClient.defaults.adapter = async (c) => {
    const data = h();
    responses.push(data);
    return { config: c, data, status: 200, statusText: "OK", headers: {} };
  };
  const view = renderHook(() => useOverviewHistory(), {
    wrapper: ({ children }: any) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
  await waitFor(() => expect(view.result.current.isSuccess).toBe(true));
  const first = view.result.current.data;
  const firstRequest = diagnostic!.association(first);
  await view.result.current.refetch();
  expect(responses).toHaveLength(2);
  expect(responses[1]).not.toBe(responses[0]);
  expect(view.result.current.data).toBe(first);
  expect(diagnostic!.association(first)).toBe(firstRequest);
  expect(diagnostic!.association(responses[1])).not.toBe(firstRequest);
  const options = client.getQueryCache().getAll()[0].options as any;
  expect(options.retry).toBe(false);
  expect(options.refetchInterval({ state: { status: "success" } })).toBe(1000);
  expect(options.refetchInterval({ state: { status: "error" } })).toBe(5000);
  expect(options.refetchIntervalInBackground).toBe(true);
  expect(options.refetchOnWindowFocus).toBe("always");
  view.unmount();
  client.clear();
});
