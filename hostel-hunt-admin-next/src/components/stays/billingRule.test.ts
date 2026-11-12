import { describe, expect, it } from 'vitest';
import type { BillingRule } from '@/types';
import { DEFAULT_RULE, canPreview, previewRent, rentLabel, toPayload, validateRule } from './billingRule';

const fixed = (over: Partial<BillingRule> = {}): BillingRule => ({
  billing_mode: 'FIXED_DAY', fixed_due_day: 1, fixed_due_last_day: false, first_period_policy: 'PRORATE',
  payable_window_days: 7, grace_days: 0, ...over,
});

describe('the billing rule form checks', () => {
  it('accepts the default rule and a complete fixed-day rule', () => {
    expect(validateRule(DEFAULT_RULE)).toEqual({});
    expect(validateRule(fixed())).toEqual({});
    expect(validateRule(fixed({ fixed_due_day: null, fixed_due_last_day: true }))).toEqual({});
  });

  it('a fixed-day rule needs a due day from 1 to 28, or the last day', () => {
    expect(validateRule(fixed({ fixed_due_day: null })).fixed_due_day).toMatch(/1 to 28/);
    for (const day of [0, 29, -3, 1.5]) {
      expect(validateRule(fixed({ fixed_due_day: day })).fixed_due_day, String(day)).toBeTruthy();
    }
    for (const day of [1, 14, 28]) expect(validateRule(fixed({ fixed_due_day: day })).fixed_due_day).toBeUndefined();
  });

  it('a day and the last-day option together are refused', () => {
    expect(validateRule(fixed({ fixed_due_day: 5, fixed_due_last_day: true })).fixed_due_day).toMatch(/not both/);
  });

  it('the first part-month policy is needed only for a fixed day', () => {
    expect(validateRule(fixed({ first_period_policy: null })).first_period_policy).toBeTruthy();
    expect(validateRule({ ...DEFAULT_RULE, first_period_policy: null })).toEqual({});
  });

  it('the payable window is 1 to 15 days and the grace period 0 to 15 days', () => {
    for (const w of [0, 16, NaN, 2.5]) expect(validateRule({ ...DEFAULT_RULE, payable_window_days: w }).payable_window_days, String(w)).toBeTruthy();
    for (const w of [1, 7, 15]) expect(validateRule({ ...DEFAULT_RULE, payable_window_days: w }).payable_window_days).toBeUndefined();
    for (const g of [-1, 16, NaN]) expect(validateRule({ ...DEFAULT_RULE, grace_days: g }).grace_days, String(g)).toBeTruthy();
    for (const g of [0, 15]) expect(validateRule({ ...DEFAULT_RULE, grace_days: g }).grace_days).toBeUndefined();
  });

  it('an anniversary payload carries no day and no policy; a last-day payload carries no day number', () => {
    expect(toPayload({ ...fixed(), billing_mode: 'ANNIVERSARY' })).toEqual({
      billing_mode: 'ANNIVERSARY', fixed_due_day: null, fixed_due_last_day: false, first_period_policy: null,
      payable_window_days: 7, grace_days: 0,
    });
    expect(toPayload(fixed({ fixed_due_day: 5, fixed_due_last_day: true })).fixed_due_day).toBeNull();
    expect(toPayload(fixed({ fixed_due_day: 5 })).fixed_due_day).toBe(5);
  });

  it('a preview is asked for only when the part that decides the dates is complete', () => {
    expect(canPreview(DEFAULT_RULE)).toBe(true);
    expect(canPreview(fixed())).toBe(true);
    expect(canPreview(fixed({ fixed_due_day: null }))).toBe(false);
    expect(canPreview(fixed({ first_period_policy: null }))).toBe(false);
    expect(canPreview(fixed({ grace_days: 99 }))).toBe(true);
  });

  it('shows the monthly rent as the rooms give it and previews with the lowest price', () => {
    const config = (monthly_rent: { min: string; max: string } | null) => ({ monthly_rent }) as never;
    expect(rentLabel(config({ min: '6000.00', max: '6000.00' }))).toBe('₹6,000');
    expect(rentLabel(config({ min: '5200.00', max: '9500.00' }))).toBe('₹5,200 to ₹9,500');
    expect(rentLabel(config(null))).toBe('No rooms yet');
    expect(previewRent(config({ min: '5200.00', max: '9500.00' }))).toBe('5200.00');
    expect(previewRent(config(null))).toBeNull();
  });
});
