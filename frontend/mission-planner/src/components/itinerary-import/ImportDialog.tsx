import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { createClientId } from '../../lib/clientId';
import { itineraryImportApi } from '../../services/itinerary-import';
import type { ImportOperation } from '../../types/itinerary-import';
import { ImportProgress } from './ImportProgress';
import { ImportCorrections } from './ImportCorrections';
interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: (missionId: string) => void;
  missionId?: string;
}
export function ImportDialog(props: Props) {
  return (
    <Dialog
      open={props.open}
      onOpenChange={(value) => {
        if (!value) props.onClose();
      }}
    >
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {props.missionId
              ? 'Update from itinerary'
              : 'Create from itinerary'}
          </DialogTitle>
          <DialogDescription>
            Upload the itinerary PDF and route KMLs together. Routes, AR windows
            and satellite plans are prepared automatically for review in the
            mission editor.
          </DialogDescription>
        </DialogHeader>
        {props.open && <ImportForm {...props} />}
      </DialogContent>
    </Dialog>
  );
}
function remembered(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function remember(key: string, value: string | null) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* Import remains usable when browser storage is unavailable. */
  }
}
function ImportForm({ missionId, onClose, onSuccess }: Props) {
  const client = useQueryClient();
  const storageKey = `itinerary-import:${missionId ?? 'new'}`;
  const [id, setId] = useState<string | null>(() => remembered(storageKey));
  const [pdf, setPdf] = useState<File | null>(null);
  const [kmls, setKmls] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const key = useRef(createClientId());
  const completed = useRef<string | null>(null);
  const query = useQuery({
    queryKey: ['itinerary-import', id],
    enabled: !!id,
    queryFn: ({ signal }) => itineraryImportApi.read(id!, signal),
    retry: false,
    refetchInterval: (q) =>
      ['queued', 'running', 'ready'].includes(q.state.data?.state ?? '')
        ? 1000
        : false,
  });
  const op = query.data;
  useEffect(() => {
    if (op?.state === 'committed' && completed.current !== op.id) {
      completed.current = op.id;
      remember(storageKey, null);
      void client.invalidateQueries({ queryKey: ['missions'] });
      void client.invalidateQueries({ queryKey: ['timeline', op.mission_id] });
      onSuccess(op.mission_id);
      onClose();
    }
  }, [op, storageKey, client, onSuccess, onClose]);
  const perform = useCallback(
    async (action: () => Promise<ImportOperation>) => {
      setBusy(true);
      setError('');
      try {
        const value = await action();
        setId(value.id);
        remember(storageKey, value.id);
        client.setQueryData(['itinerary-import', value.id], value);
      } catch (e) {
        setError(
          e instanceof Error
            ? e.message
            : 'Import could not complete. Try again.'
        );
      } finally {
        setBusy(false);
      }
    },
    [client, storageKey]
  );
  const automatic = useRef<string | null>(null);
  useEffect(() => {
    if (op?.state !== 'ready' || op.stage === 'applying_changes') return;
    const token = `${op.id}:${op.generation}`;
    if (automatic.current === token) return;
    automatic.current = token;
    const choices = Object.fromEntries(
      (op.details.revision?.conflicts ?? []).map((c) => [c.field, 'replace'])
    );
    void perform(() =>
      itineraryImportApi.commit(op.id, op.generation, choices)
    );
  }, [op, perform]);
  const reset = async () => {
    if (id) {
      try {
        await itineraryImportApi.cancel(id);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unable to cancel import');
        return;
      }
    }
    remember(storageKey, null);
    setId(null);
    key.current = createClientId();
    setError('');
  };
  return (
    <div className="space-y-4">
      {!id && (
        <fieldset disabled={busy} className="space-y-4">
          <label className="block">
            Itinerary PDF
            <Input
              type="file"
              accept=".pdf,application/pdf"
              aria-label="Itinerary PDF"
              onChange={(e) => {
                setPdf(e.target.files?.[0] ?? null);
                key.current = createClientId();
              }}
            />
          </label>
          <label className="block">
            Route KMLs
            <Input
              type="file"
              multiple
              accept=".kml"
              aria-label="Route KMLs"
              onChange={(e) => {
                setKmls(Array.from(e.target.files ?? []));
                key.current = createClientId();
              }}
            />
          </label>
          <p className="text-sm text-muted-foreground">
            PDF up to 10 MiB. Up to 16 KMLs, totaling 40 MiB.
            {missionId
              ? ' Omit unchanged files to reuse retained sources.'
              : ''}
          </p>
          <Button
            disabled={busy || (!missionId && (!pdf || !kmls.length))}
            onClick={() => {
              if (pdf || missionId)
                void perform(() =>
                  itineraryImportApi.start(pdf, kmls, key.current, missionId)
                );
            }}
          >
            {missionId ? 'Update mission' : 'Generate mission'}
          </Button>
        </fieldset>
      )}
      {op && <ImportProgress operation={op} />}
      {op?.state === 'needs_input' && (
        <ImportCorrections
          key={op.generation}
          operation={op}
          busy={busy}
          onResolve={(choices) =>
            void perform(() =>
              itineraryImportApi.resolve(op.id, op.generation, choices)
            )
          }
        />
      )}
      {op?.state === 'needs_input' && !op.details.itinerary && (
        <Button
          disabled={busy}
          onClick={() =>
            void perform(() =>
              itineraryImportApi.resolve(op.id, op.generation, {})
            )
          }
        >
          Retry update
        </Button>
      )}
      {(error || query.error) && (
        <p role="alert">
          {error ||
            (query.error instanceof Error
              ? query.error.message
              : 'Unable to load import. Try again.')}
        </p>
      )}
      {op?.state === 'failed' && (
        <p role="alert">
          Import could not complete. Your existing mission has not been
          replaced.
        </p>
      )}
      {id && op?.state !== 'committed' && (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => void reset()}
          >
            {op?.state === 'running' || op?.state === 'queued'
              ? 'Cancel import'
              : 'Choose different files'}
          </Button>
          {query.error && (
            <Button variant="outline" onClick={() => void query.refetch()}>
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
