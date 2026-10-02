import { createRoute, Link } from '@tanstack/react-router';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { EmptyState } from '@/components/ui/states';

function NotFoundPage() {
  return (
    <div className="flex flex-col gap-4">
      <EmptyState
        title="页面不存在"
        description="本控制台提供 Research 与 ETF Shadow 只读观察，不提供研究执行或真实交易功能。"
      />
      <Link to="/" className="text-sm text-primary underline underline-offset-4">
        返回概览
      </Link>
    </div>
  );
}

export const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '$',
  validateSearch: parseExplorerSearch,
  component: NotFoundPage,
});
