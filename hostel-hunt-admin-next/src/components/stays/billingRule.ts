import type { BillingConfig, BillingRule } from '@/types';

/**
 * The rent rule as the form holds it, and the checks the form makes BEFORE it asks the server. The server checks the same
 * things again (and is the one that decides); these checks only save a round trip and say what is wrong in plain words.
 * There is no billing arithmetic here: dates and amounts come from POST /stays/billing/preview/.
 */

export const LIMITS = {
  fixedDay: { min: 1, max: 28 },
  window: { min: 1, max: 15 },
  grace: { min: 0, max: 15 },
} as const;

/** The four join dates of the AdminBilling board. The preview is asked for exactly these. */
export const SAMPLE_JOINS = [
  { label: '18 Sep 2026', iso: '2026-09-18' },
  { label: '31 Jan 2027', iso: '2027-01-31' },
  { label: '1 Sep 2026', iso: '2026-09-01' },
  { label: '5 Sep 2026', iso: '2026-09-05' },
] as const;

/** The quick due-day choices on the board; any day from 1 to 28 can be typed as well. */
export const QUICK_DAYS = [1, 5, 10, 15] as const;

export const DEFAULT_RULE: BillingRule = {
  billing_mode: 'ANNIVERSARY',
  fixed_due_day: null,
  fixed_due_last_day: false,
  first_period_policy: null,
  payable_window_days: 7,
  grace_days: 0,
};

export type RuleErrors = Partial<Record<keyof BillingRule, string>>;

export function ruleFromConfig(config: BillingConfig): BillingRule {
  return {
    billing_mode: config.billing_mode,
    fixed_due_day: config.fixed_due_day,
    fixed_due_last_day: config.fixed_due_last_day,
    first_period_policy: config.first_period_policy,
    payable_window_days: config.payable_window_days,
    grace_days: config.grace_days,
  };
}

const isWhole = (n: unknown): n is number => typeof n === 'number' && Number.isInteger(n);

export function validateRule(rule: BillingRule): RuleErrors {
  const errors: RuleErrors = {};
  if (rule.billing_mode === 'FIXED_DAY') {
    if (rule.fixed_due_last_day && rule.fixed_due_day !== null) {
      errors.fixed_due_day = 'Choose a due day or the last day of the month, not both.';
    } else if (!rule.fixed_due_last_day) {
      if (rule.fixed_due_day === null) {
        errors.fixed_due_day = 'Choose a due day from 1 to 28, or the last day of the month.';
      } else if (!isWhole(rule.fixed_due_day) || rule.fixed_due_day < LIMITS.fixedDay.min || rule.fixed_due_day > LIMITS.fixedDay.max) {
        errors.fixed_due_day = 'The due day must be a whole number from 1 to 28.';
      }
    }
    if (rule.first_period_policy === null) {
      errors.first_period_policy = 'Choose how the first part-month is charged.';
    }
  }
  if (!isWhole(rule.payable_window_days) || rule.payable_window_days < LIMITS.window.min || rule.payable_window_days > LIMITS.window.max) {
    errors.payable_window_days = 'The payable window must be from 1 to 15 days.';
  }
  if (!isWhole(rule.grace_days) || rule.grace_days < LIMITS.grace.min || rule.grace_days > LIMITS.grace.max) {
    errors.grace_days = 'The grace period must be from 0 to 15 days.';
  }
  return errors;
}

/** What the server takes. An anniversary rule carries no day and no policy. */
export function toPayload(rule: BillingRule): BillingRule {
  if (rule.billing_mode === 'ANNIVERSARY') {
    return { ...rule, fixed_due_day: null, fixed_due_last_day: false, first_period_policy: null };
  }
  return {
    ...rule,
    fixed_due_day: rule.fixed_due_last_day ? null : rule.fixed_due_day,
  };
}

/** True when the rule is complete enough to ask the server for a preview (no errors in the part the preview needs). */
export function canPreview(rule: BillingRule): boolean {
  const errors = validateRule(rule);
  return !errors.fixed_due_day && !errors.first_period_policy;
}

/** The rent to preview with, from the rooms: the lowest monthly price (the board shows one number). */
export function previewRent(config: BillingConfig | undefined): string | null {
  return config?.monthly_rent?.min ?? null;
}

/** "₹6,000", or "₹5,200 to ₹9,500" when the rooms differ. Display only. */
export function rentLabel(config: BillingConfig | undefined): string {
  const rent = config?.monthly_rent;
  if (!rent) return 'No rooms yet';
  const money = (v: string) => `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
  return rent.min === rent.max ? money(rent.min) : `${money(rent.min)} to ${money(rent.max)}`;
}
