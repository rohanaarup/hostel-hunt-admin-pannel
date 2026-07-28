'use client';

import React, { useEffect, useState } from 'react';
import Icon, { IconName } from './Icon';

/**
 * Premium stat card.
 *  - Tone is a token-aligned palette entry (one of the 7 status tones).
 *  - Color is consumed via `currentColor` on the icon — no hardcoded hex.
 */

export type StatTone = 'primary' | 'success' | 'error' | 'warning' | 'info' | 'accent' | 'neutral';

interface StatCardProps {
  title: string;
  value: number | string;
  prefix?: string;
  suffix?: string;
  badge?: string;
  tone: StatTone;
  icon: IconName;
  loading?: boolean;
  delay?: number;
}

const TONE_STYLES: Record<StatTone, { bar: string; iconBox: string; iconColor: string; badge: string }> = {
  primary: {
    bar: 'bg-auburn-500',
    iconBox: 'bg-auburn-500/10',
    iconColor: 'text-auburn-500 dark:text-auburn-300',
    badge: 'bg-auburn-500/10 text-auburn-500 dark:text-auburn-300 border border-auburn-500/20',
  },
  success: {
    bar: 'bg-emerald-500',
    iconBox: 'bg-emerald-500/10',
    iconColor: 'text-emerald-500 dark:text-emerald-300',
    badge: 'bg-emerald-500/10 text-emerald-500 dark:text-emerald-300 border border-emerald-500/20',
  },
  error: {
    bar: 'bg-red-500',
    iconBox: 'bg-red-500/10',
    iconColor: 'text-red-500 dark:text-red-300',
    badge: 'bg-red-500/10 text-red-500 dark:text-red-300 border border-red-500/20',
  },
  warning: {
    bar: 'bg-amber-500',
    iconBox: 'bg-amber-500/10',
    iconColor: 'text-amber-500 dark:text-amber-300',
    badge: 'bg-amber-500/10 text-amber-500 dark:text-amber-300 border border-amber-500/20',
  },
  info: {
    bar: 'bg-blue-500',
    iconBox: 'bg-blue-500/10',
    iconColor: 'text-blue-500 dark:text-blue-300',
    badge: 'bg-blue-500/10 text-blue-500 dark:text-blue-300 border border-blue-500/20',
  },
  accent: {
    bar: 'bg-auburn-300',
    iconBox: 'bg-auburn-300/10',
    iconColor: 'text-auburn-300 dark:text-auburn-200',
    badge: 'bg-auburn-300/10 text-auburn-300 dark:text-auburn-200 border border-auburn-300/20',
  },
  neutral: {
    bar: 'bg-ivory-500',
    iconBox: 'bg-ivory-300/40 dark:bg-ivory-700/40',
    iconColor: 'text-ink-700 dark:text-ivory-300',
    badge: 'bg-ivory-300/50 dark:bg-ivory-700/50 text-ink-700 dark:text-ivory-300 border border-ivory-400/30 dark:border-ivory-600/30',
  },
};

const AnimatedNumber: React.FC<{ value: number | string; prefix?: string; suffix?: string }> = ({
  value, prefix = '', suffix = '',
}) => {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (typeof value !== 'number') { setDisplay(0); return; }
    let cur = 0;
    const steps = 36;
    const inc = value / steps;
    let raf: number;
    const tick = () => {
      cur += inc;
      if (cur >= value) { setDisplay(value); return; }
      setDisplay(Math.ceil(cur));
      raf = window.setTimeout(tick, 18) as unknown as number;
    };
    tick();
    return () => { if (raf) window.clearTimeout(raf); };
  }, [value]);
  if (typeof value !== 'number') return <>{value}</>;
  return <>{prefix}{display.toLocaleString('en-IN')}{suffix}</>;
};

export default function StatCard({
  title, value, prefix, suffix, badge, tone, icon, loading = false, delay = 0,
}: StatCardProps) {
  const t = TONE_STYLES[tone];
  return (
    <div
      className="group relative overflow-hidden rounded-2xl border border-ivory-300 dark:border-ivory-700 bg-ivory-50 dark:bg-ivory-900 p-5 transition-all duration-300 hover:border-auburn-500/40 dark:hover:border-auburn-300/40 hover:shadow-lg animate-fade-in-up"
      style={{ animationDelay: `${delay}ms` }}
    >
      {/* Color accent bar (left edge) */}
      <div className={`absolute top-0 left-0 w-1 h-full ${t.bar}`} aria-hidden="true" />

      <div className="pl-2">
        <div className="flex items-start justify-between gap-3 mb-3">
          <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-ink-700 dark:text-ivory-500">
            {title}
          </p>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${t.iconBox}`}>
            <Icon name={icon} className={`w-5 h-5 ${t.iconColor}`} />
          </div>
        </div>

        <div className="text-[30px] font-extrabold tracking-tight leading-none text-ink-900 dark:text-ivory-50 min-h-[36px]">
          {loading ? (
            <div className="h-7 w-24 rounded-md bg-ivory-300 dark:bg-ivory-700 animate-pulse" />
          ) : (
            <AnimatedNumber value={value} prefix={prefix} suffix={suffix} />
          )}
        </div>

        {badge && (
          <div className="mt-3">
            <span className={`inline-block text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md ${t.badge}`}>
              {badge}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
