import React from 'react';

interface FormFieldProps {
  label: string;
  error?: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  error,
  required,
  hint,
  children,
  className = '',
}) => (
  <div className={`flex flex-col gap-1.5 ${className}`}>
    <label className="text-[13px] font-semibold text-[#9A9690] flex items-center gap-1">
      {label}
      {required && <span className="text-[#E8571A]">*</span>}
    </label>
    {children}
    {hint && !error && (
      <p className="text-[11px] text-[#4A4A4A] font-medium">{hint}</p>
    )}
    {error && (
      <p className="text-[11px] text-red-400 font-medium flex items-center gap-1">
        <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        {error}
      </p>
    )}
  </div>
);

// ── Shared input class helper ──────────────────────────────────────────────────
export const inputClass = (hasError?: boolean) =>
  `w-full bg-[#0F0F0F] border rounded-[10px] px-4 py-3 text-white placeholder-[#3A3A3A] outline-none transition-all duration-150 font-medium text-sm ${
    hasError
      ? 'border-red-500/60 ring-2 ring-red-500/20'
      : 'border-[#2A2A2A] focus:border-[#E8571A] focus:ring-[3px] focus:ring-[#E8571A]/20'
  }`;

export const selectClass = (hasError?: boolean) =>
  `w-full bg-[#0F0F0F] border rounded-[10px] px-4 py-3 text-white outline-none transition-all duration-150 font-medium text-sm appearance-none cursor-pointer ${
    hasError
      ? 'border-red-500/60 ring-2 ring-red-500/20'
      : 'border-[#2A2A2A] focus:border-[#E8571A] focus:ring-[3px] focus:ring-[#E8571A]/20'
  }`;

export const textareaClass = (hasError?: boolean) =>
  `w-full bg-[#0F0F0F] border rounded-[10px] px-4 py-3 text-white placeholder-[#3A3A3A] outline-none transition-all duration-150 font-medium text-sm resize-none ${
    hasError
      ? 'border-red-500/60 ring-2 ring-red-500/20'
      : 'border-[#2A2A2A] focus:border-[#E8571A] focus:ring-[3px] focus:ring-[#E8571A]/20'
  }`;
