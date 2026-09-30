import { useResource } from '@/hooks/useResource';
import { getEtfQuantPort } from '../data-port';
import { EtfPageHeader } from '../components/EtfPageHeader';
import { ReadinessBanner, ReadinessFacts, ReadinessGateList, ReadinessNotes } from '../components/ReadinessGates';
import { Button } from '@/components/ui/button';
import { LoadingState } from '@/components/ui/states';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RotateCw } from 'lucide-react';
import { CurrentStatusResource } from '../components/CurrentStatus';

/**
 * Shadow 启动准备状态（SHADOW_START_READINESS_V1）。
 * 独立的 getReadiness() 读取：不依赖快照，快照接口异常时本页仍可用。
 */
function LegacyReadinessPage() {
  const port = getEtfQuantPort();
  const resource = useResource((signal) => port.getReadiness(signal), [port]);
  const readiness = resource.data;
  return (
    <div className="flex flex-col gap-5">
      <EtfPageHeader
        title="Shadow 启动准备状态"
        description="SHADOW_START_READINESS_V1 门控评估：逐项列出启动前置条件、状态与证据。本页为只读观察，不能启动 Shadow 或创建 epoch。"
        actions={
          <Button variant="outline" size="sm" onClick={resource.retry}>
            <RotateCw aria-hidden="true" />
            手动刷新
          </Button>
        }
      />
      {resource.loading ? (
        <LoadingState label="正在读取 Shadow 启动准备状态" />
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
      ) : readiness ? (
        <>
          <ReadinessBanner readiness={readiness} />
          <ReadinessFacts readiness={readiness} />
          <ReadinessGateList readiness={readiness} />
          <ReadinessNotes readiness={readiness} />
        </>
      ) : null}
    </div>
  );
}

export function ReadinessPage() {
  if(!getEtfQuantPort().getCurrentStatus) return <LegacyReadinessPage />;
  return <div className="flex flex-col gap-5">
    <EtfPageHeader title="Shadow 启动准备状态" description="Current ETF-Quant Status：当前控制状态优先；历史 readiness artifact 保留审计，不覆盖最新认证。" />
    <CurrentStatusResource />
  </div>;
}
