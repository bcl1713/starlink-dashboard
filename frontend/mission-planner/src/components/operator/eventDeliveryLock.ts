/** Atomic same-origin cue reservations work on ordinary HTTP using IndexedDB. */
const databaseName = 'operator-local-alerts-v1';
const retention = 7 * 24 * 60 * 60 * 1000;
export function reserveEventCues(
  keys: string[],
  owner: string,
  now = Date.now()
): Promise<string[]> {
  return new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) {
      reject(new Error('Local coordination unavailable'));
      return;
    }
    let settled = false;
    const request = indexedDB.open(databaseName, 1);
    const timer = setTimeout(() => {
      settled = true;
      reject(new Error('Local coordination timed out'));
    }, 2000);
    const fail = () => {
      clearTimeout(timer);
      if (!settled) {
        settled = true;
        reject(new Error('Local coordination unavailable'));
      }
    };
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore('cues', {
        keyPath: 'key',
      });
      store.createIndex('at', 'at');
    };
    request.onerror = fail;
    request.onsuccess = () => {
      const db = request.result;
      if (settled) {
        db.close();
        return;
      }
      const reserved: string[] = [];
      const transaction = db.transaction('cues', 'readwrite');
      const store = transaction.objectStore('cues');
      transaction.oncomplete = () => {
        clearTimeout(timer);
        db.close();
        if (!settled) {
          settled = true;
          resolve(reserved);
        }
      };
      transaction.onabort = () => {
        db.close();
        fail();
      };
      transaction.onerror = () => {
        db.close();
        fail();
      };
      const lease = store.get('__emitter_lease__');
      lease.onsuccess = () => {
        const current = lease.result as
          | { owner: string; expires: number }
          | undefined;
        if (current && current.owner !== owner && current.expires > now) return;
        const unique = [...new Set(keys)];
        let left = unique.length;
        for (const key of unique) {
          const existing = store.get(key);
          existing.onsuccess = () => {
            if (!existing.result || existing.result.at < now - retention)
              reserved.push(key);
            left--;
            if (left === 0 && reserved.length) {
              store.put({
                key: '__emitter_lease__',
                owner,
                expires: now + 6000,
                at: now,
              });
              for (const item of reserved) store.put({ key: item, at: now });
              // Keep the device-local emission cache bounded without touching
              // operational records or durable shared acknowledgments.
              const count = store.count();
              count.onsuccess = () => {
                let excess = Math.max(0, count.result - 2001);
                const cursor = store.index('at').openCursor();
                cursor.onsuccess = () => {
                  const item = cursor.result;
                  if (!item) return;
                  if (
                    item.primaryKey !== '__emitter_lease__' &&
                    (item.value.at < now - retention || excess > 0)
                  ) {
                    item.delete();
                    excess = Math.max(0, excess - 1);
                  }
                  item.continue();
                };
              };
            }
          };
        }
      };
    };
  });
}
