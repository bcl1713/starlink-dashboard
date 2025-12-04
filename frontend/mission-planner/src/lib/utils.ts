import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Convert datetime-local format to ISO 8601 format for backend
 * @param localDateTime - Format: "2025-11-24 10:30" or "2025-11-24T10:30"
 * @returns ISO 8601 string: "2025-11-24T10:30:00Z"
 */
export function toISO8601(localDateTime: string): string {
  if (!localDateTime) return '';

  // Handle both space and T separator
  const normalized = localDateTime.replace(' ', 'T');

  // Parse and convert to ISO 8601 with seconds and Z suffix
  const date = new Date(normalized);
  return date.toISOString();
}

/**
 * Convert ISO 8601 format to datetime-local format for input fields
 * @param iso8601 - Format: "2025-11-24T10:30:00Z"
 * @returns datetime-local string: "2025-11-24T10:30"
 */
export function fromISO8601(iso8601: string): string {
  if (!iso8601) return '';

  // Take first 16 characters (YYYY-MM-DDTHH:MM)
  return iso8601.slice(0, 16);
}
