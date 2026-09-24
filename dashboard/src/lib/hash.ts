/**
 * Hash display helpers. Hashes are abbreviated by default (8-12 chars) and
 * expanded on explicit click. No clipboard permission APIs are used.
 */

export function abbreviateHash(value: string | null | undefined, length = 10): string {
  if (value === null || value === undefined || value === '') return '—';
  const cleanLength = Math.max(4, Math.min(length, 12));
  if (value.length <= cleanLength) return value;
  return `${value.slice(0, cleanLength)}…`;
}

export function isExpandableHash(value: string | null | undefined, length = 10): boolean {
  if (value === null || value === undefined) return false;
  return value.length > Math.max(4, Math.min(length, 12));
}
