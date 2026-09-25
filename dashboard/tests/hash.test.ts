import { describe, expect, it } from 'vitest';
import { abbreviateHash, isExpandableHash } from '@/lib/hash';

describe('hash formatting', () => {
  it('abbreviates long hashes with an ellipsis', () => {
    expect(abbreviateHash('f2080f56abcdef0123456789')).toBe('f2080f56ab…');
    expect(abbreviateHash('f2080f56abcdef0123456789', 8)).toBe('f2080f56…');
  });

  it('never abbreviates short values and handles missing values', () => {
    expect(abbreviateHash('short')).toBe('short');
    expect(abbreviateHash(null)).toBe('—');
    expect(abbreviateHash(undefined)).toBe('—');
    expect(abbreviateHash('')).toBe('—');
  });

  it('knows when a hash is expandable', () => {
    expect(isExpandableHash('f2080f56abcdef0123456789')).toBe(true);
    expect(isExpandableHash('short')).toBe(false);
    expect(isExpandableHash(null)).toBe(false);
  });
});
