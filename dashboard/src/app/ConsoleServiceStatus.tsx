import { useAppData } from './AppDataProvider';
import { useEtfQuantCapability, etfServiceState } from '@/etf-quant/Provider';
import { Badge } from '@/components/ui/badge';

export function ConsoleServiceStatus() {
  const research = useAppData();
  const etf = useEtfQuantCapability();
  const researchState = research.healthLoading ? 'CHECKING'
    : research.healthError ? (research.healthError.isDisconnected ? 'DISCONNECTED' : 'DEGRADED')
    : research.error ? 'DEGRADED'
    : research.health?.status === 'ok' && research.health.readOnly ? 'READY' : 'DEGRADED';
  const services = [
    // Successfully rendering this document is the Dashboard readiness observation.
    { name: 'Dashboard', state: 'READY' },
    { name: 'ETF Quant API', state: etfServiceState(etf.loading, etf.status, etf.error) },
    { name: 'Research API', state: researchState },
  ];
  return (
    <section aria-label="控制台服务" className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-3 py-2 text-xs">
      <span className="font-semibold text-muted-foreground">控制台服务</span>
      {services.map(({ name, state }) => (
        <span key={name} className="flex items-center gap-1.5">
          {name}
          <Badge variant={state === 'READY' ? 'success' : state === 'CHECKING' ? 'outline' : state === 'DEGRADED' ? 'warning' : 'destructive'}>{state}</Badge>
        </span>
      ))}
    </section>
  );
}
