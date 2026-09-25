import * as React from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';

/**
 * Native `<select>` with shadcn-style visuals. Native selects keep full
 * keyboard/screen-reader behaviour without extra dependencies.
 */

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hideLabel?: boolean;
  options: ReadonlyArray<{ value: string; label: string }>;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, hideLabel = false, options, id, ...props }, ref) => {
    const generatedId = React.useId();
    const selectId = id ?? generatedId;
    return (
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={selectId}
          className={cn(
            'text-xs font-semibold uppercase tracking-wide text-muted-foreground',
            hideLabel && 'sr-only',
          )}
        >
          {label}
        </label>
        <div className="relative">
          <select
            id={selectId}
            ref={ref}
            className={cn(
              'h-9 w-full appearance-none rounded-md border border-input bg-card px-3 pr-9 text-sm text-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
              className,
            )}
            {...props}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown
            aria-hidden="true"
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
        </div>
      </div>
    );
  },
);
Select.displayName = 'Select';
