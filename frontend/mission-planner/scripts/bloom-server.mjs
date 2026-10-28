import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { extname, resolve, sep } from 'node:path';

const root = fileURLToPath(new URL('../dist-bloom/', import.meta.url));
const port = Number(process.env.BLOOM_PORT ?? 4290);
const mime = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.json': 'application/json',
  '.md': 'text/plain',
};
const server = createServer(async (request, response) => {
  response.setHeader(
    'Content-Security-Policy',
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'none'; worker-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
  );
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  if (!['GET', 'HEAD'].includes(request.method)) {
    response.writeHead(405).end();
    return;
  }
  try {
    const url = new URL(request.url, 'http://127.0.0.1');
    if (
      url.pathname.startsWith('/api') ||
      request.headers.host !== `127.0.0.1:${port}`
    ) {
      response.writeHead(403).end();
      return;
    }
    const pathname = decodeURIComponent(
      url.pathname === '/' ? '/bloom.html' : url.pathname
    );
    const file = resolve(root, `.${pathname}`);
    if (
      !file.startsWith(root.endsWith(sep) ? root : root + sep) ||
      !(await stat(file)).isFile()
    ) {
      response.writeHead(404).end();
      return;
    }
    response.setHeader(
      'Content-Type',
      mime[extname(file)] ?? 'application/octet-stream'
    );
    response
      .writeHead(200)
      .end(request.method === 'HEAD' ? undefined : await readFile(file));
  } catch {
    response.writeHead(404).end();
  }
});
server.listen(port, '127.0.0.1', () =>
  console.log(`Offline synthetic bloom experiment: http://127.0.0.1:${port}`)
);
for (const signal of ['SIGINT', 'SIGTERM'])
  process.on(signal, () => server.close(() => process.exit(0)));
