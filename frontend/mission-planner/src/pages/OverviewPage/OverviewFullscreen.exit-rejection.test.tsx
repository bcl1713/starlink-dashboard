import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useRef, useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { useOverviewFullscreen } from './OverviewGrid';

type Deferred = {
  readonly promise: Promise<void>;
  readonly reject: (error?: unknown) => void;
};

function deferred(): Deferred {
  let reject: (error?: unknown) => void = () => {};
  const promise = new Promise<void>((_, fail) => {
    reject = fail;
  });
  return { promise, reject };
}

function setFullscreenElement(value: Element | null) {
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    value,
  });
}

function Harness({ observeExit = false }: { readonly observeExit?: boolean }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const controller = useOverviewFullscreen(rootRef, triggerRef);
  const [exitResult, setExitResult] = useState('');
  return (
    <>
      <button ref={triggerRef} type="button">
        Saved trigger
      </button>
      <div ref={rootRef} tabIndex={-1}>
        <h1 id="overview-title" tabIndex={-1}>
          Operations Overview
        </h1>
        <output aria-label="fullscreen mode">{controller.mode}</output>
        <output aria-label="exit result">{exitResult}</output>
        <button
          onClick={() => {
            const promise = controller.exitFromUserGesture();
            if (observeExit) {
              void promise.then(
                () => setExitResult('resolved'),
                () => setExitResult('rejected')
              );
              return;
            }
            void promise;
          }}
        >
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

describe('useOverviewFullscreen native exit rejection', () => {
  it('consumes a rejected native exit and waits for fullscreenchange authority', async () => {
    const exitFullscreen = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(new Error('exit blocked'))
      .mockResolvedValueOnce(undefined);
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    const focus = vi.spyOn(HTMLButtonElement.prototype, 'focus');
    render(<Harness observeExit />);
    setFullscreenElement(root());
    fireEvent(document, new Event('fullscreenchange'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'native'
    );

    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    await waitFor(() => expect(exitFullscreen).toHaveBeenCalledTimes(1));
    await screen.findByText('resolved');
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'native'
    );
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
    expect(root()).toHaveFocus();
    expect(focus).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    await waitFor(() => expect(exitFullscreen).toHaveBeenCalledTimes(2));
    setFullscreenElement(null);
    fireEvent(document, new Event('fullscreenchange'));
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
    expect(screen.getByRole('button', { name: 'Saved trigger' })).toHaveFocus();
    expect(focus).toHaveBeenCalledTimes(1);
  });

  it('leaves other-owner rejected native exits neutral', () => {
    const exitFullscreen = vi
      .fn<() => Promise<void>>()
      .mockRejectedValue(new Error('exit blocked'));
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    render(<Harness />);
    setFullscreenElement(document.createElement('section'));
    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    expect(exitFullscreen).not.toHaveBeenCalled();
    expect(screen.getByLabelText('fullscreen mode')).toHaveTextContent(
      'inline'
    );
  });

  it('does not update state after an unmounted rejected native exit', async () => {
    const exit = deferred();
    const exitFullscreen = vi
      .fn<() => Promise<void>>()
      .mockReturnValue(exit.promise);
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    const rendered = render(<Harness />);
    setFullscreenElement(root());
    fireEvent(document, new Event('fullscreenchange'));
    fireEvent.click(screen.getByRole('button', { name: 'Exit' }));
    expect(exitFullscreen).toHaveBeenCalledTimes(1);
    rendered.unmount();
    exit.reject(new Error('exit blocked'));
    await Promise.resolve();
    expect(document.documentElement).not.toHaveClass('overview-kiosk-active');
  });
});
