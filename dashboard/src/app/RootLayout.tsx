import { Outlet, useLocation } from '@tanstack/react-router';
import { AppDataProvider, useAppData } from './AppDataProvider';
import { Header } from './Header';
import { SidebarContent } from './Sidebar';
import { MockDataBanner } from '@/components/research/MockDataBanner';
import { ResearchStatusBanner } from '@/components/research/ResearchStatusBanner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { DisconnectedState, ErrorState } from '@/components/ui/states';

const TITLES: Array<{ prefix: string; title: string }> = [
  { prefix: '/candidates', title: 'Candidate Comparison' },
  { prefix: '/development', title: 'Development Explorer' },
  { prefix: '/sectors', title: 'Sector Explorer' },
  { prefix: '/diagnostics', title: 'Diagnostics' },
  { prefix: '/integrity', title: 'Research Integrity' },
];

function titleForPath(pathname: string): string {
  if (pathname === '/') return 'Overview';
  const match = TITLES.find((entry) => pathname.startsWith(entry.prefix));
  return match?.title ?? 'Overview';
}

function Shell() {
  const location = useLocation();
  const { dataMode, loading, error, retry } = useAppData();

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-64 border-r border-border bg-card lg:block">
        <SidebarContent />
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-64">
        <Header title={titleForPath(location.pathname)} />

        <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-4 px-4 py-4 md:px-6 md:py-6">
          {dataMode === 'mock' ? <MockDataBanner /> : null}
          <ResearchStatusBanner />

          {error && !loading ? (
            error.isDisconnected ? (
              <DisconnectedState onRetry={retry} />
            ) : (
              <ErrorState error={error} onRetry={retry} />
            )
          ) : (
            <Outlet />
          )}
        </main>

        <footer className="border-t border-border px-4 py-3 text-center text-xs text-muted-foreground md:px-6">
          Shenwan Research Dashboard — read-only research view. Research artifacts are the source of
          truth. This dashboard does not control research execution and cannot trade.
        </footer>
      </div>
    </div>
  );
}

export function RootLayout() {
  return (
    <TooltipProvider delayDuration={200}>
      <AppDataProvider>
        <Shell />
      </AppDataProvider>
    </TooltipProvider>
  );
}
