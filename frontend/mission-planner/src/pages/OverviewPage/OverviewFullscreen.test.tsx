import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { useOverviewFullscreen } from './OverviewGrid';

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
        <button
          type="button"
          onClick={() => void controller.enterFromUserGesture()}
        >
          Enter
        </button>
        <button
          type="button"
          onClick={() => void controller.exitFromUserGesture()}
        >
          Exit
        </button>
      </div>
    </>
  );
}

describe('useOverviewFullscreen', () => {
  it('enters native mode only after fullscreenchange targets the owned root', async () => {
    let resolveRequest = () => {};
    const request = vi.fn(
      () => new Promise<void>((resolve) => (resolveRequest = resolve))
    );
    render(<Harness request={request} />);

    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );

    setFullscreenElement(screen.getByText('Operations Overview').parentElement);
    fireEvent(document, new Event('fullscreenchange'));
    resolveRequest();
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'native'
    );
    expect(screen.getByLabelText('Operator note')).toHaveValue('stable');
  });

  it('exits native ownership through document exit and restores trigger focus', () => {
    const exitFullscreen = vi.fn(() => Promise.resolve());
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    render(<Harness request={() => Promise.resolve()} />);
    setFullscreenElement(screen.getByText('Operations Overview').parentElement);
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

  it('falls back to kiosk on missing request support or rejection', async () => {
    const first = render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
    expect(screen.getByLabelText('fallback message')).toHaveTextContent(
      'Fullscreen unavailable — using kiosk view.'
    );
    expect(document.documentElement).toHaveClass('overview-kiosk-active');

    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
    first.unmount();

    render(<Harness request={() => Promise.reject(new Error('blocked'))} />);
    fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
    return waitFor(() => {
      expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
        'kiosk'
      );
    });
  });

  it('handles fullscreenerror, kiosk Escape, missing trigger, and cleanup', () => {
    const { unmount } = render(
      <Harness
        request={() => new Promise<void>(() => {})}
        renderTrigger={false}
      />
    );

    fireEvent(document, new Event('fullscreenerror'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent('kiosk');
    expect(document.documentElement).toHaveClass('overview-kiosk-active');

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
    expect(screen.getByText('Operations Overview')).toHaveFocus();

    unmount();
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
  });
});
