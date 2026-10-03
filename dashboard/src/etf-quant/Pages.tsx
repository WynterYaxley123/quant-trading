import { RotateCw } from 'lucide-react';
import { useResource } from '@/hooks/useResource';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingState } from '@/components/ui/states';
import { getEtfQuantPort } from './data-port';
import { EtfPageHeader } from './components/EtfPageHeader';
import { SnapshotStrip } from './components/SnapshotStrip';
import { OverviewSection } from './sections/Overview';
import { ReadinessPage } from './sections/ReadinessPage';
import { PortfolioSection } from './sections/Portfolio';
import { RankingsSection } from './sections/Rankings';
import { FactorsSection } from './sections/Factors';
import { MappingsSection } from './sections/Mappings';
import { TradesSection } from './sections/Trades';
import { BenchmarksSection } from './sections/Benchmarks';
import { HealthSection } from './sections/Health';
import { V2ResearchSection } from './sections/V2Research';
import type { EtfQuantSnapshot } from './contracts';

export type EtfSection = 'overview' | 'readiness' | 'portfolio' | 'rankings' | 'factors' | 'mappings' | 'trades' | 'benchmarks' | 'health';

type SnapshotSection = Exclude<EtfSection, 'readiness'>;

const TITLES: Record<SnapshotSection, string> = {
  overview: 'ETF Quant 总览',
  portfolio: '模拟持仓组合',
  rankings: '行业融合排名',
  factors: '因子与模型系数',
  mappings: 'ETF 映射准入',
  trades: '模拟成交流水',
  benchmarks: '基准 · CSI 300',
  health: 'ETF Quant 数据健康',
};

const DESCRIPTIONS: Record<SnapshotSection, string> = {
  overview: '独立 ETF 产品首屏：运行阶段、数据截止、Shadow 准备状态与映射 / 基准准入一览。只读快照，不是 tick 实时行情。',
  portfolio: '模拟账户的资产、持仓与 forward NAV。全部为模拟数据，非真实账户，不存在券商或真实订单路径。',
  rankings: '三个 horizon 与融合分数的行业横截面排名。预测分数不构成任何买卖含义。',
  factors: '冻结因子集（5 / 19 / 19）与 Ridge 有符号系数，训练窗口与标签截止日完整披露。',
  mappings: '行业 → ETF 映射的准入状态、证据与阻断诊断；只接受官方证据与真实流动性。',
  trades: 'Forward-only 模拟成交记账：T0 意图、T+1 真实开盘价、收盘后延迟处理。',
  benchmarks: 'CSI 300 sidecar 基准（仅展示，不进入模型）；NASDAQ / S&P 500 暂缓接入。',
  health: '数据工程状态：新鲜度、复权行、质量标记、阻断与行业成分覆盖。',
};

function SectionContent({ section, data }: { section: SnapshotSection; data: EtfQuantSnapshot }) {
  switch (section) {
    case 'overview':
      return <OverviewSection data={data} />;
    case 'portfolio':
      return <PortfolioSection data={data} />;
    case 'rankings':
      return <RankingsSection data={data} />;
    case 'factors':
      return <FactorsSection data={data} />;
    case 'mappings':
      return <MappingsSection data={data} />;
    case 'trades':
      return <TradesSection data={data} />;
    case 'benchmarks':
      return <BenchmarksSection data={data} />;
    case 'health':
      return <HealthSection data={data} />;
  }
}

function SnapshotPage({ section }: { section: SnapshotSection }) {
  const port = getEtfQuantPort();
  const resource = useResource((signal) => port.getSnapshot(signal), [port, section]);
  const data = resource.data;
  return (
    <div className="flex flex-col gap-5">
      <EtfPageHeader
        title={TITLES[section]}
        description={DESCRIPTIONS[section]}
        actions={
          <Button variant="outline" size="sm" onClick={resource.retry}>
            <RotateCw aria-hidden="true" />
            手动刷新
          </Button>
        }
      />
      {section==='overview' && <V2ResearchSection />}
      {resource.loading ? (
        <LoadingState label="正在读取 ETF Quant 独立快照" />
      ) : resource.error ? (
        <Card>
          <CardHeader>
            <CardTitle>ETF Quant 接口未连接 / 完整性阻断</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            <p>没有自动 mock fallback。请检查独立 API、runtime 配置和完整性门控后手动刷新。</p>
            <Button variant="outline" size="sm" className="w-fit" onClick={resource.retry}>
              <RotateCw aria-hidden="true" />
              手动刷新
            </Button>
          </CardContent>
        </Card>
      ) : data ? (
        <>
          <SnapshotStrip data={data} />
          <SectionContent section={section} data={data} />
        </>
      ) : null}
    </div>
  );
}

export function EtfQuantPage({ section }: { section: EtfSection }) {
  if (section === 'readiness') return <ReadinessPage />;
  return <SnapshotPage section={section} />;
}
