import { Link, useLocation } from '@tanstack/react-router';
import { Activity } from 'lucide-react';
import { visibleNavGroups } from './nav';
import { useAppData } from './AppDataProvider';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/cn';

/**
 * Sidebar content (research navigation). Shared between the desktop fixed
 * sidebar and the mobile drawer. Product identity is ours — no upstream
 * branding. Never contains trading/portfolio sections.
 */
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { capabilities, status } = useAppData();
  const location = useLocation();
  const groups = visibleNavGroups(capabilities);

  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="flex items-start gap-2 px-2">
        <Activity aria-hidden="true" className="mt-0.5 h-5 w-5 text-primary" />
        <div>
          <p className="text-sm font-semibold leading-tight">Shenwan Research Dashboard</p>
          <p className="text-xs text-muted-foreground">Sector Index Research</p>
        </div>
      </div>

      <nav aria-label="Research sections" className="flex flex-1 flex-col gap-5">
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
        {status ? (
          <Badge variant="warning" className="w-fit">
            {status.phase}
          </Badge>
        ) : null}
        <p>Read-only research dashboard. Not a trading terminal.</p>
      </div>
    </div>
  );
}
