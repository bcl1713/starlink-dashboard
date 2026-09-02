export const MAX_JSON_RESPONSE_BYTES = 4 * 1024 * 1024;

export async function getJson(
  url: string,
  signal?: AbortSignal
): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 4000);
  const relay = () => controller.abort();
  signal?.addEventListener('abort', relay, { once: true });
  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('request failed');
    return await readBoundedJson(response, controller.signal);
  } catch {
    throw new Error('Monitoring request unavailable');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', relay);
  }
}

async function readBoundedJson(
  response: Response,
  signal: AbortSignal
): Promise<unknown> {
  const declaredLength = response.headers.get('Content-Length');
  if (declaredLength !== null) {
    const parsedLength = Number(declaredLength);
    if (
      !Number.isSafeInteger(parsedLength) ||
      parsedLength < 0 ||
      parsedLength > MAX_JSON_RESPONSE_BYTES
    ) {
      throw new Error('invalid response length');
    }
  }
  if (!response.body) throw new Error('missing response body');

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let byteCount = 0;
  const cancel = () => {
    void reader.cancel().catch(() => {});
  };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    while (true) {
      if (signal.aborted) throw new Error('request aborted');
      const { done, value } = await reader.read();
      if (done) break;
      byteCount += value.byteLength;
      if (byteCount > MAX_JSON_RESPONSE_BYTES) {
        throw new Error('response too large');
      }
      chunks.push(value);
    }

    const body = new Uint8Array(byteCount);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
    const textBody = new TextDecoder('utf-8', { fatal: true }).decode(body);
    return JSON.parse(textBody) as unknown;
  } catch (error) {
    cancel();
    throw error;
  } finally {
    signal.removeEventListener('abort', cancel);
    reader.releaseLock();
  }
}
