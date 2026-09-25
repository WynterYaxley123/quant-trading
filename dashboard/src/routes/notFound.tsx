import { createRoute, Link } from '@tanstack/react-router';
import { rootRoute } from './rootRoute';
import { parseExplorerSearch } from './searchParams';
import { EmptyState } from '@/components/ui/states';

function NotFoundPage() {
  return (
    <div className="flex flex-col gap-4">
      <EmptyState
        title="Page not found"
        description="This dashboard only contains research sections. Trading, portfolio and execution pages do not exist here by design."
      />
      <Link to="/" className="text-sm text-primary underline underline-offset-4">
        Back to Overview
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
