import { useState } from 'react';
import { Menu, X } from 'lucide-react';
import { SidebarContent } from './Sidebar';
import { ThemeToggle } from './ThemeToggle';
import { useAppData } from './AppDataProvider';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';

export function Header({ title }: { title: string }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { dataMode } = useAppData();

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={() => setMenuOpen(true)}
        aria-label="打开导航菜单"
      >
        <Menu aria-hidden="true" />
      </Button>

      <h1 className="truncate text-base font-semibold tracking-tight">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        {dataMode === 'mock' ? (
          <span
            className="rounded-full border border-warning/50 bg-warning/10 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-warning-foreground dark:text-warning"
            title="当前使用合成测试数据"
          >
            模拟数据
          </span>
        ) : (
          <span
            className="rounded-full border border-border px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
            title="当前使用只读研究数据接口"
          >
            正式数据接口
          </span>
        )}
        <ThemeToggle />
      </div>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent side="right" aria-label="导航">
          <DialogTitle className="sr-only">导航</DialogTitle>
          <div className="flex h-full items-start justify-between">
            <div className="flex-1 overflow-y-auto">
              <SidebarContent onNavigate={() => setMenuOpen(false)} />
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="mt-4 mr-2"
              onClick={() => setMenuOpen(false)}
              aria-label="关闭导航菜单"
            >
              <X aria-hidden="true" />
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </header>
  );
}
