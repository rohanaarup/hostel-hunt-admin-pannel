'use client';

import React from 'react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
} from 'recharts';
import { useTheme } from '@/contexts/ThemeContext';

/**
 * Token-aligned chart palette. Each value references a Tailwind color token
 * — the actual hex is centralized in globals.css.
 *
 * Order is intentional: warm primary, then 4–6 supporting tones
 * for category distinction.
 */
export const CHART_TOKENS = [
  'var(--color-auburn-500)',
  'var(--color-emerald-500)',
  'var(--color-auburn-300)',
  'var(--color-ink-700)',
  'var(--color-auburn-700)',
  'var(--color-emerald-700)',
];

const CHART_TOKENS_DARK = [
  'var(--color-auburn-300)',
  'var(--color-emerald-300)',
  'var(--color-auburn-200)',
  'var(--color-ivory-500)',
  'var(--color-auburn-100)',
  'var(--color-emerald-100)',
];

/** Reads the active theme's token list. */
function useChartPalette() {
  const { theme } = useTheme();
  return theme === 'dark' ? CHART_TOKENS_DARK : CHART_TOKENS;
}

const TooltipBox: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-lg border border-ivory-300 dark:border-ivory-700 bg-ivory-50 dark:bg-ivory-900 px-3 py-2 shadow-lg">
      {label != null && (
        <p className="text-[10px] font-bold uppercase tracking-wider text-ink-700 dark:text-ivory-500 mb-1">
          {label}
        </p>
      )}
      {payload.map((entry: any, i: number) => (
        <p key={i} className="text-[12px] font-semibold text-ink-900 dark:text-ivory-50">
          <span
            className="inline-block w-2 h-2 rounded-full mr-2 align-middle"
            style={{ backgroundColor: entry.color }}
          />
          {entry.name}: <span className="font-extrabold">{entry.value}</span>
        </p>
      ))}
    </div>
  );
};

/* ─── Donut: occupancy / status / payment-mode ─────────────────────────────── */

interface DonutProps {
  data: { name: string; value: number }[];
  size?: number;
  innerRadius?: number;
  showLegend?: boolean;
  showLabels?: boolean;
}

export function Donut({ data, size = 180, innerRadius = 55, showLegend = true, showLabels = false }: DonutProps) {
  const palette = useChartPalette();
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <div>
      <div className="relative" style={{ width: size, height: size, margin: '0 auto' }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={innerRadius}
              outerRadius={size / 2 - 4}
              paddingAngle={2}
              dataKey="value"
              stroke="transparent"
              label={showLabels ? ({ percent }: any) => `${Math.round(percent * 100)}%` : undefined}
              labelLine={false}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={palette[i % palette.length]} />
              ))}
            </Pie>
            <Tooltip content={<TooltipBox />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-[20px] font-extrabold text-ink-900 dark:text-ivory-50">{total.toLocaleString('en-IN')}</p>
          <p className="text-[10px] font-bold uppercase tracking-wider text-ink-700 dark:text-ivory-500">Total</p>
        </div>
      </div>
      {showLegend && (
        <div className="mt-3 grid grid-cols-2 gap-1.5 text-[11px]">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center gap-2 min-w-0">
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: palette[i % palette.length] }}
              />
              <span className="truncate text-ink-700 dark:text-ivory-400">
                <span className="font-bold text-ink-900 dark:text-ivory-50 mr-1">{d.value}</span>
                {d.name}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Bar: payment mode split, monthly counts, etc. ─────────────────────────── */

interface BarSeries {
  dataKey: string;
  name: string;
}

interface SimpleBarProps {
  data: Record<string, any>[];
  xKey: string;
  series: BarSeries[];
  height?: number;
}

export function SimpleBar({ data, xKey, series, height = 220 }: SimpleBarProps) {
  const palette = useChartPalette();
  const { theme } = useTheme();
  const axis = theme === 'dark' ? '#C4B7A6' : '#5A3D34';
  const grid = theme === 'dark' ? '#3A312B' : '#EFE3D6';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: axis, fontSize: 11, fontWeight: 600 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: axis, fontSize: 11, fontWeight: 600 }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(165, 42, 42, 0.05)' }} />
        {series.map((s, i) => (
          <Bar key={s.dataKey} dataKey={s.dataKey} name={s.name} fill={palette[i % palette.length]} radius={[6, 6, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ─── Line: revenue trend ──────────────────────────────────────────────────── */

interface SimpleLineProps {
  data: Record<string, any>[];
  xKey: string;
  yKey: string;
  height?: number;
  yLabel?: string;
}

export function SimpleLine({ data, xKey, yKey, height = 240, yLabel }: SimpleLineProps) {
  const palette = useChartPalette();
  const stroke = palette[0];
  const { theme } = useTheme();
  const axis = theme === 'dark' ? '#C4B7A6' : '#5A3D34';
  const grid = theme === 'dark' ? '#3A312B' : '#EFE3D6';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid stroke={grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={xKey} tick={{ fill: axis, fontSize: 11, fontWeight: 600 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: axis, fontSize: 11, fontWeight: 600 }} axisLine={false} tickLine={false} allowDecimals={false} label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', style: { fill: axis, fontSize: 11, fontWeight: 600 } } : undefined} />
        <Tooltip content={<TooltipBox />} cursor={{ stroke: stroke, strokeWidth: 1, strokeDasharray: '3 3' }} />
        <Line
          type="monotone"
          dataKey={yKey}
          stroke={stroke}
          strokeWidth={3}
          dot={{ r: 4, strokeWidth: 2, fill: '#fff', stroke }}
          activeDot={{ r: 6, strokeWidth: 2, fill: stroke, stroke: '#fff' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
