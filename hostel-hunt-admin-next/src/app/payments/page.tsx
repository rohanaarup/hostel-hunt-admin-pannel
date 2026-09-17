'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input, Textarea, Select } from '@/components/ui/Input';
import DashboardLayout from '@/components/common/DashboardLayout';
import Modal from '@/components/ui/Modal';
import StatusBadge from '@/components/ui/StatusBadge';
import Icon from '@/components/ui/Icon';
import type { Payment, PaymentStatus } from '@/types';
import { paymentService, hostelService } from '@/services/api';
import gsap from 'gsap';

const METHOD_LABELS: Record<string, { icon: any; label: string }> = {
  upi:           { icon: 'phone',   label: 'UPI' },
  card:          { icon: 'wallet',  label: 'Card' },
  bank_transfer: { icon: 'money',   label: 'NEFT/RTGS' },
  cash:          { icon: 'money',   label: 'Cash' },
};

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function PaymentsPage() {
  const [filter, setFilter] = useState<PaymentStatus | 'all'>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState({
    resident_name: '', resident_phone: '', hostel: '', amount_due: '', due_date: '', mode: 'cash',
  });
  const queryClient = useQueryClient();
  const tableRef = useRef<HTMLTableSectionElement>(null);

  const { data: payments = [] as Payment[], isLoading: isPaymentsLoading } = useQuery<Payment[]>({
    queryKey: ['payments', filter],
    queryFn: () => paymentService.getPayments(filter === 'all' ? undefined : filter)
      .then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  const { data: hostels = [] as any[], isLoading: isHostelsLoading } = useQuery<any[]>({
    queryKey: ['hostels'],
    queryFn: () => hostelService.getHostels()
      .then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  const isLoading = isPaymentsLoading || isHostelsLoading;

  useEffect(() => {
    if (!isLoading && tableRef.current) {
      const rows = tableRef.current.querySelectorAll('tr');
      gsap.fromTo(rows,
        { opacity: 0, x: -12 },
        { opacity: 1, x: 0, duration: 0.3, stagger: 0.04, ease: 'power2.out' }
      );
    }
  }, [isLoading, filter]);

  const handleMarkPaid = async (id: string, currentDue: number) => {
    try {
      await paymentService.markPaymentPaid(id, currentDue);
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
    } catch (error) {
      console.error('Failed to mark paid', error);
      alert('Failed to update payment status');
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await paymentService.createPayment({ ...formData, amount_due: parseFloat(formData.amount_due) });
      queryClient.invalidateQueries({ queryKey: ['payments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
      setShowAddModal(false);
    } catch (error) {
      console.error('Failed to create payment', error);
      alert('Failed to create payment record');
    }
  };

  const collectedRevenue = payments
    .filter(p => p.status === 'paid' || p.status === 'completed')
    .reduce((s, p) => s + parseFloat((p.amount_paid as any) || 0), 0);

  const pendingAmount = payments
    .filter(p => p.status === 'pending' || p.status === 'overdue' || p.status === 'partial')
    .reduce((s, p) => s + (parseFloat((p.amount_due as any) || 0) - parseFloat((p.amount_paid as any) || 0)), 0);

  const overdueAmount = payments
    .filter(p => p.status === 'overdue')
    .reduce((s, p) => s + parseFloat((p.amount_due as any) || 0), 0);

  const summaryCards = [
    {
      label: 'Collected Revenue',
      amount: collectedRevenue,
      icon: 'money' as const,
      tone: 'success' as const,
      color: 'var(--color-success)',
      lightColor: 'var(--color-success-light)',
    },
    {
      label: 'Pending Dues',
      amount: pendingAmount,
      icon: 'wallet' as const,
      tone: 'warning' as const,
      color: 'var(--color-warning)',
      lightColor: 'var(--color-warning-light)',
    },
    {
      label: 'Overdue',
      amount: overdueAmount,
      icon: 'alert' as const,
      tone: 'error' as const,
      color: 'var(--color-error)',
      lightColor: 'var(--color-error-light)',
    },
    {
      label: 'Total Records',
      amount: payments.length,
      icon: 'tag' as const,
      tone: 'primary' as const,
      color: 'var(--color-primary)',
      lightColor: 'var(--color-primary-light)',
      isCount: true,
    },
  ];

  const filterTabs: { id: PaymentStatus | 'all'; label: string }[] = [
    { id: 'all',     label: 'All Transactions' },
    { id: 'pending', label: 'Pending' },
    { id: 'overdue', label: 'Overdue' },
    { id: 'partial', label: 'Partial' },
    { id: 'paid',    label: 'Paid' },
  ];

  return (
    <DashboardLayout title="Payments">
      <div className="w-full space-y-6 animate-fade-in-up">

        {/* Page header */}
        <div className="flex justify-between items-end">
          <div>
            <h1
              className="text-2xl font-extrabold tracking-tight"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
            >
              Payments
            </h1>
            <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
              Track all transactions and revenue
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-90"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--color-text-inverse)',
            }}
          >
            <Icon name="plus" className="w-4 h-4" />
            Add Record
          </button>
        </div>

        {/* Summary bento grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {summaryCards.map(s => (
            <div
              key={s.label}
              className="relative overflow-hidden rounded-2xl p-5 transition-all duration-200 hover:shadow-md"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div
                className="absolute top-0 left-0 w-1 h-full rounded-l-full"
                style={{ background: s.color }}
              />
              <div className="pl-2">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                  style={{ background: s.lightColor, color: s.color }}
                >
                  <Icon name={s.icon} className="w-5 h-5" />
                </div>
                <div className="text-[22px] font-extrabold" style={{ color: 'var(--color-text-primary)' }}>
                  {s.isCount ? s.amount : `₹${s.amount.toLocaleString('en-IN')}`}
                </div>
                <div className="text-[11px] font-semibold mt-1 uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                  {s.label}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Filter tabs + table */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          {/* Tabs */}
          <div
            className="flex gap-1 p-3 border-b overflow-x-auto"
            style={{ borderColor: 'var(--color-border)' }}
          >
            {filterTabs.map(f => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className="px-4 py-1.5 rounded-[8px] text-sm font-semibold transition-all whitespace-nowrap"
                style={
                  filter === f.id
                    ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }
                    : { color: 'var(--color-text-muted)' }
                }
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="py-16 text-center">
              <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mx-auto" style={{ borderColor: 'var(--color-primary)' }} />
            </div>
          ) : payments.length === 0 ? (
            <div className="py-16 text-center">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
              >
                <Icon name="money" className="w-7 h-7" />
              </div>
              <p className="font-semibold" style={{ color: 'var(--color-text-muted)' }}>No transactions in this category</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                    {['Resident', 'Amount Due', 'Amount Paid', 'Method', 'Due Date', 'Status', 'Actions'].map((h, i) => (
                      <th
                        key={h}
                        className={`px-5 py-3 text-[10px] uppercase tracking-wider font-bold ${i >= 3 && i < 5 ? 'hidden md:table-cell' : i === 3 ? 'hidden sm:table-cell' : ''}`}
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody ref={tableRef}>
                  {payments.map(pay => {
                    const methodInfo = METHOD_LABELS[pay.mode] || { icon: 'money', label: pay.mode };
                    return (
                      <tr
                        key={pay.id}
                        className="transition-colors last:border-0"
                        style={{ borderBottom: '1px solid var(--color-border)' }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--color-border)/30')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                      >
                        <td className="px-5 py-4">
                          <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                            {pay.resident_name || 'Unknown'}
                          </p>
                          <p className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                            {pay.resident_phone || '—'}
                          </p>
                        </td>
                        <td className="px-5 py-4">
                          <span className="font-bold text-sm" style={{ color: 'var(--color-text-primary)' }}>
                            ₹{pay.amount_due}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="font-bold text-sm" style={{ color: 'var(--color-success)' }}>
                            ₹{pay.amount_paid}
                          </span>
                        </td>
                        <td className="px-5 py-4 hidden sm:table-cell">
                          <span className="text-sm flex items-center gap-1.5" style={{ color: 'var(--color-text-muted)' }}>
                            <Icon name={methodInfo.icon} className="w-3.5 h-3.5" />
                            <span className="capitalize">{methodInfo.label}</span>
                          </span>
                        </td>
                        <td className="px-5 py-4 hidden md:table-cell">
                          <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                            {formatDate(pay.due_date)}
                          </span>
                        </td>
                        <td className="px-5 py-4">
                          <StatusBadge status={pay.status} />
                        </td>
                        <td className="px-5 py-4 text-right">
                          {pay.status !== 'paid' && pay.status !== 'completed' && (
                            <button
                              onClick={() => handleMarkPaid(pay.id, pay.amount_due)}
                              className="text-xs font-bold transition-colors hover:opacity-70"
                              style={{ color: 'var(--color-primary)' }}
                            >
                              Mark Paid
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Add Payment Modal */}
      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}>
        <div
          className="p-6 rounded-2xl w-[90vw] max-w-lg"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
            Add Payment Record
          </h2>
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Resident Name</label>
                <Input required type="text" value={formData.resident_name}
                  onChange={e => setFormData({ ...formData, resident_name: e.target.value })}
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Resident Phone</label>
                <Input required type="text" value={formData.resident_phone}
                  onChange={e => setFormData({ ...formData, resident_phone: e.target.value })}
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Hostel</label>
              <Select required value={formData.hostel}
                onChange={e => setFormData({ ...formData, hostel: e.target.value })}
                className="w-full p-2.5 rounded-lg text-sm outline-none"
                style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              >
                <option value="">Select Hostel</option>
                {hostels.map(h => <option key={h.hostel_id || h.id} value={h.hostel_id || h.id}>{h.name}</option>)}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Amount Due</label>
                <Input required type="number" step="0.01" value={formData.amount_due}
                  onChange={e => setFormData({ ...formData, amount_due: e.target.value })}
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Due Date</label>
                <Input required type="date" value={formData.due_date}
                  onChange={e => setFormData({ ...formData, due_date: e.target.value })}
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Payment Mode</label>
              <Select value={formData.mode}
                onChange={e => setFormData({ ...formData, mode: e.target.value })}
                className="w-full p-2.5 rounded-lg text-sm outline-none"
                style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              >
                <option value="cash">Cash</option>
                <option value="upi">UPI</option>
                <option value="bank_transfer">Bank Transfer</option>
              </Select>
            </div>
            <div className="pt-4 flex justify-end gap-3">
              <button type="button" onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-sm font-semibold transition-colors"
                style={{ color: 'var(--color-text-muted)' }}
              >Cancel</button>
              <button type="submit"
                className="px-4 py-2 text-sm font-semibold rounded-[8px] transition-all hover:opacity-90"
                style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
              >Save Record</button>
            </div>
          </form>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
