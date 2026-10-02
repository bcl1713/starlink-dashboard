import { buildSync } from 'esbuild';
import type { Page } from '@playwright/test';

/** Mount the production panel/uPlot with a controlled producer, without navigation. */
export async function mountMetricPanelFixture(page: Page) {
  const built = buildSync({
    stdin: {
      contents: `import React from 'react';
        import {createRoot} from 'react-dom/client';
        import {flushSync} from 'react-dom';
        import {OverviewMetricHistoryPanel} from './src/pages/OverviewMetricHistoryPanel';
        import {OVERVIEW_METRIC_GRAPHS} from './src/pages/overview-metric-history';
        const root = createRoot(document.getElementById('fixture'));
        window.renderPanel = (history, windowSeconds = 60) => flushSync(() => root.render(
          React.createElement(OverviewMetricHistoryPanel, {
            descriptor: OVERVIEW_METRIC_GRAPHS[0], history, error: false,
            selectedWindowSeconds: windowSeconds, nowMs: Date.now(),
            readout: {value: 7, state: 'fresh', ageMs: 0, observedAtMs: Date.now()}
          })));`,
      resolveDir: process.cwd(),
      loader: 'tsx',
    },
    bundle: true,
    jsx: 'automatic',
    write: false,
    outfile: 'fixture.js',
    define: { 'process.env.NODE_ENV': '"production"' },
  });
  await page.setContent('<div id="fixture" style="width:480px"></div>');
  await page.addStyleTag({
    content: built.outputFiles.find((file) => file.path.endsWith('.css'))!.text,
  });
  await page.addStyleTag({
    content:
      '.overview-metric-history__viewport {flex:0 0 auto;width:400px;height:80px} .overview-metric-history {background:#111827;color:white}',
  });
  await page.addScriptTag({
    content: built.outputFiles.find((file) => file.path.endsWith('.js'))!.text,
  });
}
