import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { useOverviewFullscreen } from './OverviewGrid';

type Deferred = {
  readonly promise: Promise<void>;
  readonly resolve: () => void;
  readonly reject: (error?: unknown) => void;
};

function deferred(): Deferred {
  let resolve = () => {};
  let reject: (error?: unknown) => void = () => {};
  const promise = new Promise<void>((ok, fail) => {
    resolve = ok;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function setFullscreenElement(value: Element | null) {
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    value,
  });
}

function Harness(props: {
  readonly request?: () => Promise<void>;
  readonly renderTrigger?: boolean;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const controller = useOverviewFullscreen(rootRef, triggerRef);
  return (
    <>
      {props.renderTrigger === false ? null : (
        <button ref={triggerRef} type="button">
          Saved trigger
        </button>
      )}
      <div
        ref={(node) => {
          rootRef.current = node;
          if (node && props.request) node.requestFullscreen = props.request;
        }}
        tabIndex={-1}
      >
        <h1 id="overview-title" tabIndex={-1}>
          Operations Overview
        </h1>
        <input aria-label="Operator note" defaultValue="stable" />
        <output aria-label="fullscreen mode">{controller.mode}</output>
        <output aria-label="fallback message">
          {controller.fallbackMessage ?? ''}
        </output>
        <output aria-label="enter pending">
          {controller.enterPending ? 'pending' : 'idle'}
        </output>
        <button onClick={() => void controller.enterFromUserGesture()}>
          Enter
        </button>
        <button onClick={() => void controller.exitFromUserGesture()}>
          Exit
        </button>
      </div>
    </>
  );
}

function root() {
  return screen.getByText('Operations Overview')
    .parentElement as HTMLDivElement;
}

describe('useOverviewFullscreen', () => {
  it('does not call the fullscreen API on mount', () => {
    const request = vi.fn(() => Promise.resolve());
    render(<Harness request={request} />);
    expect(request).not.toHaveBeenCalled();
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
  });

  it('enters native mode only when fullscreenchange targets the owned root', () => {
    const request = vi.fn(() => new Promise<void>(() => {}));
    render(<Harness request={request} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
    setFullscreenElement(root());
    fireEvent(document, new Event('fullscreenchange'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'native'
    );
    expect(root()).toHaveFocus();
  });

  it('exits native ownership and restores trigger focus', () => {
    const exitFullscreen = vi.fn(() => Promise.resolve());
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    render(<Harness request={() => Promise.resolve()} />);
    setFullscreenElement(root());
    fireEvent(document, new Event('fullscreenchange'));
    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
    setFullscreenElement(null);
    fireEvent(document, new Event('fullscreenchange'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
    expect(screen.getByRole('button', { name: 'Saved trigger' })).toHaveFocus();
  });

  it('uses kiosk view when requestFullscreen is missing', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
    expect(document.documentElement).toHaveClass('overview-kiosk-active');
  });

  it('handles a rejected request exactly once', async () => {
    const request = vi.fn(() => Promise.reject(new Error('blocked')));
    render(<Harness request={request} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    await screen.findByText('kiosk');
    expect(request).toHaveBeenCalledTimes(1);
    fireEvent(document, new Event('fullscreenerror'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
  });

  it('dedupes error plus rejection and lets the later attempt receive error', async () => {
    const first = deferred();
    const second = deferred();
    const request = vi
      .fn<() => Promise<void>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    render(<Harness request={request} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent(document, new Event('fullscreenerror'));
    first.reject(new Error('first'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent(document, new Event('fullscreenerror'));
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
  });

  it('double rapid enter => one request/one active', () => {
    const first = deferred();
    const request = vi.fn<() => Promise<void>>().mockReturnValue(first.promise);
    render(<Harness request={request} />);

    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('enter pending')).toHaveTextContent('pending');
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
  });

  it('active error=>one kiosk', () => {
    const first = deferred();
    const request = vi.fn<() => Promise<void>>().mockReturnValue(first.promise);
    render(<Harness request={request} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent(document, new Event('fullscreenerror'));

    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
    expect(screen.getByLabelText('enter pending')).toHaveTextContent('idle');
    fireEvent(document, new Event('fullscreenerror'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
  });

  it('exit/new attempt receives error', () => {
    const first = deferred();
    const second = deferred();
    const request = vi
      .fn<() => Promise<void>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    render(<Harness request={request} />);

    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent(document, new Event('fullscreenerror'));
    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent(document, new Event('fullscreenerror'));

    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
  });

  it('native success then late reject neutral', async () => {
    const first = deferred();
    const request = vi.fn<() => Promise<void>>().mockReturnValue(first.promise);
    render(<Harness request={request} />);

    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    setFullscreenElement(root());
    fireEvent(document, new Event('fullscreenchange'));
    first.reject(new Error('late'));
    await Promise.resolve();

    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'native'
    );
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
  });

  it('exits kiosk view with Escape', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
  });

  it('exits native mode on owned Escape fullscreenchange', () => {
    render(<Harness request={() => Promise.resolve()} />);
    setFullscreenElement(root());
    fireEvent(document, new Event('fullscreenchange'));
    setFullscreenElement(null);
    fireEvent(document, new Event('fullscreenchange'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
  });

  it('ignores inactive errors and non-owner fullscreen changes', () => {
    render(<Harness request={() => new Promise<void>(() => {})} />);
    fireEvent(document, new Event('fullscreenerror'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
    setFullscreenElement(document.createElement('section'));
    fireEvent(document, new Event('fullscreenchange'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
  });

  it('unmount', async () => {
    const first = deferred();
    const request = vi.fn<() => Promise<void>>().mockReturnValue(first.promise);
    const rendered = render(<Harness request={request} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    expect(screen.getByLabelText('Operator note')).toHaveValue('stable');
    rendered.unmount();
    first.reject(new Error('late'));
    await waitFor(() =>
      expect(document.documentElement).not.toHaveClass('overview-kiosk-active')
    );
  });
});
