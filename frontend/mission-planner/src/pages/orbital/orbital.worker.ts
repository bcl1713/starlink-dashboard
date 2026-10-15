import { OrbitalWorkerRuntime, type WorkerInput } from './worker-protocol';

const runtime = new OrbitalWorkerRuntime((message, transfer) =>
  self.postMessage(message, { transfer })
);
self.onmessage = (event: MessageEvent<WorkerInput>) =>
  runtime.receive(event.data);
