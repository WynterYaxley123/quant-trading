import { createRoute, Link } from '@tanstack/react-router';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { EmptyState } from '@/components/ui/states';

function NotFoundPage() {
  return (
    <div className="flex flex-col gap-4">
      <EmptyState
        title="页面不存在"
        description="本仪表盘仅提供研究页面，不提供交易、组合或执行功能。"
      />
      <Link to="/" className="text-sm text-primary underline underline-offset-4">
        返回概览
      </Link>
    </div>
  );
}

export const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '*',
  validateSearch: parseExplorerSearch,
  component: NotFoundPage,
});
