'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useTheme } from '@/contexts/ThemeContext';
import Modal from '@/components/ui/Modal';
import type { Payment, PaymentStatus } from '@/types';
import { paymentService, hostelService } from '@/services/api';

const STATUS_STYLES: Record<PaymentStatus, { cls: string; label: string }> = {
  completed: { cls: 'bg-green-500/10 text-green-400 border-green-500/20', label: 'Completed' },
  paid: { cls: 'bg-green-500/10 text-green-400 border-green-500/20', label: 'Paid' },
  pending: { cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20', label: 'Pending' },
  failed: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Failed' },
  refunded: { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20', label: 'Refunded' },
  overdue: { cls: 'bg-red-500/10 text-red-400 border-red-500/20', label: 'Overdue' },
  partial: { cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20', label: 'Partial' },
};

const METHOD_LABELS: Record<string, { icon: string; label: string }> = {
  upi: { icon: '📱', label: 'UPI' },
  card: { icon: '💳', label: 'Card' },
  bank_transfer: { icon: '🏦', label: 'NEFT/RTGS' },
  cash: { icon: '💵', label: 'Cash' },
};

export default function PaymentsPage() {
  const { theme } = useTheme();
  const [filter, setFilter] = useState<PaymentStatus | 'all'>('all');
  const [payments, setPayments] = useState<Payment[]>([]);
  const [hostels, setHostels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState({
    resident_name: '', resident_phone: '', hostel: '', amount_due: '', due_date: '', mode: 'cash'
  });

  useEffect(() => {
    fetchData();
  }, [filter]);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const [payRes, hostRes] = await Promise.all([
        paymentService.getPayments(filter === 'all' ? undefined : filter),
        hostelService.getHostels()
      ]);
      setPayments(payRes?.data || payRes || []);
      setHostels(hostRes?.data || hostRes || []);
    } catch (error) {
      console.error('Failed to fetch data', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkPaid = async (id: string, currentDue: number) => {
    try {
      await paymentService.markPaymentPaid(id, currentDue);
      fetchData();
    } catch (error) {
      console.error('Failed to mark paid', error);
      alert('Failed to update payment status');
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await paymentService.createPayment({
        ...formData,
        amount_due: parseFloat(formData.amount_due)
      });
      setShowAddModal(false);
      fetchData();
    } catch (error) {
      console.error('Failed to create payment', error);
      alert('Failed to create payment record');
    }
  };

  const cardBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-100';
  const cardBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';
  const textSub = theme === 'dark' ? 'text-ivory-500' : 'text-ink-700';
  const rowHover = theme === 'dark' ? 'hover:bg-ivory-50/5' : 'hover:bg-ivory-50';

  const totalRevenue = payments.filter(p => p.status === 'paid' || p.status === 'completed').reduce((s, p) => s + parseFloat(p.amount_paid as any || 0), 0);
  const pendingAmount = payments.filter(p => p.status === 'pending' || p.status === 'overdue' || p.status === 'partial').reduce((s, p) => s + (parseFloat(p.amount_due as any || 0) - parseFloat(p.amount_paid as any || 0)), 0);

  return (
    <DashboardLayout title="Payments">
      <div className="w-full animate-fade-in-up space-y-6">
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-ink-900 dark:text-ivory-50">Payments</h1>
            <p className={`${textSub} mt-1 text-sm font-medium`}>Track all transactions and revenue</p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="bg-auburn-500 text-white dark:bg-auburn-300 dark:text-ink-900 px-4 py-2 rounded-[10px] text-sm font-semibold hover:opacity-90 transition-opacity">
            + Add Record
          </button>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Collected Revenue', amount: totalRevenue, color: '#10B981', icon: '💰' },
            { label: 'Pending Dues', amount: pendingAmount, color: '#F59E0B', icon: '⏳' },
          ].map(s => (
            <div key={s.label} className={`${cardBg} border ${cardBorder} rounded-xl p-5 relative overflow-hidden`}>
              <div className="absolute top-0 left-0 w-1 h-full rounded-l-xl" style={{ backgroundColor: s.color }} />
              <div className="pl-2">
                <div className="text-xl mb-2">{s.icon}</div>
                <div className="text-xl font-extrabold text-ink-900 dark:text-ivory-50">
                  ₹{s.amount.toLocaleString('en-IN')}
                </div>
                <div className={`text-xs font-semibold ${textSub} mt-1`}>{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        <div className={`${cardBg} border ${cardBorder} rounded-2xl overflow-hidden`}>
          <div className="flex gap-1 p-4 border-b border-ivory-300 dark:border-ivory-700 overflow-x-auto">
            {(['all', 'pending', 'overdue', 'partial', 'paid'] as const).map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-4 py-1.5 rounded-[8px] text-sm font-semibold transition-all whitespace-nowrap capitalize ${
                  filter === f ? 'bg-auburn-500 text-ivory-50 dark:bg-auburn-300 dark:text-ink-900' : `${textSub} hover:text-ink-900 dark:hover:text-ivory-50 hover:bg-ivory-50/50 dark:hover:bg-ivory-50/10`
                }`}>
                {f === 'all' ? 'All Transactions' : f}
              </button>
            ))}
          </div>

          {isLoading ? (
            <div className="py-16 text-center text-ink-700 dark:text-ivory-500 font-medium text-sm animate-pulse">
              Loading payments...
            </div>
          ) : payments.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-4xl mb-3">💰</div>
              <p className={`${textSub} font-medium`}>No transactions in this category</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className={`text-[10px] uppercase tracking-wider font-bold ${textSub} border-b border-ivory-300 dark:border-ivory-700`}>
                    <th className="px-5 py-3">Resident</th>
                    <th className="px-5 py-3">Amount Due</th>
                    <th className="px-5 py-3">Amount Paid</th>
                    <th className="px-5 py-3 hidden sm:table-cell">Method</th>
                    <th className="px-5 py-3 hidden md:table-cell">Due Date</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map(pay => {
                    const methodInfo = METHOD_LABELS[pay.mode] || { icon: '💵', label: pay.mode };
                    const statusInfo = STATUS_STYLES[pay.status] || STATUS_STYLES.pending;

                    return (
                      <tr key={pay.id} className={`border-b border-ivory-300 dark:border-ivory-700 last:border-0 ${rowHover} transition-colors`}>
                        <td className="px-5 py-4">
                          <p className="text-ink-900 dark:text-ivory-50 text-sm font-semibold">{pay.resident_name || 'Unknown'}</p>
                          <p className={`${textSub} text-xs`}>{pay.resident_phone || '-'}</p>
                        </td>
                        <td className="px-5 py-4">
                          <span className="text-ink-900 dark:text-ivory-50 font-bold">₹{pay.amount_due}</span>
                        </td>
                        <td className="px-5 py-4">
                          <span className="text-green-500 font-bold">₹{pay.amount_paid}</span>
                        </td>
                        <td className="px-5 py-4 hidden sm:table-cell">
                          <span className={`${textSub} text-sm flex items-center gap-1.5`}>
                            <span>{methodInfo.icon}</span>
                            <span className="capitalize">{methodInfo.label}</span>
                          </span>
                        </td>
                        <td className={`px-5 py-4 ${textSub} text-xs hidden md:table-cell`}>
                          {pay.due_date ? new Date(pay.due_date).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border ${statusInfo.cls}`}>
                            {statusInfo.label}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right">
                          {pay.status !== 'paid' && pay.status !== 'completed' && (
                            <button
                              onClick={() => handleMarkPaid(pay.id, pay.amount_due)}
                              className="text-xs font-bold text-blue-500 hover:text-blue-700 transition-colors"
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

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}>
        <div className="bg-ivory-100 dark:bg-ivory-900 border border-ivory-300 dark:border-ivory-700 p-6 rounded-2xl w-[90vw] max-w-lg">
          <h2 className="text-xl font-bold text-ink-900 dark:text-ivory-50 mb-4">Add Payment Record</h2>
          <form onSubmit={handleAddSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Resident Name</label>
              <input required type="text" value={formData.resident_name} onChange={e => setFormData({...formData, resident_name: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Resident Phone</label>
              <input required type="text" value={formData.resident_phone} onChange={e => setFormData({...formData, resident_phone: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Hostel</label>
            <select required value={formData.hostel} onChange={e => setFormData({...formData, hostel: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm">
              <option value="">Select Hostel</option>
              {hostels.map(h => <option key={h.hostel_id || h.id} value={h.hostel_id || h.id}>{h.name}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Amount Due</label>
              <input required type="number" step="0.01" value={formData.amount_due} onChange={e => setFormData({...formData, amount_due: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Due Date</label>
              <input required type="date" value={formData.due_date} onChange={e => setFormData({...formData, due_date: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Payment Mode</label>
            <select value={formData.mode} onChange={e => setFormData({...formData, mode: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm">
              <option value="cash">Cash</option>
              <option value="upi">UPI</option>
              <option value="bank_transfer">Bank Transfer</option>
            </select>
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <button type="button" onClick={() => setShowAddModal(false)} className="px-4 py-2 text-sm font-semibold text-ink-700 dark:text-ivory-500">Cancel</button>
            <button type="submit" className="px-4 py-2 text-sm font-semibold bg-auburn-500 text-white rounded-[8px]">Save Record</button>
          </div>
        </form>
      </div>
    </Modal>
    </DashboardLayout>
  );
}
