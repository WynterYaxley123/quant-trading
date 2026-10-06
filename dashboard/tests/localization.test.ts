import { describe, expect, it } from 'vitest';
import { NAV_GROUPS } from '@/app/nav';
import { researchStatusSchema } from '@/api/contracts';
import { ResearchApiError } from '@/api/errors';
import { formatReturn, formatUnitless, NULL_PLACEHOLDER } from '@/lib/format';
import {
  classificationLabel, enabledLabel, phaseLabel, researchLabel,
  sealLabel, sourceLabel, yesNo,
} from '@/lib/labels';
import { mockResearchStatus } from '@/mocks/fixtures';

describe('Chinese presentation without changing machine contracts', () => {
  it('keeps the research-only navigation in Chinese while preserving route paths', () => {
    expect(NAV_GROUPS.flatMap((group) => group.items.map((item) => [item.to, item.label])))
      .toEqual([
        ['/', 'Industry Forecast'], ['/research', '概览'], ['/candidates', '候选方案对比'],
        ['/development', 'Development 探索'], ['/sectors', '行业探索'],
        ['/diagnostics', '诊断'], ['/integrity', '研究完整性'],
      ]);
  });

  it('maps Development, sealed and disabled statuses without changing raw values', () => {
    expect(phaseLabel('DEVELOPMENT')).toBe('Development（开发集）');
    expect(sealLabel('SEALED')).toBe('已封存');
    expect(enabledLabel('DISABLED')).toBe('未启用');
    expect(researchLabel('SECTOR_INDEX_RESEARCH_ONLY')).toBe('仅限行业指数研究');
    expect(classificationLabel('FIXED_CLASSIFICATION_RESEARCH')).toBe('固定分类研究');
    expect(sourceLabel('RESEARCH_ARTIFACTS')).toBe('正式研究产物');
  });

  it('does not invert false or conflate zero with unavailable', () => {
    expect(yesNo(false)).toBe('否');
    expect(yesNo(true)).toBe('是');
    expect(formatUnitless(0)).toBe('0.0000');
    expect(formatUnitless(null)).toBe(NULL_PLACEHOLDER);
    expect(NULL_PLACEHOLDER).toBe('—');
  });

  it('keeps IC/RankIC unitless and formats only returns as percentages', () => {
    expect(formatUnitless(0.0312)).toBe('0.0312');
    expect(formatReturn(0.032)).toBe('3.20%');
  });

  it('shows Chinese error explanations while retaining exact machine error codes', () => {
    const error = new ResearchApiError('SEALED_PHASE', 'Sealed phase is unavailable', 403);
    expect(error.code).toBe('SEALED_PHASE');
    expect(error.message).toBe('Sealed phase is unavailable');
    expect(error.userMessage).toContain('封存');
    expect(new ResearchApiError('NETWORK_UNREACHABLE').userMessage)
      .toBe('研究数据接口未连接。');
  });

  it('keeps API field names and raw enum values machine-readable', () => {
    const parsed = researchStatusSchema.parse(mockResearchStatus);
    expect(parsed.phase).toBe('DEVELOPMENT');
    expect(parsed.validation).toBe('SEALED');
    expect(parsed.tradable).toBe(false);
    expect(Object.keys(parsed)).toContain('classification');
    expect(Object.keys(parsed)).not.toContain('分类方式');
  });
});
