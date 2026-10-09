import { createRoute } from '@tanstack/react-router';
import { rootRoute } from './rootRoute';
import { IndustryForecastPage } from '@/industry-forecast/Page';
import { Rev10Page } from '@/industry-forecast/Rev10Page';

export const industryForecastRoute=createRoute({getParentRoute:()=>rootRoute,path:'/',component:IndustryForecastPage});
export const industryForecastAlias=createRoute({getParentRoute:()=>rootRoute,path:'/industry-forecast',component:IndustryForecastPage});
export const rev10Route=createRoute({getParentRoute:()=>rootRoute,path:'/industry-forecast/swl1-rev10',component:Rev10Page});
