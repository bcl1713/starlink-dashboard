# Overview Window Synchronization: Display Control Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for native execution, or `superpowers:subagent-driven-development` if
> delegation is selected. Track the checkbox steps below.

**Goal:** Expose acknowledged Recenter view and Fullscreen requests on
Configuration for an explicitly selected, already-open Overview window.

**Architecture:** A small validated protocol and session runtime own ephemeral
display discovery, presence, commands, and results. React hooks connect this
runtime to existing Overview camera/fullscreen behavior and a Configuration
card.

**Tech Stack:** BroadcastChannel, React, TypeScript, Vitest/jsdom, Playwright.

**Spec:** [Approved design](../specs/2026-10-04-overview-window-sync-design.md).
Read the [main plan](2026-10-04-overview-window-sync.md) for Global Constraints,
Review Focus, baseline, and execution requirements.

## Task 3: Deliver validated presence and targeted command sessions

**Files:**

- Create: `src/services/overview-display-protocol.ts`,
  `overview-display-session.ts`, and matching `.test.ts` files.

**Interfaces:**

Produce these protocol types and exported parser:

```ts
type DisplayAction = "recenter" | "fullscreen";
type DisplayResult =
  | "accepted"
  | "interaction-required"
  | "unsupported"
  | "expired"
  | "failed";
interface DisplayPeer {
  id: string;
  label: string;
  fullscreen: boolean;
  actions: DisplayAction[];
}
interface CommandFeedback {
  requestId: string;
  targetId: string;
  action: DisplayAction;
  status: "pending" | DisplayResult | "timeout" | "unavailable";
}
interface DisplaySnapshot {
  available: boolean;
  peers: DisplayPeer[];
  feedback: CommandFeedback | null;
}
```

Messages use common fields `v: 1`, `type`, `sender: string`,
`target: string | null`, and `seq: number`. Exact additional fields per type:

- `discover`: none; target null.
- `presence`: `label`, `fullscreen`, `actions`; target controller or null.
- `bye`: none; target null.
- `command`: target display, `requestId`, `action`, `expiresAtMs`.
- `result`: target controller, `requestId`, `action`, `status: DisplayResult`,
  `fullscreen: boolean`.

Export `OverviewDisplayMessage` as this discriminated union and
`parseOverviewDisplayMessage(value: unknown): OverviewDisplayMessage | null`.
Validate exact keys, nonempty IDs/labels of at most 128 characters, positive
safe-integer seq, finite nonnegative expiry, booleans, allowed results/actions,
and no duplicate capabilities. Reject inherited/malformed fields and unknown
versions/types; no arbitrary payload or remote executable data.

Produce
`createOverviewDisplaySession(options: DisplaySessionOptions): OverviewDisplaySession`.
Options have `role: 'display' | 'controller'`,
`onSnapshot(snapshot: DisplaySnapshot): void`; display options additionally have
`readPeer(): Omit<DisplayPeer, 'id' | 'label'>` and
`onCommand(action: DisplayAction, expiresAtMs: number): Promise<DisplayResult>`.

Session exports readonly `id`/`label`,
`request(targetId: string, action: DisplayAction): string | null`,
`publishPresence(): void`, and `close(): void`. Only controllers request. Use
channel name `starlink-overview-display-v1`, a UUID session ID, and matching
human-visible label consisting of `Overview`, a space, and the ID's final six
characters.

- [x] **Step 1: Write failing parser and in-memory two-session tests.** Mock
      BroadcastChannel with separate instances and ordered delivery. Test names
      and fixed assertions include:

  ```ts
  // 'recenter reaches exactly the selected display'
  expect(selectedRecenter).toHaveBeenCalledTimes(1);
  expect(otherRecenter).not.toHaveBeenCalled();
  // 'duplicate request does not execute again'
  expect(selectedRecenter).toHaveBeenCalledTimes(1);
  // 'late delivered command is expired'
  expect(expiredResult.status).toBe("expired");
  // 'missing result times out after three seconds'
  await vi.advanceTimersByTimeAsync(3000);
  expect(snapshot.feedback?.status).toBe("timeout");
  // 'missing heartbeat expires peer after fifteen seconds'
  await vi.advanceTimersByTimeAsync(15000);
  expect(snapshot.peers).toEqual([]);
  ```

  Include discover after an existing display starts, five-second heartbeats,
  bye/close, decreasing presence seq, duplicate result, old result after newer
  request, result from a different peer, malformed/oversized/unknown messages,
  expired capability, constructor/postMessage failure, and idempotent cleanup.

- [x] **Step 2: Run the new service tests and observe missing-module failures.**
      Run
      `npm run test:unit -- src/services/overview-display-protocol.test.ts src/services/overview-display-session.test.ts`.
- [x] **Step 3: Implement parser and session state machine.** Keep one session
      scheduler at 1000ms for expiry and five-second heartbeat emission. Emit
      discovery immediately for controllers and presence immediately for hosts.
      Use receive time for peer expiry; use command expiry for execution. A host
      accepts only commands targeting its own ID before deadline and remembers
      up to 128 `(sender, requestId)` pairs in FIFO order. Duplicate commands
      may replay a cached result, never execute again. No message loops or cache
      data. Ignore results not matching the current request/target/action.
      Ignore regressive peer seq values. Close clears
      intervals/listeners/pending state. Missing BroadcastChannel or transport
      failure sets available false rather than breaking Overview or throwing
      into the app.
- [x] **Step 4: Verify parser and lifecycle tests pass.** Add discovery with
      multiple controllers and no duplicate broadcasts; assert cleanup returns
      fake-channel listeners and timer counts to baseline.
- [x] **Step 5: Commit the protocol deliverable.** Commit
      `feat(overview): add targeted display command sessions`.

## Task 4: Deliver Configuration controls and honest fullscreen feedback

**Files:**

- Create: `src/hooks/useOverviewDisplayHost.ts`,
  `useOverviewDisplayController.ts`, and `.test.tsx` files.
- Create: `src/pages/overview-fullscreen.ts`, `.test.ts`,
  `OverviewDisplaySettingsCard.tsx`, `.test.tsx`.
- Modify: `src/pages/OverviewFullscreenControl.tsx`, its test,
  `OverviewPage.tsx`, `OverviewPage.css`, `ConfigurationPage.tsx`, its test.
- Create: `tests/e2e/overview-window-controls.spec.ts`.

**Interfaces:**

- Consume Task 3's session/protocol. Host calls existing `onReset`, observes
  `useDocumentFullscreen`, and publishes on fullscreenchange and heartbeat.
- Produce `requestOverviewFullscreen(): Promise<DisplayResult>` in
  `overview-fullscreen.ts`. Already-fullscreen resolves accepted; missing API
  resolves unsupported; rejection resolves interaction-required; fulfillment is
  accepted only if target document.fullscreenElement is actually the root.
- Produce `useOverviewDisplayHost(onRecenter: () => void): DisplayHostState`,
  exporting DisplayHostState fields `label: string | null` and
  `fullscreenFeedback: DisplayResult | null`. Its callback reads the latest
  onRecenter and expiresAtMs; never use a stale camera closure.
- Produce `useOverviewDisplayController(): DisplayControllerState`, exporting
  DisplayControllerState extending DisplaySnapshot with
  `send(targetId: string, action: DisplayAction): string | null`.
- Produce `OverviewDisplaySettingsCard(): React.JSX.Element` in Configuration.
  Host's label is visible alongside Overview's existing fullscreen/map controls
  and matches the selector's accessible name. Do not expose internal UUIDs.
- Extend `OverviewFullscreenControl` with optional
  `feedback?: DisplayResult | null`. Local clicks call the same helper directly
  within the trusted click handler; an async preparatory operation cannot
  consume activation. Provide accessible feedback for unsupported/rejected
  entry.

- [ ] **Step 1: Add failing hook/helper/card tests and a two-page control
      suite.** Pin these expectations:

  ```ts
  // 'no displays offers a separate Overview window'
  expect(screen.getByRole("button", { name: "Open Overview" })).toBeEnabled();
  // 'multiple displays require selection'
  expect(screen.getByRole("button", { name: "Recenter view" })).toBeDisabled();
  // 'recenter uses the target existing reset callback'
  expect(onReset).toHaveBeenCalledTimes(1);
  // 'fullscreen rejection gives a local-click fallback'
  expect(await requestOverviewFullscreen()).toBe("interaction-required");
  // 'closing the selected display never selects another silently'
  expect(send).not.toHaveBeenCalledWith(otherId, "recenter");
  ```

  Also cover single peer auto-selection, multi-peer explicit choice, peer loss,
  no/failed channel, blocked popup, pending/timeout feedback, real
  fullscreenchange and Escape, accepted callback vs settled camera animation,
  and StrictMode cleanup. Browser tests change camera manually, command Recenter
  from Configuration, assert target camera resets without navigation, and retain
  native fullscreen.

- [ ] **Step 2: Observe failures before UI integration.** Run the new hook,
      helper, card, and browser suites:

  ```sh
  npm run test:unit -- \
    src/hooks/useOverviewDisplayHost.test.tsx \
    src/hooks/useOverviewDisplayController.test.tsx \
    src/pages/overview-fullscreen.test.ts \
    src/pages/OverviewDisplaySettingsCard.test.tsx
  npx playwright test tests/e2e/overview-window-controls.spec.ts --workers=1
  ```

- [ ] **Step 3: Implement host/controller hooks and card.**
      Subscribe/unsubscribe within effects. Select the only peer automatically
      only when no prior selected target was lost; peer loss leaves explicit
      selection required. Put the card adjacent to Overview camera settings.
      Open Overview with `window.open('/overview', '_blank', 'noopener')`
      directly on click, retain Configuration, and infer popup success from
      display discovery rather than treating a null noopener handle as certain
      failure. After three seconds without a new peer, offer popup-blocking
      guidance. Feedback uses role status or alert; controls have keyboard
      access and visible focus.
- [ ] **Step 4: Implement shared fullscreen helper and Overview integration.**
      Configuration sends Fullscreen to the host; host checks expiry then calls
      the helper and publishes actual state. Provide exact actionable fallback:
      `Click Fullscreen in the Overview window to finish.` Recenter invokes the
      existing onReset. No camera remount, focus forcing, navigation, or control
      of Configuration's fullscreen. Already-fullscreen target displays its
      active state; local Escape publishes its exited state.
- [ ] **Step 5: Verify ordinary/fullscreen controls and lifecycle.** Run
      affected unit suites, Configuration/fullscreen tests, and the controls
      browser suite. Assert controller stays foreground during the remote
      request; test real browser rejection and successful local-click fallback
      without permissions bypasses. Test a native request already in flight when
      the three-second deadline elapses: no new invocation/replay or late
      success feedback, while actual fullscreenchange events remain
      authoritative. Browser fullscreen requests have no abort API; do not
      falsely claim timeout cancelled one.
- [ ] **Step 6: Commit the working control deliverable.** Commit
      `feat(configuration): control selected Overview displays`.
