import { describe, expect, it } from 'vitest';
import { parseExplorerSearch } from '@/routes/searchParams';

describe('explorer URL state', () => {
  it('preserves a numeric horizon parsed from a bookmarked URL', () => {
    expect(parseExplorerSearch({ candidate: 'D3', metric: 'top5MinusUniverse', horizon: 120 }))
      .toEqual({ candidate: 'D3', metric: 'top5MinusUniverse', horizon: '120' });
  });

  it('accepts only the frozen horizons without changing route field names', () => {
    expect(parseExplorerSearch({ horizon: '40' }).horizon).toBe('40');
    expect(parseExplorerSearch({ horizon: 10 }).horizon).toBe('10');
    expect(parseExplorerSearch({ horizon: 20 }).horizon).toBeUndefined();
  });
});
