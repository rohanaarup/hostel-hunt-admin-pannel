'use client';

import React from 'react';

interface FormFieldProps {
  label: string;
  error?: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

export default function FormField({
  label,
  error,
  required,
  hint,
  children,
  className = '',
}: FormFieldProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label className="text-[13px] font-semibold text-ink-700 dark:text-ivory-500 flex items-center gap-1">
        {label}
        {required && <span className="text-auburn-500 dark:text-auburn-300">*</span>}
      </label>
      {children}
      {hint && !error && (
        <p className="text-[11px] text-ink-700 dark:text-ivory-500 font-medium">{hint}</p>
      )}
      {error && (
        <p className="text-[11px] text-red-400 font-medium flex items-center gap-1">
          <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          {error}
        </p>
      )}
    </div>
  );
}

// ── Shared input class helper ──────────────────────────────────────────────────
// Kept as aliases to preserve existing call sites. The single source of truth
// is now `<Input />`, `<Textarea />`, `<Select />` in `./Input.tsx`, which all
// share the same token-aligned, dark-mode-correct styling.
export const inputClass = (hasError?: boolean) => {
  // Local re-derivation: keep it in lockstep with the Input component.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const err = hasError
    ? 'border-red-500/60 dark:border-red-400/60 ring-2 ring-red-500/20'
    : 'border-ivory-300 focus:border-auburn-500 focus:ring-[3px] focus:ring-auburn-500/20 dark:border-ivory-700 dark:focus:border-auburn-300 dark:focus:ring-auburn-300/20';
  return `w-full min-h-[44px] bg-ivory-50 dark:bg-ivory-950 ${err} rounded-[10px] px-3.5 py-2.5 text-ink-900 dark:text-ivory-50 placeholder-ink-700/50 dark:placeholder-ivory-500/50 outline-none transition-all duration-150 font-medium text-sm color-scheme:light dark:color-scheme:dark`;
};

export const selectClass = (hasError?: boolean) =>
  `${inputClass(hasError)} appearance-none cursor-pointer pr-9`;

export const textareaClass = (hasError?: boolean) =>
  `${inputClass(hasError)} resize-none`;
