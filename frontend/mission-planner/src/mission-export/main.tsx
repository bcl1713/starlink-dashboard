import { Component, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { MissionExportScene } from './scene';
import { frameMissionRoute } from './framing';
import { validateMapInput } from './protocol';

document.addEventListener(
  'webglcontextlost',
  () => {
    window.missionMap.state = {
      ...window.missionMap.state,
      status: 'error',
      error: 'WebGL context lost',
    };
  },
  true
);
const root = createRoot(document.getElementById('root')!);
class SceneBoundary extends Component<
  { children: ReactNode },
  { error: string | null }
> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error: error.message };
  }
  componentDidCatch(error: Error) {
    if (window.missionMap.state.status !== 'error')
      window.missionMap.state = {
        status: 'error',
        error: `Scene/texture error: ${error.message}`,
      };
  }
  render() {
    return this.state.error ? null : this.props.children;
  }
}
window.missionMap = {
  state: { status: 'loading' },
  plan: (raw, viewport) =>
    frameMissionRoute(validateMapInput(raw), viewport).map(({ id }) => ({
      id,
    })),
  render: (raw, viewIndex, digest, viewport) => {
    window.missionMap.state = { status: 'loading', digest };
    try {
      const input = validateMapInput(raw);
      const views = frameMissionRoute(input, viewport);
      const view = views[viewIndex];
      if (!view) throw new Error('Missing required view');
      root.render(
        <SceneBoundary key={`${digest}/${viewIndex}`}>
          <MissionExportScene input={input} view={view} digest={digest} />
        </SceneBoundary>
      );
    } catch (error) {
      window.missionMap.state = {
        status: 'error',
        error: String(error),
        digest,
      };
    }
  },
};
