'use client';

import React, { forwardRef } from 'react';

/**
 * Shared input primitives. All variants consume the central design token
 * system — `--color-surface`, `--color-border`, `--color-text-primary`,
 * `--color-primary` — so dark mode is correct by default.
 *
 * Before this component existed, every page inlined its own
 * `style={{ background: 'var(--color-background)' ... }}` on raw
 * `<input>` elements. Two problems:
 *  1. The background and border used `var(--color-background)` /
 *     `var(--color-border)` (instead of `--color-surface` for inputs),
 *     which gave poor contrast against the surrounding card.
 *  2. The token for placeholder / native browser chrome wasn't applied
 *     uniformly, so on some forms dark-mode inputs still rendered with
 *     browser-default light styling bleeding through.
 *
 * Use these everywhere new. The legacy `inputClass` / `selectClass` /
 * `textareaClass` helpers in `FormField.tsx` remain for backwards
 * compatibility and now delegate to the same token set.
 */

const baseFieldClass = [
  'w-full min-h-[44px] rounded-[10px] px-3.5 py-2.5 text-sm font-medium outline-none',
  'transition-all duration-150',
  'border focus:ring-[3px]',
  // Background + text (Using CSS variables ensures it works instantly with the global theme toggle)
  'bg-[var(--color-surface)] text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)]',
  // Default border + focus styling
  'border-[var(--color-border)]',
  'focus:border-[var(--color-primary)] focus:ring-[var(--color-primary)]/20',
  // Native form chrome (date/time pickers) in dark mode
  'color-scheme:light dark:color-scheme:dark',
].join(' ');

const errorFieldClass = [
  'border-[var(--color-error)]',
  'ring-2 ring-[var(--color-error)]/20',
].join(' ');

interface CommonProps {
  hasError?: boolean;
  className?: string;
  id?: string;
  name?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  'aria-invalid'?: boolean;
}

const compose = (hasError?: boolean, extra?: string) =>
  [baseFieldClass, hasError ? errorFieldClass : '', extra ?? ''].filter(Boolean).join(' ');

export const Input = forwardRef<HTMLInputElement, CommonProps & React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ hasError, className = '', ...rest }, ref) {
    return <input ref={ref} className={compose(hasError, className)} {...rest} />;
  }
);

export const Textarea = forwardRef<HTMLTextAreaElement, CommonProps & React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ hasError, className = '', ...rest }, ref) {
    const cls = compose(hasError, ['resize-none', className].join(' '));
    return <textarea ref={ref} className={cls} {...rest} />;
  }
);

interface SelectProps extends CommonProps {
  options?: { value: string; label: string }[];
  children?: React.ReactNode;
  value?: string;
  onChange?: React.ChangeEventHandler<HTMLSelectElement>;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'value'>>(
  function Select({ hasError, className = '', options, children, ...rest }, ref) {
    const cls = compose(hasError, ['appearance-none cursor-pointer pr-9', className].join(' '));
    return (
      <select ref={ref} className={cls} {...rest}>
        {children ? children : options?.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    );
  }
);

interface FieldGroupProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  htmlFor?: string;
  className?: string;
  children: React.ReactNode;
}

/** Label + control + error/hint — small wrapper, mirrors <FormField>. */
export function FieldGroup({ label, hint, error, required, htmlFor, className = '', children }: FieldGroupProps) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label htmlFor={htmlFor} className="text-[13px] font-semibold text-ink-700 dark:text-ivory-500 flex items-center gap-1">
        {label}
        {required && <span className="text-auburn-500 dark:text-auburn-300">*</span>}
      </label>
      {children}
      {hint && !error && (
        <p className="text-[11px] text-ink-700 dark:text-ivory-500 font-medium">{hint}</p>
      )}
      {error && (
        <p className="text-[11px] text-red-500 dark:text-red-400 font-medium">{error}</p>
      )}
    </div>
  );
}
