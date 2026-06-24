import React, { useRef, useCallback } from 'react';
import type { ClipboardEvent, KeyboardEvent, ChangeEvent } from 'react';

interface OtpInputProps {
  length?: number;
  value: string;
  onChange: (val: string) => void;
  error?: boolean;
  disabled?: boolean;
}

export const OtpInput: React.FC<OtpInputProps> = ({
  length = 6,
  value,
  onChange,
  error = false,
  disabled = false,
}) => {
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);

  const digits = Array.from({ length }, (_, i) => value[i] ?? '');

  const focusAt = (idx: number) => {
    const el = inputsRef.current[idx];
    if (el) { el.focus(); el.select(); }
  };

  const updateValue = useCallback((next: string[]) => {
    onChange(next.join(''));
  }, [onChange]);

  const handleChange = (e: ChangeEvent<HTMLInputElement>, idx: number) => {
    const raw = e.target.value.replace(/\D/g, '');
    if (!raw) return;
    const char = raw[raw.length - 1]; // take last digit
    const next = [...digits];
    next[idx] = char;
    updateValue(next);
    if (idx < length - 1) focusAt(idx + 1);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>, idx: number) => {
    if (e.key === 'Backspace') {
      e.preventDefault();
      const next = [...digits];
      if (next[idx]) {
        next[idx] = '';
        updateValue(next);
      } else if (idx > 0) {
        next[idx - 1] = '';
        updateValue(next);
        focusAt(idx - 1);
      }
    } else if (e.key === 'ArrowLeft' && idx > 0) {
      focusAt(idx - 1);
    } else if (e.key === 'ArrowRight' && idx < length - 1) {
      focusAt(idx + 1);
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    const next = Array.from({ length }, (_, i) => pasted[i] ?? '');
    updateValue(next);
    focusAt(Math.min(pasted.length, length - 1));
  };

  const borderClass = error
    ? 'border-red-500/70 ring-2 ring-red-500/20 bg-red-500/5'
    : 'border-[#2A2A2A] focus:border-[#E8571A] focus:ring-[3px] focus:ring-[#E8571A]/20 bg-[#0F0F0F]';

  return (
    <div className="flex gap-3 justify-center">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={el => { inputsRef.current[i] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d}
          disabled={disabled}
          onChange={e => handleChange(e, i)}
          onKeyDown={e => handleKeyDown(e, i)}
          onPaste={handlePaste}
          onFocus={e => e.target.select()}
          className={`w-12 h-14 text-center text-xl font-bold text-white rounded-[10px] border outline-none transition-all duration-150 disabled:opacity-50 ${borderClass}`}
          aria-label={`OTP digit ${i + 1}`}
        />
      ))}
    </div>
  );
};
