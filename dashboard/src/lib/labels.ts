/** Human-facing Chinese labels. API, route and artifact machine values remain unchanged. */
export function phaseLabel(value: string): string {
  return value === 'DEVELOPMENT' ? 'Development（开发集）' : '未识别阶段';
}

export function sealLabel(value: string): string {
  return value === 'SEALED' ? '已封存' : '未识别状态';
}

export function enabledLabel(value: string): string {
  return value === 'DISABLED' ? '未启用' : '未识别状态';
}

export function yesNo(value: boolean): string {
  return value ? '是' : '否';
}

export function researchLabel(value: string): string {
  if (value === 'SECTOR_INDEX_RESEARCH_ONLY') return '仅限行业指数研究';
  if (value === 'MOCK_SYNTHETIC_RESEARCH_LABEL') return '模拟研究标签';
  return '未识别研究标签';
}

export function classificationLabel(value: string): string {
  if (value === 'FIXED_CLASSIFICATION_RESEARCH') return '固定分类研究';
  if (value === 'MOCK_FIXED_CLASSIFICATION') return '模拟固定分类研究';
  return '未识别分类方式';
}

export function sourceLabel(value: string): string {
  if (value === 'RESEARCH_ARTIFACTS') return '正式研究产物';
  if (value === 'MOCK_SYNTHETIC_FIXTURES') return '模拟测试数据';
  return '未识别数据来源';
}

export function preprocessingLabel(value: string): string {
  if (value === 'NONE') return '无';
  if (value === 'TRAIN_ONLY_STANDARDIZATION') return '仅训练集标准化';
  return '未识别预处理';
}

export function targetLabel(value: string): string {
  if (value === 'ABSOLUTE_FORWARD_RETURN') return '绝对未来收益';
  if (value === 'CROSS_SECTIONAL_EXCESS_FORWARD_RETURN') return '横截面超额未来收益';
  return '未识别训练目标';
}

export function horizonLabel(value: number): string {
  return `${value}日`;
}
