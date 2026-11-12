'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import DashboardLayout from '@/components/common/DashboardLayout';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import ErrorState from '@/components/ui/ErrorState';
import Modal from '@/components/ui/Modal';
import StatusBadge from '@/components/ui/StatusBadge';
import RecordPaymentModal from '@/components/stays/RecordPaymentModal';
import VoidPaymentModal from '@/components/stays/VoidPaymentModal';
import { METHODS, reasonOf } from '@/components/stays/recordPayment';
import { useAdminStays, useStayActions } from '@/hooks/queries';
import type { AdminStayRow, StayAction } from '@/types';

/**
 * The AdminDues board: who has paid, who is due soon, who is overdue. Everything shown (the four totals, the tab counts, each
 * row's status and the buttons it may use) is decided by the server; this page only draws it and calls the existing endpoints
 * (record payment and void: Phase 6, send reminder: Phase 8, end stay: Phase 5).
 */

const PAGE_SIZE = 25;
type Tab = 'all' | 'overdue' | 'due_this_week' | 'paid';

const rupees = (value: string | number) => `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
const dayLabel = (iso: string | null | undefined) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : '—';
const stayWord = (n: number) => `${n} ${n === 1 ? 'stay' : 'stays'}`;

const ACTION_LABEL: Record<StayAction, string> = {
  record_payment: 'Record payment', send_reminder: 'Send reminder', view: 'View', receipt: 'Receipt', void: 'Void payment', end_stay: 'End stay',
};
const SOURCE_LABEL: Record<string, string> = { ONLINE: 'Paid online', OFFLINE_OWNER: 'Recorded by owner' };

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-2xl p-5" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>{label}</div>
      <div className="text-[24px] font-extrabold mt-1" style={{ color: 'var(--color-text-primary)' }}>{value}</div>
      <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>{note}</div>
    </div>
  );
}

export default function StaysPage() {
  const [hostel, setHostel] = useState('');
  const [tab, setTab] = useState<Tab>('all');
  const [needsReview, setNeedsReview] = useState(false);
  const [page, setPage] = useState(1);

  const [recordFor, setRecordFor] = useState<AdminStayRow | null>(null);
  const [voidFor, setVoidFor] = useState<AdminStayRow | null>(null);
  const [viewFor, setViewFor] = useState<AdminStayRow | null>(null);
  const [receiptFor, setReceiptFor] = useState<AdminStayRow | null>(null);
  const [endFor, setEndFor] = useState<AdminStayRow | null>(null);
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);

  const { data, isLoading, error, refetch, isFetching } = useAdminStays({
    hostel: hostel || undefined,
    overdue: tab === 'overdue' || undefined,
    due_this_week: tab === 'due_this_week' || undefined,
    paid: tab === 'paid' || undefined,
    needs_review: needsReview || undefined,
    page,
    page_size: PAGE_SIZE,
  });
  const { remind, endStay } = useStayActions();

  const rows = data?.results ?? [];
  const totals = data?.totals;
  const hostels = data?.hostels ?? [];
  const chosen = hostels.find((h) => h.id === hostel);
  const billingHref = `/stays/billing${hostel || hostels[0] ? `?hostel=${hostel || hostels[0].id}` : ''}`;
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: 'all', label: 'All' },
    { id: 'overdue', label: 'Overdue', count: data?.tab_counts.overdue },
    { id: 'due_this_week', label: 'Due this week', count: data?.tab_counts.due_this_week },
    { id: 'paid', label: 'Paid', count: data?.tab_counts.paid },
  ];
  const from = rows.length ? (page - 1) * PAGE_SIZE + 1 : 0;

  const choose = (next: Tab) => { setTab(next); setPage(1); };

  const run = (row: AdminStayRow, action: StayAction) => {
    setNotice(null);
    if (action === 'record_payment') setRecordFor(row);
    else if (action === 'void') setVoidFor(row);
    else if (action === 'view') setViewFor(row);
    else if (action === 'receipt') setReceiptFor(row);
    else if (action === 'end_stay') setEndFor(row);
    else if (action === 'send_reminder' && row.action_due_id) {
      remind.mutate(row.action_due_id, {
        onSuccess: () => setNotice({ tone: 'ok', text: `Reminder queued for ${row.student_name}.` }),
        onError: (e) => setNotice({ tone: 'error', text: reasonOf(e) }),
      });
    }
  };

  const secondary = (row: AdminStayRow): StayAction[] =>
    (['record_payment', 'void', 'end_stay'] as StayAction[]).filter((a) => a !== row.primary_action && row.allowed_actions.includes(a));

  return (
    <DashboardLayout title="Stays and rent">
      <div className="w-full space-y-6 animate-fade-in-up">
        <nav aria-label="Breadcrumb" className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>
          Stays and rent{chosen ? ` › ${chosen.name}${chosen.locality ? ` · ${chosen.locality}` : ''}` : ''}
        </nav>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
              Stays and dues
            </h1>
            <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
              See who has paid, who is due soon and who is overdue.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {hostels.length > 1 ? (
              <label className="text-xs font-semibold" style={{ color: 'var(--color-text-muted)' }}>
                <span className="sr-only">Hostel</span>
                <select aria-label="Hostel" value={hostel} onChange={(e) => { setHostel(e.target.value); setPage(1); }}
                  className="min-h-[44px] rounded-[10px] px-3 text-sm border"
                  style={{ background: 'var(--color-surface)', color: 'var(--color-text-primary)', borderColor: 'var(--color-border)' }}>
                  <option value="">All hostels</option>
                  {hostels.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
                </select>
              </label>
            ) : null}
            <Link href={billingHref} className="min-h-[44px] inline-flex items-center px-4 rounded-[10px] text-sm font-semibold border"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-primary)', background: 'var(--color-surface)' }}>
              Billing rule
            </Link>
          </div>
        </div>

        {error ? <ErrorState error={error} what="stays and dues" onRetry={() => refetch()} retrying={isFetching} /> : null}

        <div role="status" aria-live="polite" className="min-h-[1px]">
          {notice ? (
            <p className="text-sm font-semibold rounded-xl px-4 py-2" style={{
              background: notice.tone === 'ok' ? 'var(--color-success-light)' : 'var(--color-error-light)',
              color: notice.tone === 'ok' ? 'var(--color-success)' : 'var(--color-error)' }}>
              {notice.text}
            </p>
          ) : null}
        </div>

        {totals ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Tile label="Collected this month" value={rupees(totals.collected_this_month.amount)}
              note={`${totals.collected_this_month.stays_paid} of ${stayWord(totals.collected_this_month.stays_total)}`} />
            <Tile label="Due this week" value={rupees(totals.due_this_week.amount)} note={stayWord(totals.due_this_week.count)} />
            <Tile label="Overdue" value={rupees(totals.overdue.amount)} note={stayWord(totals.overdue.count)} />
            <Tile label="Active stays" value={String(totals.active_stays)} note={chosen ? chosen.name : 'All hostels'} />
          </div>
        ) : null}

        <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
          <div className="flex flex-wrap items-center justify-between gap-2 p-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <div role="tablist" aria-label="Rent status" className="flex gap-1 overflow-x-auto">
              {tabs.map((t) => (
                <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => choose(t.id)}
                  className="px-4 py-1.5 rounded-[8px] text-sm font-semibold whitespace-nowrap"
                  style={tab === t.id ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)' } : { color: 'var(--color-text-muted)' }}>
                  {t.label}{t.count !== undefined ? ` ${t.count}` : ''}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
              <input type="checkbox" checked={needsReview} onChange={(e) => { setNeedsReview(e.target.checked); setPage(1); }} />
              Needs review only
            </label>
          </div>

          {isLoading ? (
            <p role="status" className="py-16 text-center text-sm" style={{ color: 'var(--color-text-muted)' }}>Loading stays…</p>
          ) : rows.length === 0 && !error ? (
            <p className="py-16 text-center font-semibold" style={{ color: 'var(--color-text-muted)' }}>No stays in this view</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left" aria-label="Stays and rent">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                    {['Student', 'Room and bed', 'Rent', 'Next due', 'Status', 'Action'].map((h) => (
                      <th key={h} scope="col" className="px-5 py-3 text-[10px] uppercase tracking-wider font-bold" style={{ color: 'var(--color-text-muted)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} style={{ borderBottom: '1px solid var(--color-border)' }}>
                      <td className="px-5 py-4">
                        <span className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{row.student_name || 'Unknown'}</span>
                        {row.needs_review ? (
                          <span title="This stay needs a person to look at it" className="ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full border"
                            style={{ color: 'var(--color-warning)', borderColor: 'var(--color-warning)' }}>Needs review</span>
                        ) : null}
                        {row.stay_status === 'NOTICE' ? <span className="ml-2 text-[10px] font-semibold" style={{ color: 'var(--color-text-muted)' }}>On notice</span> : null}
                      </td>
                      <td className="px-5 py-4 text-sm" style={{ color: 'var(--color-text-primary)' }}>{row.room_label}, {row.bed_label}</td>
                      <td className="px-5 py-4 text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{rupees(row.rent_amount)}</td>
                      <td className="px-5 py-4 text-sm" style={{ color: 'var(--color-text-primary)' }}>{dayLabel(row.next_due?.date)}</td>
                      <td className="px-5 py-4"><StatusBadge status={row.status.toLowerCase()} /></td>
                      <td className="px-5 py-4">
                        <button type="button" onClick={() => run(row, row.primary_action)}
                          disabled={(row.primary_action === 'send_reminder' && remind.isPending) || (row.primary_action === 'record_payment' && !row.action_due)}
                          aria-label={`${ACTION_LABEL[row.primary_action]} for ${row.student_name}`}
                          className="min-h-[40px] px-3.5 rounded-[10px] text-sm font-semibold disabled:opacity-60"
                          style={row.primary_action === 'record_payment'
                            ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }
                            : { border: '1px solid var(--color-border)', color: 'var(--color-text-primary)', background: 'var(--color-surface)' }}>
                          {ACTION_LABEL[row.primary_action]}
                        </button>
                        <div className="flex gap-3 mt-1">
                          {secondary(row).map((a) => (
                            <button key={a} type="button" onClick={() => run(row, a)} aria-label={`${ACTION_LABEL[a]} for ${row.student_name}`}
                              className="text-xs font-semibold underline" style={{ color: 'var(--color-text-muted)' }}>
                              {ACTION_LABEL[a]}
                            </button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.count > 0 ? (
            <div className="flex items-center justify-between p-3 border-t text-xs" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
              <span>Showing {from}–{from + rows.length - 1} of {data.count}</span>
              <span className="flex gap-2">
                <button type="button" disabled={!data.previous} onClick={() => setPage((p) => p - 1)} className="px-3 py-1.5 rounded-[8px] border disabled:opacity-40" style={{ borderColor: 'var(--color-border)' }}>Previous</button>
                <button type="button" disabled={!data.next} onClick={() => setPage((p) => p + 1)} className="px-3 py-1.5 rounded-[8px] border disabled:opacity-40" style={{ borderColor: 'var(--color-border)' }}>Next</button>
              </span>
            </div>
          ) : null}
        </div>
      </div>

      {recordFor ? (
        <RecordPaymentModal key={recordFor.id} isOpen row={recordFor} onClose={() => setRecordFor(null)}
          onSaved={() => setNotice({ tone: 'ok', text: `Payment recorded for ${recordFor.student_name}.` })} />
      ) : null}
      {voidFor ? <VoidPaymentModal key={voidFor.id} isOpen row={voidFor} onClose={() => setVoidFor(null)} /> : null}

      <Modal isOpen={Boolean(viewFor)} onClose={() => setViewFor(null)} className="w-full max-w-[460px]">
        {viewFor ? (
          <div role="document" className="rounded-2xl p-6 shadow-2xl space-y-3" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
            <h2 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>{viewFor.student_name}</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm" style={{ color: 'var(--color-text-primary)' }}>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Hostel</dt><dd>{viewFor.hostel_name}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Room and bed</dt><dd>{viewFor.room_label}, {viewFor.bed_label}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Monthly rent</dt><dd>{rupees(viewFor.rent_amount)}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Joined</dt><dd>{dayLabel(viewFor.join_date)}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Next due</dt><dd>{viewFor.next_due ? `${dayLabel(viewFor.next_due.date)}, ${rupees(viewFor.next_due.amount)}` : '—'}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Status</dt><dd>{viewFor.status_label}</dd></div>
            </dl>
            <button type="button" onClick={() => setViewFor(null)} className="w-full min-h-[44px] rounded-[10px] text-sm font-medium border" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>Close</button>
          </div>
        ) : null}
      </Modal>

      <Modal isOpen={Boolean(receiptFor)} onClose={() => setReceiptFor(null)} className="w-full max-w-[460px]">
        {receiptFor?.last_payment ? (
          <div role="document" className="rounded-2xl p-6 shadow-2xl space-y-3" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
            <h2 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)' }}>Receipt</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm" style={{ color: 'var(--color-text-primary)' }}>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Receipt number</dt><dd>{receiptFor.last_payment.receipt_number}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Amount</dt><dd>{rupees(receiptFor.last_payment.amount)}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Paid on</dt><dd>{receiptFor.last_payment.paid_at ? new Date(receiptFor.last_payment.paid_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata' }) : '—'}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>How</dt><dd>{METHODS.find((m) => m.value === receiptFor.last_payment?.method)?.label ?? (receiptFor.last_payment.method || '—')}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Source</dt><dd>{SOURCE_LABEL[receiptFor.last_payment.source] ?? receiptFor.last_payment.source}</dd></div>
              <div><dt className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Student</dt><dd>{receiptFor.student_name}</dd></div>
            </dl>
            <button type="button" onClick={() => setReceiptFor(null)} className="w-full min-h-[44px] rounded-[10px] text-sm font-medium border" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>Close</button>
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog isOpen={Boolean(endFor)} variant="danger" title="End this stay?"
        message={`${endFor?.student_name ?? 'The student'} leaves ${endFor?.room_label ?? 'the room'}, ${endFor?.bed_label ?? 'the bed'}. The bed is released so it can be booked again, and future rent that is not yet due is cancelled. This cannot be undone.`}
        confirmLabel="End stay" isLoading={endStay.isPending} onCancel={() => setEndFor(null)}
        onConfirm={() => {
          if (!endFor) return;
          endStay.mutate(endFor.id, {
            onSuccess: () => { setNotice({ tone: 'ok', text: `The stay of ${endFor.student_name} has ended.` }); setEndFor(null); },
            onError: (e) => { setNotice({ tone: 'error', text: reasonOf(e) }); setEndFor(null); },
          });
        }} />
    </DashboardLayout>
  );
}
