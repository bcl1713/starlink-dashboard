export type DisplayAction = 'recenter' | 'fullscreen';
export type DisplayResult =
  | 'accepted'
  | 'interaction-required'
  | 'unsupported'
  | 'expired'
  | 'failed';

export interface DisplayPeer {
  id: string;
  label: string;
  fullscreen: boolean;
  actions: DisplayAction[];
}
export interface CommandFeedback {
  requestId: string;
  targetId: string;
  action: DisplayAction;
  status: 'pending' | DisplayResult | 'timeout' | 'unavailable';
}
export interface DisplaySnapshot {
  available: boolean;
  peers: DisplayPeer[];
  feedback: CommandFeedback | null;
}

type Envelope = { v: 1; sender: string; seq: number };
export type OverviewDisplayMessage = Envelope &
  (
    | { type: 'discover' | 'bye'; target: null }
    | {
        type: 'presence';
        target: string | null;
        label: string;
        fullscreen: boolean;
        actions: DisplayAction[];
      }
    | {
        type: 'command';
        target: string;
        requestId: string;
        action: DisplayAction;
        expiresAtMs: number;
      }
    | {
        type: 'result';
        target: string;
        requestId: string;
        action: DisplayAction;
        status: DisplayResult;
        fullscreen: boolean;
      }
  );

const fields = {
  discover: [],
  bye: [],
  presence: ['label', 'fullscreen', 'actions'],
  command: ['requestId', 'action', 'expiresAtMs'],
  result: ['requestId', 'action', 'status', 'fullscreen'],
} as const;
const commonFields = ['v', 'type', 'sender', 'target', 'seq'];
const isText = (value: unknown): value is string =>
  typeof value === 'string' && value.trim().length > 0 && value.length <= 128;
const isAction = (value: unknown): value is DisplayAction =>
  value === 'recenter' || value === 'fullscreen';
const isResult = (value: unknown): value is DisplayResult =>
  value === 'accepted' ||
  value === 'interaction-required' ||
  value === 'unsupported' ||
  value === 'expired' ||
  value === 'failed';

function parseActions(value: unknown): DisplayAction[] | null {
  if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype)
    return null;
  const descriptors: Record<string, PropertyDescriptor> =
    Object.getOwnPropertyDescriptors(value);
  const length = descriptors.length.value;
  if (length > 2 || Reflect.ownKeys(value).length !== length + 1) return null;
  const actions: DisplayAction[] = [];
  for (let index = 0; index < length; index++) {
    const descriptor = descriptors[String(index)];
    if (!descriptor || !('value' in descriptor) || !isAction(descriptor.value))
      return null;
    actions.push(descriptor.value);
  }
  return new Set(actions).size === actions.length ? actions : null;
}

export function parseOverviewDisplayMessage(
  value: unknown
): OverviewDisplayMessage | null {
  try {
    if (!value || typeof value !== 'object') return null;
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) return null;
    const descriptors = Object.getOwnPropertyDescriptors(value);
    // No accessors, symbols or inherited fields: examine data descriptors first.
    if (
      Reflect.ownKeys(value).some(
        (key) => typeof key !== 'string' || !('value' in descriptors[key])
      )
    )
      return null;
    const type: unknown = descriptors.type?.value;
    if (typeof type !== 'string' || !Object.hasOwn(fields, type)) return null;
    const keys = [...commonFields, ...fields[type as keyof typeof fields]];
    if (
      Reflect.ownKeys(value).length !== keys.length ||
      keys.some((key) => !Object.hasOwn(descriptors, key))
    )
      return null;
    const data = value as Record<string, unknown>;
    if (
      data.v !== 1 ||
      !isText(data.sender) ||
      !Number.isSafeInteger(data.seq) ||
      (data.seq as number) <= 0
    )
      return null;
    const envelope: Envelope = {
      v: 1,
      sender: data.sender,
      seq: data.seq as number,
    };
    if (type === 'discover' || type === 'bye') {
      return data.target === null ? { ...envelope, type, target: null } : null;
    }
    if (type === 'presence') {
      const actions = parseActions(data.actions);
      if (
        (data.target !== null && !isText(data.target)) ||
        !isText(data.label) ||
        typeof data.fullscreen !== 'boolean' ||
        actions === null
      )
        return null;
      return {
        ...envelope,
        type,
        target: data.target,
        label: data.label,
        fullscreen: data.fullscreen,
        actions,
      };
    }
    if (
      !isText(data.target) ||
      !isText(data.requestId) ||
      !isAction(data.action)
    )
      return null;
    const commandFields = {
      ...envelope,
      target: data.target,
      requestId: data.requestId,
      action: data.action,
    };
    if (type === 'command') {
      return typeof data.expiresAtMs === 'number' &&
        Number.isFinite(data.expiresAtMs) &&
        data.expiresAtMs >= 0
        ? { ...commandFields, type, expiresAtMs: data.expiresAtMs }
        : null;
    }
    return isResult(data.status) && typeof data.fullscreen === 'boolean'
      ? {
          ...commandFields,
          type: 'result',
          status: data.status,
          fullscreen: data.fullscreen,
        }
      : null;
  } catch {
    return null;
  }
}
