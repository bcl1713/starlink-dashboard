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

/**
 * Format ISO 8601 datetime string to 24-hour format for display
 *
 * This utility ensures consistent 24-hour time display throughout the application,
 * which is critical for professional users in aviation, maritime, and military contexts
 * where 24-hour format is the standard.
 *
 * @param iso8601 - Format: "2025-11-24T10:30:00Z"
 * @returns Formatted string in 24-hour format: "01/07/2025, 14:30:00"
 *
 * @example
 * formatTime24Hour("2025-01-07T14:30:00Z") // Returns "01/07/2025, 14:30:00"
 */
export function formatTime24Hour(iso8601: string): string {
  if (!iso8601) return '';

  const date = new Date(iso8601);

  // Use toLocaleString with explicit 24-hour format options
  // hour12: false ensures 24-hour format (14:00 instead of 2:00 PM)
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}
