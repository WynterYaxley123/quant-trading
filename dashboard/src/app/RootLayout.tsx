import { Outlet, useLocation } from '@tanstack/react-router';
import { AppDataProvider, useAppData } from './AppDataProvider';
import { Header } from './Header';
import { SidebarContent } from './Sidebar';
import { MockDataBanner } from '@/components/research/MockDataBanner';
import { ResearchStatusBanner } from '@/components/research/ResearchStatusBanner';
import { TooltipProvider } from '@/components/ui/tooltip';
import { DisconnectedState, ErrorState } from '@/components/ui/states';
import { EtfQuantProvider } from '@/etf-quant/Provider';

const TITLES: Array<{ prefix: string; title: string }> = [
  { prefix: '/candidates', title: '候选方案对比' },
  { prefix: '/development', title: 'Development 探索' },
  { prefix: '/sectors', title: '行业探索' },
  { prefix: '/diagnostics', title: '诊断' },
  { prefix: '/integrity', title: '研究完整性' },
];

function titleForPath(pathname: string): string {
  if (pathname === '/') return '概览';
  if (pathname.startsWith('/etf-quant/')) return 'ETF Quant · SIMULATION ONLY';
  const match = TITLES.find((entry) => pathname.startsWith(entry.prefix));
  return match?.title ?? '概览';
}

function Shell() {
  const location = useLocation();
  const { dataMode, loading, error, retry } = useAppData();
  const isEtf = location.pathname.startsWith('/etf-quant/');

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-50 hidden w-64 border-r border-border bg-card lg:block">
        <SidebarContent />
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-64">
        <Header title={titleForPath(location.pathname)} />

        <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-4 px-4 py-4 md:px-6 md:py-6">
          {!isEtf && dataMode === 'mock' ? <MockDataBanner /> : null}
          {!isEtf ? <ResearchStatusBanner /> : null}

          {!isEtf && error && !loading ? (
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
          {isEtf ? 'ETF Quant · 只读模拟账户观察；不是投资建议，没有券商或真实订单路径。' :
          '申万研究仪表盘 · 只读行业指数研究。正式研究产物是数据事实来源；本界面不能发起研究执行或交易。'}
        </footer>
      </div>
    </div>
  );
}

export function RootLayout() {
  const location=useLocation();
  return (
    <TooltipProvider delayDuration={200}>
      <AppDataProvider enabled={!location.pathname.startsWith('/etf-quant/')}>
        <EtfQuantProvider>
        <Shell />
        </EtfQuantProvider>
      </AppDataProvider>
    </TooltipProvider>
  );
}
