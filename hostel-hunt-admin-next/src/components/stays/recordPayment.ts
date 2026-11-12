import { errorMessage } from '@/services/errors';
import type { OfflineMethod } from '@/types';

/** The three ways rent is paid outside the app, with the board's wording. */
export const METHODS: { value: OfflineMethod; label: string }[] = [
  { value: 'CASH', label: 'Cash' },
  { value: 'BANK_TRANSFER', label: 'Bank transfer' },
  { value: 'UPI_DIRECT', label: 'UPI direct' },
];

/** The server's own sentence when it gave one (a refusal such as "a reminder was already sent today"), else the generic one. */
export function reasonOf(error: unknown): string {
  const data = (error as { response?: { data?: { message?: unknown } } })?.response?.data;
  return typeof data?.message === 'string' && data.message ? data.message : errorMessage(error);
}

export const NOTE_MAX = 200;
export const REASON_MAX = 200;

export interface RecordForm {
  date: string;   // YYYY-MM-DD, as the browser's date field gives it
  time: string;   // HH:MM
  method: OfflineMethod | '';
  note: string;
}

export type RecordErrors = Partial<Record<keyof RecordForm, string>>;

const pad = (n: number) => String(n).padStart(2, '0');

/** Today's date and the current time, as the two fields want them (the browser's own clock and zone). */
export function nowFields(now: Date = new Date()): Pick<RecordForm, 'date' | 'time'> {
  return {
    date: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
    time: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
  };
}

/** The moment the two fields describe, or null when they are empty or not a real date. */
export function paidAtOf(date: string, time: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return null;
  const moment = new Date(`${date}T${time}:00`);
  return Number.isNaN(moment.getTime()) ? null : moment;
}

export function validateRecord(form: RecordForm, now: Date = new Date()): RecordErrors {
  const errors: RecordErrors = {};
  const moment = paidAtOf(form.date, form.time);
  if (!form.date) errors.date = 'Choose the date the rent was paid.';
  else if (!form.time) errors.time = 'Choose the time the rent was paid.';
  else if (!moment) errors.date = 'That date or time is not valid.';
  else if (moment.getTime() > now.getTime()) errors.date = 'The payment time cannot be in the future.';
  if (!form.method) errors.method = 'Choose how it was paid.';
  const note = form.note.trim();
  if (!note) errors.note = 'Add a reference note, for example the receipt book number.';
  else if (note.length > NOTE_MAX) errors.note = `Keep the note to ${NOTE_MAX} characters.`;
  return errors;
}

/** What POST /stays/dues/{id}/record-payment/ takes. Call only when validateRecord found nothing. */
export function recordBody(form: RecordForm): { paid_at: string; method: OfflineMethod; reference_note: string } {
  return {
    paid_at: (paidAtOf(form.date, form.time) as Date).toISOString(),
    method: form.method as OfflineMethod,
    reference_note: form.note.trim(),
  };
}
