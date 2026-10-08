import { z } from 'zod';

export const mapInputSchema = z
  .object({
    schemaVersion: z.literal(1),
    framingVersion: z.literal('mission-map-v1'),
    legId: z.string().regex(/^[a-zA-Z0-9_-]{1,100}$/),
    referenceUtc: z.iso.datetime(),
    route: z
      .array(
        z.object({
          latitude: z.number().min(-90).max(90),
          longitude: z.number().min(-180).max(180),
          timestamp: z.iso.datetime(),
        })
      )
      .min(2)
      .max(2000),
    markers: z
      .array(
        z.object({
          id: z.string().min(1).max(100),
          label: z.string().regex(/^\d{1,4}$/),
          routeIndex: z.number().int().nonnegative(),
        })
      )
      .max(200),
  })
  .superRefine((input, ctx) => {
    if (input.referenceUtc !== input.route[0].timestamp)
      ctx.addIssue({
        code: 'custom',
        message: 'Reference must be effective takeoff',
      });
    if (
      input.route.some(
        (p, i) =>
          i > 0 &&
          Date.parse(p.timestamp) <= Date.parse(input.route[i - 1].timestamp)
      )
    )
      ctx.addIssue({
        code: 'custom',
        message: 'Route timestamps must be ordered',
      });
    if (
      input.markers.some((m) => m.routeIndex >= input.route.length) ||
      new Set(input.markers.map((m) => m.id)).size !== input.markers.length
    )
      ctx.addIssue({
        code: 'custom',
        message: 'Markers must identify route points uniquely',
      });
  });
export type MissionMapInput = z.infer<typeof mapInputSchema>;
export function validateMapInput(raw: unknown): MissionMapInput {
  return mapInputSchema.parse(raw);
}
export interface MapReadiness {
  status: 'loading' | 'ready' | 'error';
  error?: string;
  digest?: string;
  viewId?: string;
  framing?: unknown;
  labels?: { text: string; x: number; y: number }[];
  stages?: string[];
}
declare global {
  interface Window {
    missionMap: {
      plan: (raw: unknown) => { id: string }[];
      render: (raw: unknown, viewIndex: number, digest: string) => void;
      state: MapReadiness;
    };
  }
}
