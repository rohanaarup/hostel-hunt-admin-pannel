'use client';

import React from 'react';
import Icon, { IconName } from './Icon';

interface EmptyStateProps {
  icon?: IconName;
  title: string;
  message?: string;
  action?: React.ReactNode;
}

/**
 * Reusable empty state. Used on every list page when there's no data.
 */
export default function EmptyState({
  icon = 'inbox',
  title,
  message,
  action,
}: EmptyStateProps) {
  return (
    <div className="py-16 px-6 text-center bg-ivory-50 dark:bg-ivory-900 border border-ivory-300 dark:border-ivory-700 border-dashed rounded-2xl">
      <div className="w-14 h-14 rounded-full bg-ivory-200/60 dark:bg-ivory-800/60 flex items-center justify-center mx-auto mb-4 text-ink-500 dark:text-ivory-400">
        <Icon name={icon} className="w-7 h-7" />
      </div>
      <p className="text-[15px] font-bold text-ink-900 dark:text-ivory-50 mb-1">{title}</p>
      {message && (
        <p className="text-[13px] text-ink-700 dark:text-ivory-500 max-w-sm mx-auto">{message}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
