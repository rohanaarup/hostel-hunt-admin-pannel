'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stayService } from '@/services/api';
import { useBillingConfig, useSaveBilling } from '@/hooks/queries';
import { errorMessage } from '@/services/errors';
import ErrorState from '@/components/ui/ErrorState';
import type { BillingRule, FirstPeriodPolicy } from '@/types';
import {
  DEFAULT_RULE, LIMITS, QUICK_DAYS, SAMPLE_JOINS, canPreview, previewRent, rentLabel, ruleFromConfig, toPayload, validateRule,
  type RuleErrors,
} from './billingRule';

/**
 * The AdminBilling board: choose when students pay, see what it does for four sample join dates, save. Used on the Billing
 * page and as the Billing section of the hostel form. The preview is asked from the server (POST /stays/billing/preview/):
 * this file never works out a date or an amount.
 */

const PREVIEW_DELAY_MS = 300;

const POLICIES: { key: FirstPeriodPolicy; title: string; text: string }[] = [
  { key: 'PRORATE', title: 'Prorate the first period', text: 'Charge only for the days from joining to the first fixed day.' },
  { key: 'FULL_MONTH', title: 'Charge the full month', text: 'Charge the whole rent for the first period, then the fixed day.' },
];

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

const card = (on: boolean): React.CSSProperties => ({
  background: on ? 'var(--color-primary-light)' : 'var(--color-surface)',
  border: `2px solid ${on ? 'var(--color-primary)' : 'var(--color-border)'}`,
  color: 'var(--color-text-primary)',
});
const pill = (on: boolean): React.CSSProperties =>
  on
    ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)', border: '1px solid var(--color-primary)' }
    : { background: 'var(--color-surface)', color: 'var(--color-text-primary)', border: '1px solid var(--color-border)' };

const fieldBox = 'w-full min-h-[44px] rounded-[10px] px-3.5 py-2.5 text-sm font-medium outline-none border';
const fieldStyle: React.CSSProperties = {
  background: 'var(--color-surface)', color: 'var(--color-text-primary)', borderColor: 'var(--color-border)',
};

interface Props {
  hostelId: string;
  /** Called after a successful save. */
  onSaved?: () => void;
}

export default function BillingRuleEditor({ hostelId, onSaved }: Props) {
  const config = useBillingConfig(hostelId);
  const save = useSaveBilling(hostelId);

  const [rule, setRule] = useState<BillingRule>(DEFAULT_RULE);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [joinIndex, setJoinIndex] = useState(0);
  const [showErrors, setShowErrors] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Take the server's rule once per hostel (never overwrite what the owner is typing).
  useEffect(() => {
    if (config.data && loadedFor !== config.data.hostel_id) {
      setRule(ruleFromConfig(config.data));
      setLoadedFor(config.data.hostel_id);
    }
  }, [config.data, loadedFor]);

  const errors: RuleErrors = useMemo(() => validateRule(rule), [rule]);
  const rent = previewRent(config.data);
  const previewBody = useMemo(() => {
    const payload = toPayload(rule);
    return {
      billing_mode: payload.billing_mode,
      fixed_due_day: payload.fixed_due_day,
      fixed_due_last_day: payload.fixed_due_last_day,
      first_period_policy: payload.first_period_policy,
      monthly_rent: rent ?? '',
      join_dates: SAMPLE_JOINS.map((j) => j.iso),
      count: 5,
    };
  }, [rule, rent]);
  const debouncedBody = useDebounced(previewBody, PREVIEW_DELAY_MS);
  const preview = useQuery({
    enabled: Boolean(debouncedBody.monthly_rent) && canPreview(rule),
    queryKey: ['stays', 'preview', debouncedBody],
    queryFn: () => stayService.previewBilling(debouncedBody as Parameters<typeof stayService.previewBilling>[0]),
    placeholderData: (previous) => previous,
    retry: false,
  });

  const change = (patch: Partial<BillingRule>) => {
    setSaved(false);
    setSaveError(null);
    setRule((current) => ({ ...current, ...patch }));
  };

  const chooseMode = (mode: BillingRule['billing_mode']) =>
    change(mode === 'ANNIVERSARY'
      ? { billing_mode: mode }
      : { billing_mode: mode, fixed_due_day: rule.fixed_due_day ?? (rule.fixed_due_last_day ? null : 1), first_period_policy: rule.first_period_policy ?? 'PRORATE' });

  const submit = () => {
    setShowErrors(true);
    if (Object.keys(errors).length > 0) return;
    save.mutate(toPayload(rule), {
      onSuccess: () => { setSaved(true); setSaveError(null); onSaved?.(); },
      onError: (error) => setSaveError(errorMessage(error)),
    });
  };

  if (config.error) {
    return <ErrorState error={config.error} what="the billing rule" onRetry={() => config.refetch()} retrying={config.isFetching} />;
  }
  if (config.isLoading || !config.data) {
    return <p role="status" className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading the billing rule…</p>;
  }

  const fixed = rule.billing_mode === 'FIXED_DAY';
  const shown = preview.data?.results?.[joinIndex];
  const err = (key: keyof BillingRule) => (showErrors ? errors[key] : undefined);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      {/* The rule */}
      <section aria-labelledby="rule-heading" className="space-y-5">
        <div>
          <h3 id="rule-heading" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
            Rent due date rule
          </h3>
          <div role="radiogroup" aria-labelledby="rule-heading" className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
            <button type="button" role="radio" aria-checked={!fixed} onClick={() => chooseMode('ANNIVERSARY')}
              className="text-left rounded-[14px] p-3.5" style={card(!fixed)}>
              <span className="flex items-center gap-2 font-semibold text-sm">
                Same day each month
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: 'var(--color-border)' }}>Default</span>
              </span>
              <span className="block text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                A student who joins on the 18th pays on the 18th of every month.
              </span>
            </button>
            <button type="button" role="radio" aria-checked={fixed} onClick={() => chooseMode('FIXED_DAY')}
              className="text-left rounded-[14px] p-3.5" style={card(fixed)}>
              <span className="font-semibold text-sm">Fixed day of the month</span>
              <span className="block text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                Everyone pays on the same day, for example the 1st. Used by a few hostels.
              </span>
            </button>
          </div>
        </div>

        {fixed ? (
          <>
            <fieldset>
              <legend className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Due day</legend>
              <div className="flex flex-wrap gap-2 mt-2 items-center">
                {QUICK_DAYS.map((day) => {
                  const on = !rule.fixed_due_last_day && rule.fixed_due_day === day;
                  return (
                    <button key={day} type="button" aria-pressed={on} onClick={() => change({ fixed_due_day: day, fixed_due_last_day: false })}
                      className="min-w-[48px] h-10 px-3.5 rounded-[10px] text-sm font-semibold" style={pill(on)}>
                      {day}
                    </button>
                  );
                })}
                <button type="button" aria-pressed={rule.fixed_due_last_day}
                  onClick={() => change({ fixed_due_day: null, fixed_due_last_day: true })}
                  className="h-10 px-3.5 rounded-[10px] text-sm font-semibold" style={pill(rule.fixed_due_last_day)}>
                  Last day
                </button>
                <label className="flex items-center gap-2 text-xs ml-1" style={{ color: 'var(--color-text-muted)' }}>
                  Other day
                  <input type="number" inputMode="numeric" min={LIMITS.fixedDay.min} max={LIMITS.fixedDay.max} aria-label="Other due day"
                    className="w-20 h-10 rounded-[10px] px-2 text-sm border" style={fieldStyle}
                    value={!rule.fixed_due_last_day && rule.fixed_due_day !== null && !QUICK_DAYS.includes(rule.fixed_due_day as never) ? rule.fixed_due_day : ''}
                    onChange={(e) => change({ fixed_due_last_day: false, fixed_due_day: e.target.value === '' ? null : Number(e.target.value) })} />
                </label>
              </div>
              {err('fixed_due_day') ? <p role="alert" className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{err('fixed_due_day')}</p> : null}
            </fieldset>

            <fieldset>
              <legend className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>First part-month</legend>
              <div role="radiogroup" aria-label="First part-month" className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
                {POLICIES.map((p) => (
                  <button key={p.key} type="button" role="radio" aria-checked={rule.first_period_policy === p.key}
                    onClick={() => change({ first_period_policy: p.key })} className="text-left rounded-[14px] p-3.5" style={card(rule.first_period_policy === p.key)}>
                    <span className="block font-semibold text-sm">{p.title}</span>
                    <span className="block text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>{p.text}</span>
                  </button>
                ))}
              </div>
              {err('first_period_policy') ? <p role="alert" className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{err('first_period_policy')}</p> : null}
            </fieldset>
          </>
        ) : null}

        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Monthly rent</dt>
            <dd className="mt-1 font-semibold" data-testid="monthly-rent">{rentLabel(config.data)}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Booking payment covers</dt>
            <dd className="mt-1 font-semibold">First period rent</dd>
          </div>
          <div>
            <label htmlFor="billing-window" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Payable window</label>
            <div className="flex items-center gap-2 mt-1">
              <input id="billing-window" type="number" inputMode="numeric" min={LIMITS.window.min} max={LIMITS.window.max} className={fieldBox + ' w-24'} style={fieldStyle}
                value={Number.isNaN(rule.payable_window_days) ? '' : rule.payable_window_days} aria-invalid={Boolean(err('payable_window_days'))}
                onChange={(e) => change({ payable_window_days: e.target.value === '' ? NaN : Number(e.target.value) })} />
              <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>days before due</span>
            </div>
            {err('payable_window_days') ? <p role="alert" className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{err('payable_window_days')}</p> : null}
          </div>
          <div>
            <label htmlFor="billing-grace" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>Grace period</label>
            <div className="flex items-center gap-2 mt-1">
              <input id="billing-grace" type="number" inputMode="numeric" min={LIMITS.grace.min} max={LIMITS.grace.max} className={fieldBox + ' w-24'} style={fieldStyle}
                value={Number.isNaN(rule.grace_days) ? '' : rule.grace_days} aria-invalid={Boolean(err('grace_days'))}
                onChange={(e) => change({ grace_days: e.target.value === '' ? NaN : Number(e.target.value) })} />
              <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>days</span>
            </div>
            {err('grace_days') ? <p role="alert" className="text-xs mt-1" style={{ color: 'var(--color-error)' }}>{err('grace_days')}</p> : null}
          </div>
        </dl>

        <div>
          <button type="button" onClick={submit} disabled={save.isPending}
            className="px-5 py-2.5 rounded-[10px] text-sm font-semibold disabled:opacity-60"
            style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}>
            {save.isPending ? 'Saving…' : 'Save billing rule'}
          </button>
          <p className="text-xs mt-2" style={{ color: 'var(--color-text-muted)' }}>
            Applies to new stays. Students already staying keep the rule they joined with.
          </p>
          {saved ? <p role="status" className="text-sm mt-2 font-semibold" style={{ color: 'var(--color-success)' }}>Billing rule saved. It applies to new stays only.</p> : null}
          {saveError ? <p role="alert" className="text-sm mt-2" style={{ color: 'var(--color-error)' }}>{saveError}</p> : null}
        </div>
      </section>

      {/* The preview */}
      <section aria-labelledby="preview-heading" className="space-y-3">
        <h3 id="preview-heading" className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
          Preview: a student joins on
        </h3>
        <div className="flex flex-wrap gap-2" role="group" aria-labelledby="preview-heading">
          {SAMPLE_JOINS.map((join, index) => (
            <button key={join.iso} type="button" aria-pressed={joinIndex === index} onClick={() => setJoinIndex(index)}
              className="h-10 px-3.5 rounded-[10px] text-sm font-semibold" style={pill(joinIndex === index)}>
              {join.label}
            </button>
          ))}
        </div>
        {!rent ? (
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Add a room with a price to see a preview.</p>
        ) : preview.error ? (
          <p role="alert" className="text-sm" style={{ color: 'var(--color-error)' }}>{errorMessage(preview.error)}</p>
        ) : !canPreview(rule) ? (
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Finish the rule to see the preview.</p>
        ) : !shown ? (
          <p role="status" className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Working out the preview…</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--color-border)' }}>
              <table className="w-full text-left text-sm" aria-label="Preview of due dates">
                <thead>
                  <tr>
                    {['Item', 'Rent period', 'Due on', 'Amount'].map((h) => (
                      <th key={h} scope="col" className="px-3 py-2 text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--color-text-muted)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {shown.rows.map((row) => (
                    <tr key={row.label} style={{ borderTop: '1px solid var(--color-border)' }}>
                      <td className="px-3 py-2 font-semibold">{row.label}</td>
                      <td className="px-3 py-2">{row.period}</td>
                      <td className="px-3 py-2">{row.due}</td>
                      <td className="px-3 py-2 font-semibold">{row.amount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p data-testid="preview-summary" className="text-sm" style={{ color: 'var(--color-text-muted)' }}>{shown.summary}</p>
          </>
        )}
      </section>
    </div>
  );
}
