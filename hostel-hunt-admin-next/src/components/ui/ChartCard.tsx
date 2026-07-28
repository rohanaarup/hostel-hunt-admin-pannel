'use client';

import React from 'react';
import Icon, { IconName } from './Icon';

/**
 * Card surface for charts. Header slot, content slot for the chart,
 * and a graceful "no data" empty state baked in.
 */

interface ChartCardProps {
  title: string;
  description?: string;
  icon?: IconName;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyMessage?: string;
  emptyIcon?: IconName;
  children: React.ReactNode;
  className?: string;
  /** Optional accent bar color (token class) */
  accentClass?: string;
}

export default function ChartCard({
  title,
  description,
  icon,
  isEmpty = false,
  emptyTitle = 'No data yet',
  emptyMessage = 'Once you have activity, you’ll see it visualized here.',
  emptyIcon = 'inbox',
  children,
  className = '',
  accentClass = 'bg-auburn-500',
}: ChartCardProps) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-ivory-300 dark:border-ivory-700 bg-ivory-50 dark:bg-ivory-900 p-5 transition-colors ${className}`}
    >
      <div className={`absolute top-0 left-0 w-1 h-full ${accentClass}`} aria-hidden="true" />

      <div className="pl-2 mb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-[14px] font-bold text-ink-900 dark:text-ivory-50">{title}</h3>
            {description && (
              <p className="text-[11px] text-ink-700 dark:text-ivory-500 mt-0.5">{description}</p>
            )}
          </div>
          {icon && (
            <div className="w-8 h-8 rounded-lg bg-auburn-500/10 flex items-center justify-center text-auburn-500 dark:text-auburn-300 flex-shrink-0">
              <Icon name={icon} className="w-4 h-4" />
            </div>
          )}
        </div>
      </div>

      <div className="pl-2">
        {isEmpty ? (
          <div className="py-10 flex flex-col items-center justify-center text-center">
            <div className="w-12 h-12 rounded-full bg-ivory-200 dark:bg-ivory-800 flex items-center justify-center text-ink-500 dark:text-ivory-400 mb-3">
              <Icon name={emptyIcon} className="w-6 h-6" />
            </div>
            <p className="text-[13px] font-bold text-ink-900 dark:text-ivory-50 mb-1">{emptyTitle}</p>
            <p className="text-[12px] text-ink-700 dark:text-ivory-500 max-w-[280px]">{emptyMessage}</p>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
