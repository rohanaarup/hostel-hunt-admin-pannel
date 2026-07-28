'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AuthLayout from '@/components/auth/AuthLayout';
import { useAuth } from '@/contexts/AuthContext';
import { authService } from '@/services/api';
import type { IdentifierType } from '@/types';

type Field = 'identifier' | 'password' | null;

const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const phoneRegex = /^[6-9]\d{9}$/;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();

  const [identifierType, setIdentifierType] = useState<IdentifierType>('email');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState<Set<Field>>(new Set());

  const touch = (f: Field) => setTouched(p => new Set([...p, f]));

  const identifierError = (() => {
    if (!touched.has('identifier')) return '';
    if (!identifier) return 'This field is required';
    if (identifierType === 'email' && !emailRegex.test(identifier)) return 'Enter a valid email address';
    if (identifierType === 'phone' && !phoneRegex.test(identifier.replace(/\s/g, ''))) return 'Enter a valid 10-digit phone number';
    return '';
  })();

  const passwordError = (() => {
    if (!touched.has('password')) return '';
    if (!password) return 'Password is required';
    if (password.length < 6) return 'Password must be at least 6 characters';
    return '';
  })();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    touch('identifier');
    touch('password');
    if (identifierError || passwordError || !identifier || !password) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const response = await authService.login({
        identifier,
        identifier_type: identifierType,
        password,
        remember_me: rememberMe
      });

      login(response.data.user, response.data.tokens, rememberMe);
      router.push('/dashboard');
    } catch (err: any) {
      if (!err.response) {
        setError('Cannot connect to backend server. Is it running?');
      } else if (err.response?.data?.errors?.detail) {
        const detail = err.response.data.errors.detail;
        setError(Array.isArray(detail) ? detail[0] : detail);
      } else if (err.response?.data?.errors) {
        const errors = err.response.data.errors;
        const firstError = Object.values(errors)[0];
        setError(Array.isArray(firstError) ? firstError[0] : (firstError as string));
      } else if (err.response?.data?.message) {
        setError(err.response.data.message);
      } else {
        setError('Invalid credentials. Please check and try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputBase = (hasError: boolean) =>
    `w-full bg-ivory-50 dark:bg-ivory-900 border rounded-[10px] px-4 py-3 text-ink-900 dark:text-ivory-50 placeholder-ink-700 dark:placeholder-ivory-500 outline-none transition-all duration-150 font-medium text-sm ${
      hasError
        ? 'border-error/60 ring-2 ring-error/20'
        : 'border-ivory-300 dark:border-ivory-700 focus:border-auburn-500 dark:focus:border-auburn-300 focus:ring-[3px] focus:ring-auburn-500/20 dark:focus:ring-auburn-300/20'
    }`;

  return (
    <AuthLayout heroTitle={'Manage your hostel\nwith confidence'}>
      <div className="bg-ivory-100 dark:bg-ivory-900/80 rounded-2xl border border-ivory-300 dark:border-ivory-700 p-8 shadow-2xl relative overflow-hidden glass-card">
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-auburn-500/5 dark:bg-auburn-300/5 rounded-full blur-[80px] pointer-events-none" />

        <div className="mb-7 relative z-10">
          <h2 className="text-2xl font-bold text-ink-900 dark:text-ivory-50 tracking-tight">Welcome back</h2>
          <p className="text-ink-700 dark:text-ivory-500 mt-1.5 text-sm font-medium">Sign in to your owner account</p>
        </div>

        {error && (
          <div className="mb-5 bg-error/10 border border-error/20 text-error text-sm rounded-lg p-3 flex gap-2 items-start">
            <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 relative z-10" noValidate>
          <div className="flex bg-ivory-50 dark:bg-ink-900 rounded-[10px] p-1 border border-ivory-300 dark:border-ivory-700">
            {(['email', 'phone'] as IdentifierType[]).map(t => (
              <button
                key={t}
                type="button"
                onClick={() => { setIdentifierType(t); setIdentifier(''); }}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-[8px] capitalize transition-all duration-200 ${
                  identifierType === t
                    ? 'bg-auburn-500 text-ivory-50 dark:bg-auburn-300 dark:text-ink-900 shadow'
                    : 'text-ink-700 dark:text-ivory-500 hover:text-ink-900 dark:hover:text-ivory-50'
                }`}
              >
                {t === 'email' ? '✉ Email' : '📱 Phone'}
              </button>
            ))}
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-ink-700 dark:text-ivory-500 mb-1.5">
              {identifierType === 'email' ? 'Email address' : 'Phone number'}
            </label>
            <input
              type={identifierType === 'email' ? 'email' : 'tel'}
              value={identifier}
              onChange={e => setIdentifier(e.target.value)}
              onBlur={() => touch('identifier')}
              className={inputBase(!!identifierError)}
              placeholder={identifierType === 'email' ? 'owner@example.com' : '9876543210'}
              autoComplete={identifierType === 'email' ? 'email' : 'tel'}
            />
            {identifierError && (
              <p className="text-[11px] text-error mt-1 font-medium">{identifierError}</p>
            )}
          </div>

          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="text-[12px] font-semibold text-ink-700 dark:text-ivory-500">Password</label>
              <Link
                href="/forgot-password"
                className="text-[11px] text-auburn-500 hover:text-auburn-700 dark:text-auburn-300 dark:hover:text-auburn-100 font-medium transition-colors"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                onBlur={() => touch('password')}
                className={`${inputBase(!!passwordError)} pr-11`}
                placeholder="••••••••"
                autoComplete="current-password"
              />
              <button
                type="button"
                tabIndex={-1}
                onClick={() => setShowPassword(p => !p)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-700/50 hover:text-ink-700 dark:text-ivory-500/50 dark:hover:text-ivory-500 transition-colors p-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
            {passwordError && (
              <p className="text-[11px] text-error mt-1 font-medium">{passwordError}</p>
            )}
          </div>

          <label className="flex items-center gap-2.5 cursor-pointer group">
            <div
              onClick={() => setRememberMe(p => !p)}
              className={`w-4 h-4 rounded border flex items-center justify-center transition-all flex-shrink-0 ${
                rememberMe ? 'bg-auburn-500 border-auburn-500 dark:bg-auburn-300 dark:border-auburn-300' : 'border-ivory-300 dark:border-ivory-700 group-hover:border-auburn-500/50 dark:group-hover:border-auburn-300/50'
              }`}
            >
              {rememberMe && (
                <svg className="w-2.5 h-2.5 text-ivory-50 dark:text-ink-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </div>
            <input type="checkbox" className="hidden" checked={rememberMe} onChange={() => {}} />
            <span className="text-[12px] text-ink-700 dark:text-ivory-500 group-hover:text-ink-900 dark:group-hover:text-ivory-50 transition-colors font-medium">Remember me for 30 days</span>
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-auburn-500 hover:bg-auburn-700 dark:bg-auburn-300 dark:hover:bg-auburn-100 text-ivory-50 dark:text-ink-900 font-semibold py-3 rounded-[10px] transition-all duration-200 auburn-glow disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-2"
          >
            {isSubmitting ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Signing in...
              </>
            ) : 'Sign In'}
          </button>
        </form>

        <div className="mt-6 text-center text-[13px] text-ink-700 dark:text-ivory-500 font-medium relative z-10">
          Don't have an account?{' '}
          <Link href="/signup" className="text-auburn-500 hover:text-auburn-700 dark:text-auburn-300 dark:hover:text-auburn-100 transition-colors font-semibold">
            Create account
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
