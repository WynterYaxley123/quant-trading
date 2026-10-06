import { createRouter, type Router, type RouterHistory } from '@tanstack/react-router';
import { rootRoute } from '@/routes/rootRoute';
import { overviewRoute } from '@/routes/overview';
import { candidatesRoute } from '@/routes/candidates';
import { developmentRoute } from '@/routes/development';
import { sectorsRoute } from '@/routes/sectors';
import { diagnosticsRoute } from '@/routes/diagnostics';
import { integrityRoute } from '@/routes/integrity';
import { notFoundRoute } from '@/routes/notFound';
import { etfQuantRoutes } from '@/routes/etfQuant';
import { industryForecastRoute, industryForecastAlias } from '@/routes/industryForecast';

const routeTree = rootRoute.addChildren([
  industryForecastRoute,
  industryForecastAlias,
  overviewRoute,
  candidatesRoute,
  developmentRoute,
  sectorsRoute,
  diagnosticsRoute,
  integrityRoute,
  ...etfQuantRoutes,
  notFoundRoute,
]);

export type AppRouter = Router<typeof routeTree>;

/**
 * Fresh router factory (config-based TanStack Router). Tests create isolated
 * instances with a memory history; the app uses browser history by default.
 */
export function createAppRouter(history?: RouterHistory): AppRouter {
  return createRouter({
    routeTree,
    ...(history ? { history } : {}),
    defaultPreload: 'intent',
  });
}

declare module '@tanstack/react-router' {
  interface Register {
    router: AppRouter;
  }
}
