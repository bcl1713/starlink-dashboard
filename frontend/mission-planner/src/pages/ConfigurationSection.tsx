import type { ReactNode } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from '@/components/ui/card';

/** Shared surface for configuration controls and read-only health reports. */
export function ConfigurationSection({
  title,
  description,
  children,
  label = title,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  label?: string;
}) {
  return (
    <Card role="region" aria-label={label} className="min-w-0">
      <CardHeader className="py-4">
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
