import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { within } from './render-budget.mjs';
import { ownedPath } from './render-owner.mjs';
import {
  composeMissionPage,
  composeMissionBriefing,
} from './briefing/document.mjs';
import { planBriefingPages } from './briefing/pagination.mjs';
import { buildPdfExpectations } from './briefing/pdf-expectations.mjs';
const here = path.dirname(fileURLToPath(import.meta.url));
const hash = (v) => createHash('sha256').update(v).digest('hex');
const error = (code, message) => Object.assign(new Error(message), { code });

async function ready(page, budget) {
  const result = await within(
    page.evaluate(async () => {
      await document.fonts.ready;
      try {
        await document.fonts.load('400 20px Briefing');
        await document.fonts.load('700 20px Briefing');
      } catch {
        return { fonts: false };
      }
      const fonts =
        [...document.fonts].length === 2 &&
        [...document.fonts].every((f) => f.status === 'loaded');
      const images = await Promise.all(
        [...document.images].map(async (image) => {
          try {
            await image.decode();
            return image.naturalWidth > 0;
          } catch {
            return false;
          }
        })
      );
      return {
        fonts,
        images: images.every(Boolean),
      };
    }),
    budget.workRemainingMs()
  );
  if (!result.fonts) throw error('runtime', 'Intended fonts did not load');
  if (!result.images) throw error('runtime', 'Image decode failed');
}

export function createMissionDocumentLoader({
  page,
  budget,
  check,
  isBlocked,
}) {
  let loaded = false;
  return async (html) => {
    check();
    if (!loaded) {
      await page.setContent(html, {
        waitUntil: 'domcontentloaded',
        timeout: budget.workRemainingMs(),
      });
      loaded = true;
    } else {
      const body = html.slice(
        html.indexOf('<body>') + 6,
        html.lastIndexOf('</body>')
      );
      await within(
        page.locator('body').evaluate((element, content) => {
          element.innerHTML = content;
        }, body),
        budget.workRemainingMs()
      );
    }
    await ready(page, budget);
    if (isBlocked()) throw error('runtime', 'Remote asset rejected');
    check();
  };
}

const fitsPage = (fit) =>
  fit.width === 1280 &&
  fit.height === 720 &&
  !fit.overflow.length &&
  !fit.labelOverlaps.length;
export function cachePrimaryMeasurements({ measured, measure }) {
  return async (request) => {
    const original = measured.find((p) => p.legId === request.legId);
    if (
      original &&
      request.kind === 'primary' &&
      !request.continued &&
      JSON.stringify(original.visibleRowIds) === JSON.stringify(request.rowIds)
    )
      return { fits: fitsPage(original) };
    return measure(request);
  };
}

async function measurePages(page, budget) {
  return within(
    page.evaluate(() =>
      [...document.querySelectorAll('.briefing-page')].map((element, index) => {
        const p = element.getBoundingClientRect();
        const box = (e) => {
          const r = e.getBoundingClientRect();
          return [
            r.left - p.left,
            r.top - p.top,
            r.right - p.left,
            r.bottom - p.top,
          ];
        };
        const overflow = [],
          labels = [];
        for (const e of element.querySelectorAll(
          '[data-fit],[data-svg-label]'
        )) {
          const r = box(e);
          if (
            r[0] < -0.5 ||
            r[1] < -0.5 ||
            r[2] > p.width + 0.5 ||
            r[3] > p.height + 0.5 ||
            (!(e instanceof SVGElement) &&
              (e.scrollWidth > e.clientWidth + 1 ||
                e.scrollHeight > e.clientHeight + 1))
          )
            overflow.push({
              tag: e.tagName,
              text: e.textContent.slice(0, 80),
              bounds: r,
            });
          if (e.hasAttribute('data-svg-label'))
            labels.push({ text: e.textContent, bounds: r });
        }
        const labelOverlaps = [];
        for (let i = 0; i < labels.length; i++)
          for (let j = i + 1; j < labels.length; j++) {
            const a = labels[i].bounds,
              b = labels[j].bounds;
            if (
              Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > 1 &&
              Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > 1
            )
              labelOverlaps.push([labels[i].text, labels[j].text]);
          }
        const rows = [...element.querySelectorAll('[data-row-id]')];
        const body = rows.length ? box(element.querySelector('tbody')) : null;
        const table = box(element.querySelector('table'));
        const header = box(element.querySelector('thead'));
        return {
          page: index + 1,
          legId: element.dataset.legId,
          width: p.width,
          height: p.height,
          visibleRowIds: rows.map((r) => r.dataset.rowId),
          overflow,
          labelOverlaps,
          labels,
          pdfMeasured: {
            tableBodyBoundsPx: body,
            tableInspectionBoundsPx: [
              table[0],
              body ? body[1] : header[3],
              table[2],
              box(element.querySelector('footer'))[1],
            ],
            rows: rows.map((r) => ({
              id: r.dataset.rowId,
              cellBoundsPx: [...r.cells].map(box),
            })),
          },
        };
      })
    ),
    budget.workRemainingMs()
  );
}

export async function prepareMissionDocument({
  owner,
  budget,
  payload,
  maps,
  outputRoot,
  fault,
  check,
  onDiagnostic,
}) {
  const paths = {
    regularFont:
      process.env.BRIEFING_REGULAR_FONT ||
      '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    boldFont:
      process.env.BRIEFING_BOLD_FONT ||
      '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    apo:
      process.env.BRIEFING_APO_PATH ||
      path.resolve(
        here,
        '../../../../backend/starlink-location/app/mission/assets/APO Patch.jpg'
      ),
    css: path.join(here, 'briefing', 'briefing.css'),
  };
  const bytes = {},
    assetHashes = {};
  for (const [key, file] of Object.entries(paths)) {
    bytes[key] = await readFile(file);
    assetHashes[key] = hash(bytes[key]);
    check();
  }
  const encoded = (key, type) =>
    `data:${type};base64,${bytes[key].toString('base64')}`;
  const assets = {
    regularFontDataUrl: encoded('regularFont', 'font/ttf'),
    boldFontDataUrl: encoded('boldFont', 'font/ttf'),
    apoDataUrl: encoded('apo', 'image/jpeg'),
    cssText: bytes.css.toString(),
    maps: Object.fromEntries(
      Object.entries(maps).map(([id, m]) => [id, m.pngs[0] ?? null])
    ),
  };
  if (fault === 'font')
    assets.regularFontDataUrl = 'data:font/ttf;base64,broken';
  if (fault === 'image') assets.apoDataUrl = 'data:image/png;base64,broken';
  const context = await owner.newContext({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 2.5,
    locale: 'en-US',
    timezoneId: 'America/New_York',
    reducedMotion: 'reduce',
  });
  let blocked = false;
  await context.route('**/*', (route) => {
    blocked = true;
    return route.abort('blockedbyclient');
  });
  const page = await context.newPage();
  await page.emulateMedia({ media: 'print' });
  const load = createMissionDocumentLoader({
    page,
    budget,
    check,
    isBlocked: () => blocked,
  });
  const history = [];
  const progress = async (operation) => {
    history.push({ operation, elapsedMs: budget.elapsedMs() });
    await writeFile(
      ownedPath(outputRoot, 'document-progress.json'),
      JSON.stringify({ history })
    );
  };
  const primaryPlan = {
    schemaVersion: 2,
    missionId: payload.missionId,
    snapshotFingerprint: payload.snapshotFingerprint,
    pages: payload.legs.map((leg, index) => ({
      page: index + 1,
      legId: leg.legId,
      kind: 'primary',
      legPage: 1,
      legPageCount: 1,
      rowIds: leg.rows.map((r) => r.id),
    })),
  };
  const initialHtml = composeMissionBriefing(payload, primaryPlan, assets);
  await progress('batch-primary');
  if (fault === 'measure-hang')
    await within(new Promise(() => {}), budget.workRemainingMs());
  await load(initialHtml);
  const initialMeasured = await measurePages(page, budget);
  const pagePlan = await planBriefingPages({
    payload,
    budget,
    measure: cachePrimaryMeasurements({
      measured: initialMeasured,
      measure: async (request) => {
        await progress(
          'measure:' +
            request.legId +
            ':' +
            request.kind +
            ':' +
            request.rowIds.length
        );
        if (fault === 'measure-hang')
          await within(new Promise(() => {}), budget.workRemainingMs());
        const leg = payload.legs.find((l) => l.legId === request.legId);
        await load(
          composeMissionPage(
            leg,
            {
              ...request,
              legPage: request.kind === 'primary' ? 1 : 3,
              legPageCount: 3,
            },
            assets
          )
        );
        const [fit] = await measurePages(page, budget);
        return { fits: fitsPage(fit) };
      },
    }),
  });
  const html = composeMissionBriefing(payload, pagePlan, assets);
  await progress('final-assembly');
  if (html !== initialHtml) await load(html);
  const measured = await measurePages(page, budget);
  if (
    measured.length !== pagePlan.pages.length ||
    measured.some(
      (fit, i) =>
        fit.overflow.length ||
        fit.labelOverlaps.length ||
        fit.width !== 1280 ||
        fit.height !== 720 ||
        JSON.stringify(fit.visibleRowIds) !==
          JSON.stringify(pagePlan.pages[i].rowIds)
    )
  )
    throw error('overflow', 'Final assembled pages do not fit');
  const expectations = {
    schemaVersion: 1,
    pageCount: measured.length,
    pageSizePt: [960, 540],
    pages: [],
    rows: [],
  };
  for (let i = 0; i < measured.length; i++) {
    const descriptor = pagePlan.pages[i],
      leg = payload.legs.find((l) => l.legId === descriptor.legId);
    const rows = descriptor.rowIds.map((id) =>
      leg.rows.find((r) => r.id === id)
    );
    const expected = buildPdfExpectations(
      { ...leg, rows },
      measured[i].pdfMeasured
    );
    expectations.pages.push({ ...expected.pages[0], page: i + 1 });
    expectations.rows.push(
      ...expected.rows.map((r) => ({ ...r, page: i + 1 }))
    );
  }
  const renderedHtml = await within(page.content(), budget.workRemainingMs());
  const diagnosticNames = [],
    diagnosticHashes = { htmlPath: hash(renderedHtml) };
  await writeFile(
    ownedPath(outputRoot, 'mission-customer-briefing-trial.html'),
    renderedHtml
  );
  for (let i = 0; i < measured.length; i++) {
    check();
    await progress('preview:' + (i + 1));
    const png = await page.locator('.briefing-page').nth(i).screenshot({
      type: 'png',
      animations: 'disabled',
      timeout: budget.workRemainingMs(),
    });
    const name = `mission-customer-briefing-trial-page-${i + 1}.png`;
    onDiagnostic(name);
    await writeFile(ownedPath(outputRoot, name), png);
    diagnosticNames.push(name);
    diagnosticHashes['page-' + (i + 1)] = hash(png);
  }
  return {
    context,
    page,
    pagePlan,
    fit: { pageCount: measured.length, pages: measured },
    expectations,
    assetHashes,
    diagnosticNames,
    diagnosticHashes,
  };
}

export async function printMissionDocument({ document, budget, fault }) {
  if (fault === 'print') throw error('pdf', 'Injected print failure');
  if (fault === 'print-hang')
    return within(new Promise(() => {}), budget.workRemainingMs());
  return within(
    document.page.pdf({
      width: '13.333333in',
      height: '7.5in',
      scale: 1,
      margin: { top: '0', right: '0', bottom: '0', left: '0' },
      printBackground: true,
      displayHeaderFooter: false,
      preferCSSPageSize: true,
    }),
    budget.workRemainingMs()
  );
}
