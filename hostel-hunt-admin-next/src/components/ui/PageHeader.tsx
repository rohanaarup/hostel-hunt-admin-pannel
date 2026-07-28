'use client';

import React from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

/**
 * Shared page header — used at the top of every list page for consistency.
 * Single source of truth for the "title + subtitle + right-aligned actions" pattern.
 */
export default function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6 animate-fade-in-up">
      <div>
        <h1 className="text-[26px] font-bold tracking-tight text-ink-900 dark:text-ivory-50">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm font-medium text-ink-700 dark:text-ivory-400">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
