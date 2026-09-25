import { describe, expect, it } from 'vitest';
import {
  formatCount,
  formatFactor,
  formatReturn,
  formatUnitless,
  NULL_PLACEHOLDER,
} from '@/lib/format';

describe('number formatting', () => {
  it('formats unitless metrics as plain decimals (never percentage)', () => {
    expect(formatUnitless(-0.0682)).toBe('-0.0682');
    expect(formatUnitless(0)).toBe('0.0000');
    expect(formatUnitless(0.0123)).toBe('0.0123');
  });

  it('converts return decimals to percentages', () => {
    expect(formatReturn(0.0181)).toBe('1.81%');
    expect(formatReturn(-0.0101)).toBe('-1.01%');
    expect(formatReturn(0)).toBe('0.00%');
  });

  it('renders null / undefined / NaN / Infinity as the em-dash placeholder', () => {
    for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(formatUnitless(value as number | null | undefined)).toBe(NULL_PLACEHOLDER);
      expect(formatReturn(value as number | null | undefined)).toBe(NULL_PLACEHOLDER);
      expect(formatCount(value as number | null | undefined)).toBe(NULL_PLACEHOLDER);
      expect(formatFactor(value as number | null | undefined)).toBe(NULL_PLACEHOLDER);
    }
    expect(NULL_PLACEHOLDER).toBe('—');
  });

  it('formats counts as integers and factors with 2 decimals', () => {
    expect(formatCount(124)).toBe('124');
    expect(formatCount(0)).toBe('0');
    expect(formatFactor(0.25)).toBe('0.25');
  });
});
