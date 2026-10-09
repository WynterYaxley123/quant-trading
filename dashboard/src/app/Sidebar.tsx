import { Link, useLocation } from '@tanstack/react-router';
import { Activity } from 'lucide-react';
import { visibleNavGroups } from './nav';
import { useAppData } from './AppDataProvider';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/cn';
import { phaseLabel } from '@/lib/labels';
import { useEtfQuantCapability } from '@/etf-quant/Provider';

/**
 * Sidebar content (research navigation). Shared between the desktop fixed
 * sidebar and the mobile drawer. Product identity is ours — no upstream
 * branding. ETF Quant is independently capability-gated, never a Research flag.
 */
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { capabilities, status } = useAppData();
  const location = useLocation();
  const {etfQuant} = useEtfQuantCapability();
  const groups = visibleNavGroups(capabilities,etfQuant && location.pathname.startsWith('/etf-quant/'));

  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-start gap-2 px-2">
        <Activity aria-hidden="true" className="mt-0.5 h-5 w-5 text-primary" />
        <div>
          <p className="text-sm font-semibold leading-tight">Quant Trading / Industry Forecast</p>
          <p className="text-xs text-muted-foreground">申万行业 · 只读预测研究</p>
        </div>
      </div>

      <nav aria-label="研究页面导航" className="flex flex-1 flex-col gap-5">
        <Link to="/industry-forecast/swl1-rev10" onClick={onNavigate} aria-current={location.pathname==='/industry-forecast/swl1-rev10'?'page':undefined} className="rounded-md border border-border px-3 py-2 text-sm font-medium">REV10 · 短周期研究</Link>
        {groups.map((group) => (
          <div key={group.label} className="flex flex-col gap-1">
            <p className="px-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {group.label}
            </p>
            {group.items.map((item) => {
              const active =
                item.to === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={onNavigate}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'rounded-md px-2 py-1.5 text-sm transition-colors',
                    active
                      ? 'bg-accent font-medium text-accent-foreground'
                      : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="flex flex-col gap-1 px-2 text-xs text-muted-foreground">
        {location.pathname.startsWith('/etf-quant/') ? <Badge variant="warning" className="w-fit">SIMULATION_ONLY</Badge> : status ? (
          <Badge variant="warning" className="w-fit">
            {phaseLabel(status.phase)}
          </Badge>
        ) : null}
        <p>只读研究界面，不提供交易功能。</p>
      </div>
    </div>
  );
}
