import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, type Page } from '@playwright/test';

const audits: unknown[] = [];
/** Native Chromium accessibility names, not a WCAG or physical-device certification. */
export async function auditControlNames(page: Page, stage: string) {
  const session = await page.context().newCDPSession(page);
  try {
    const { nodes } = await session.send('Accessibility.getFullAXTree');
    const roles = new Set([
      'button',
      'link',
      'textbox',
      'combobox',
      'checkbox',
      'switch',
      'radio',
      'slider',
      'spinbutton',
    ]);
    const unnamed = nodes
      .filter(
        (node) =>
          !node.ignored &&
          roles.has(String(node.role?.value)) &&
          !String(node.name?.value ?? '').trim()
      )
      .map((node) => ({
        role: node.role?.value,
        backendNodeId: node.backendDOMNodeId,
      }));
    audits.push({
      stage,
      viewport: page.viewportSize(),
      unnamed,
      controlsChecked: nodes.filter(
        (node) => !node.ignored && roles.has(String(node.role?.value))
      ).length,
    });
    writeFileSync(
      join(
        process.env.OPERATOR_ACCEPTANCE_EVIDENCE!,
        'workspace-accessibility.json'
      ),
      JSON.stringify(
        {
          synthetic: true,
          scope:
            'Native accessible names; keyboard focus/resize asserted in journey. Does not certify contrast, screen-reader use or real-device keyboards.',
          audits,
        },
        null,
        2
      )
    );
    expect(unnamed, stage + ' exposes an unnamed interactive control').toEqual(
      []
    );
  } finally {
    await session.detach();
  }
}
