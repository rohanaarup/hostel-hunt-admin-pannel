import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { httpError, renderWithQueryClient } from '@/test-utils';

const api = vi.hoisted(() => ({
  stayService: { getBilling: vi.fn(), saveBilling: vi.fn(), previewBilling: vi.fn() },
}));
vi.mock('@/services/api', () => api);
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ isReady: true, isAuthenticated: true }) }));

import BillingRuleEditor from './BillingRuleEditor';

const config = (over: Record<string, unknown> = {}) => ({
  hostel_id: 'h1', hostel_name: 'Sample PG', locality: 'Dilsukhnagar', billing_mode: 'ANNIVERSARY', fixed_due_day: null,
  fixed_due_last_day: false, first_period_policy: null, payable_window_days: 7, grace_days: 0,
  monthly_rent: { min: '6000.00', max: '6000.00' }, booking_payment_covers: 'FIRST_PERIOD_RENT', applies_to: 'new_stays',
  is_default: true, ...over,
});

// What the SERVER answers. The admin shows these words; it never works them out (a test below checks that it asks).
const row = (label: string, period: string, due: string, amount: string) => ({
  label, kind: label === 'Booking' ? 'BOOKING_PERIOD' : 'RENT', period, due, amount, period_start: '', period_end: '', due_date: '', amount_rupees: '',
});
const answer = (summary: string) => ({
  results: [
    { join_date: '2026-09-18', summary, rows: [row('Booking', '18 Sep 2026 to 17 Oct 2026', '18 Sep 2026 (at booking)', '₹6,000'),
      row('Rent 1', '18 Oct 2026 to 17 Nov 2026', '18 Oct 2026', '₹6,000')] },
    { join_date: '2027-01-31', summary: 'second', rows: [row('Booking', '31 Jan 2027 to 27 Feb 2027', '31 Jan 2027 (at booking)', '₹6,000')] },
    { join_date: '2026-09-01', summary: 'third', rows: [] },
    { join_date: '2026-09-05', summary: 'fourth', rows: [] },
  ],
});

beforeEach(() => {
  vi.clearAllMocks();
  api.stayService.getBilling.mockResolvedValue(config());
  api.stayService.previewBilling.mockResolvedValue(answer('Rent repeats on day 18 of every month.'));
  api.stayService.saveBilling.mockResolvedValue(config({ is_default: false }));
});

describe('the billing rule editor', () => {
  it('asks the server for the preview of the four sample join dates and shows the server\'s words', async () => {
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);

    expect(await screen.findByText('18 Sep 2026 to 17 Oct 2026')).toBeInTheDocument();
    expect(screen.getByText('18 Sep 2026 (at booking)')).toBeInTheDocument();
    expect(screen.getByTestId('preview-summary')).toHaveTextContent('Rent repeats on day 18 of every month.');
    expect(screen.getByTestId('monthly-rent')).toHaveTextContent('₹6,000');
    const body = api.stayService.previewBilling.mock.calls[0][0];
    expect(body).toMatchObject({
      billing_mode: 'ANNIVERSARY', fixed_due_day: null, first_period_policy: null, monthly_rent: '6000.00',
      join_dates: ['2026-09-18', '2027-01-31', '2026-09-01', '2026-09-05'], count: 5,
    });
  });

  it('shows another sample join date from the same answer', async () => {
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);
    await screen.findByText('18 Sep 2026 to 17 Oct 2026');

    fireEvent.click(screen.getByRole('button', { name: '31 Jan 2027' }));

    expect(await screen.findByText('31 Jan 2027 to 27 Feb 2027')).toBeInTheDocument();
    expect(screen.getByTestId('preview-summary')).toHaveTextContent('second');
  });

  it('a fixed-day choice asks for a new preview with the fixed day and the policy', async () => {
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);
    await screen.findByText('18 Sep 2026 to 17 Oct 2026');
    api.stayService.previewBilling.mockResolvedValue(answer('First period is prorated: 13 of 30 days = ₹2,600. From 1 Oct 2026 the full rent is due on the fixed day.'));

    fireEvent.click(screen.getByRole('radio', { name: /fixed day of the month/i }));

    await waitFor(() => expect(screen.getByTestId('preview-summary')).toHaveTextContent('13 of 30 days = ₹2,600'));
    const last = api.stayService.previewBilling.mock.calls.at(-1)![0];
    expect(last).toMatchObject({ billing_mode: 'FIXED_DAY', fixed_due_day: 1, fixed_due_last_day: false, first_period_policy: 'PRORATE' });
    expect(screen.getByRole('radio', { name: /prorate the first period/i })).toHaveAttribute('aria-checked', 'true');
  });

  it('the last-day option previews with the last-day flag and no day number', async () => {
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);
    await screen.findByText('18 Sep 2026 to 17 Oct 2026');
    fireEvent.click(screen.getByRole('radio', { name: /fixed day of the month/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Last day' }));

    await waitFor(() => expect(api.stayService.previewBilling.mock.calls.at(-1)![0]).toMatchObject({ fixed_due_day: null, fixed_due_last_day: true }));
  });

  it('does not save an invalid rule and says what is wrong', async () => {
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);
    await screen.findByText('18 Sep 2026 to 17 Oct 2026');
    fireEvent.click(screen.getByRole('radio', { name: /fixed day of the month/i }));
    fireEvent.change(screen.getByLabelText('Other due day'), { target: { value: '29' } });
    fireEvent.change(screen.getByLabelText(/payable window/i), { target: { value: '20' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save billing rule' }));

    expect(await screen.findByText('The due day must be a whole number from 1 to 28.')).toBeInTheDocument();
    expect(screen.getByText('The payable window must be from 1 to 15 days.')).toBeInTheDocument();
    expect(api.stayService.saveBilling).not.toHaveBeenCalled();
  });

  it('saves a valid rule and says it applies to new stays only', async () => {
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);
    await screen.findByText('18 Sep 2026 to 17 Oct 2026');
    fireEvent.change(screen.getByLabelText(/grace period/i), { target: { value: '3' } });

    fireEvent.click(screen.getByRole('button', { name: 'Save billing rule' }));

    expect(await screen.findByText('Billing rule saved. It applies to new stays only.')).toBeInTheDocument();
    expect(api.stayService.saveBilling).toHaveBeenCalledWith('h1', {
      billing_mode: 'ANNIVERSARY', fixed_due_day: null, fixed_due_last_day: false, first_period_policy: null,
      payable_window_days: 7, grace_days: 3,
    });
    expect(screen.getByText(/students already staying keep the rule they joined with/i)).toBeInTheDocument();
  });

  it('shows the server\'s reason when the save is refused', async () => {
    api.stayService.saveBilling.mockRejectedValue(httpError(400, { fixed_due_day: ['Choose a due day from 1 to 28.'] }));
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);
    await screen.findByText('18 Sep 2026 to 17 Oct 2026');

    fireEvent.click(screen.getByRole('button', { name: 'Save billing rule' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('Billing rule saved. It applies to new stays only.')).not.toBeInTheDocument();
  });

  it('starts from the saved rule of the hostel', async () => {
    api.stayService.getBilling.mockResolvedValue(config({
      billing_mode: 'FIXED_DAY', fixed_due_day: 5, first_period_policy: 'FULL_MONTH', payable_window_days: 10, grace_days: 2, is_default: false }));
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);

    await waitFor(() => expect(screen.getByRole('radio', { name: /fixed day of the month/i })).toHaveAttribute('aria-checked', 'true'));
    expect(screen.getByRole('radio', { name: /charge the full month/i })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText(/payable window/i)).toHaveValue(10);
    expect(screen.getByLabelText(/grace period/i)).toHaveValue(2);
  });

  it('asks for no preview when the hostel has no rooms to take a rent from', async () => {
    api.stayService.getBilling.mockResolvedValue(config({ monthly_rent: null }));
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);

    expect(await screen.findByText('Add a room with a price to see a preview.')).toBeInTheDocument();
    expect(api.stayService.previewBilling).not.toHaveBeenCalled();
  });

  it('shows the reason and a Retry when the rule cannot be loaded', async () => {
    api.stayService.getBilling.mockRejectedValueOnce(httpError(500, { detail: 'oops' })).mockResolvedValue(config());
    renderWithQueryClient(<BillingRuleEditor hostelId="h1" />);

    expect(await screen.findByText(/could not load the billing rule/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(await screen.findByText('Same day each month')).toBeInTheDocument();
  });
});
