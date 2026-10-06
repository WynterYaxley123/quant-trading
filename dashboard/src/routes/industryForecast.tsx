import { createRoute } from '@tanstack/react-router';
import { rootRoute } from './rootRoute';
import { IndustryForecastPage } from '@/industry-forecast/Page';

export const industryForecastRoute=createRoute({getParentRoute:()=>rootRoute,path:'/',component:IndustryForecastPage});
export const industryForecastAlias=createRoute({getParentRoute:()=>rootRoute,path:'/industry-forecast',component:IndustryForecastPage});
