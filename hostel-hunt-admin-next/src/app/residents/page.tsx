'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useTheme } from '@/contexts/ThemeContext';
import Modal from '@/components/ui/Modal';
import type { Resident } from '@/types';
import { residentService, hostelService } from '@/services/api';

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-green-500/10 text-green-400 border-green-500/20',
  vacated: 'bg-ivory-300 dark:bg-ivory-700 text-ink-700 dark:text-ivory-500 border-ivory-400 dark:border-ivory-600',
  notice_given: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
};

export default function ResidentsPage() {
  const { theme } = useTheme();
  const [residents, setResidents] = useState<Resident[]>([]);
  const [hostels, setHostels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  const [formData, setFormData] = useState({
    name: '', phone: '', hostel: '', room: '', bed_number: '',
    id_proof_type: 'Aadhaar', id_proof_number: '',
    emergency_contact_name: '', emergency_contact_phone: '',
    move_in_date: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const [resRes, hostRes] = await Promise.all([
        residentService.getResidents(),
        hostelService.getHostels()
      ]);
      setResidents(resRes?.data || resRes || []);
      setHostels(hostRes?.data || hostRes || []);
    } catch (error) {
      console.error('Failed to fetch data', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkVacated = async (id: string) => {
    try {
      await residentService.markResidentVacated(id);
      fetchData();
    } catch (error) {
      console.error('Failed to mark vacated', error);
      alert('Failed to update resident status');
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await residentService.createResident(formData);
      setShowAddModal(false);
      fetchData();
    } catch (error) {
      console.error('Failed to create resident', error);
      alert('Failed to create resident record');
    }
  };

  const cardBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-100';
  const cardBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';
  const textSub = theme === 'dark' ? 'text-ivory-500' : 'text-ink-700';
  const rowHover = theme === 'dark' ? 'hover:bg-ivory-50/5' : 'hover:bg-ivory-50';

  return (
    <DashboardLayout title="Residents">
      <div className="w-full animate-fade-in-up space-y-6">
        <div className="flex justify-between items-end">
          <div>
            <h1 className="text-2xl font-bold text-ink-900 dark:text-ivory-50">Residents</h1>
            <p className={`${textSub} mt-1 text-sm font-medium`}>Manage all hostel residents</p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="bg-auburn-500 text-white dark:bg-auburn-300 dark:text-ink-900 px-4 py-2 rounded-[10px] text-sm font-semibold hover:opacity-90 transition-opacity">
            + Add Resident
          </button>
        </div>

        <div className={`${cardBg} border ${cardBorder} rounded-2xl overflow-hidden`}>
          {isLoading ? (
            <div className="py-16 text-center text-ink-700 dark:text-ivory-500 font-medium text-sm animate-pulse">
              Loading residents...
            </div>
          ) : residents.length === 0 ? (
            <div className="py-16 text-center">
              <div className="text-4xl mb-3">👥</div>
              <p className={`${textSub} font-medium`}>No residents found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className={`text-[10px] uppercase tracking-wider font-bold ${textSub} border-b border-ivory-300 dark:border-ivory-700`}>
                    <th className="px-5 py-3">Resident</th>
                    <th className="px-5 py-3">Hostel / Room</th>
                    <th className="px-5 py-3 hidden md:table-cell">Move-in Date</th>
                    <th className="px-5 py-3">Status</th>
                    <th className="px-5 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {residents.map(res => (
                    <tr key={res.id} className={`border-b border-ivory-300 dark:border-ivory-700 last:border-0 ${rowHover} transition-colors`}>
                      <td className="px-5 py-4">
                        <p className="text-ink-900 dark:text-ivory-50 text-sm font-semibold">{res.name}</p>
                        <p className={`${textSub} text-xs`}>{res.phone}</p>
                      </td>
                      <td className="px-5 py-4">
                        <p className="text-ink-900 dark:text-ivory-50 text-sm font-semibold">{res.room || 'N/A'}</p>
                        <p className={`${textSub} text-xs`}>{res.hostel}</p>
                      </td>
                      <td className={`px-5 py-4 ${textSub} text-xs hidden md:table-cell`}>
                        {res.move_in_date ? new Date(res.move_in_date).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-[6px] text-[10px] font-bold border capitalize ${STATUS_STYLES[res.status] || STATUS_STYLES.vacated}`}>
                          {res.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        {res.status === 'active' && (
                          <button
                            onClick={() => handleMarkVacated(res.id)}
                            className="text-xs font-bold text-red-500 hover:text-red-700 transition-colors"
                          >
                            Mark Vacated
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}>
        <div className="bg-ivory-100 dark:bg-ivory-900 border border-ivory-300 dark:border-ivory-700 p-6 rounded-2xl w-[90vw] max-w-lg">
          <h2 className="text-xl font-bold text-ink-900 dark:text-ivory-50 mb-4">Add Resident</h2>
          <form onSubmit={handleAddSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Name</label>
              <input required type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Phone</label>
              <input required type="text" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Hostel</label>
              <select required value={formData.hostel} onChange={e => setFormData({...formData, hostel: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm">
                <option value="">Select Hostel</option>
                {hostels.map(h => <option key={h.hostel_id || h.id} value={h.hostel_id || h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Room ID</label>
              <input type="text" value={formData.room} onChange={e => setFormData({...formData, room: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" placeholder="Optional" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Bed Number</label>
              <input required type="text" value={formData.bed_number} onChange={e => setFormData({...formData, bed_number: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">ID Proof Type</label>
              <input required type="text" value={formData.id_proof_type} onChange={e => setFormData({...formData, id_proof_type: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">ID Proof Number</label>
              <input required type="text" value={formData.id_proof_number} onChange={e => setFormData({...formData, id_proof_number: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Emergency Contact Name</label>
              <input required type="text" value={formData.emergency_contact_name} onChange={e => setFormData({...formData, emergency_contact_name: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Emergency Contact Phone</label>
              <input required type="text" value={formData.emergency_contact_phone} onChange={e => setFormData({...formData, emergency_contact_phone: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Move-in Date</label>
            <input required type="date" value={formData.move_in_date} onChange={e => setFormData({...formData, move_in_date: e.target.value})} className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm" />
          </div>

          <div className="pt-4 flex justify-end gap-3">
            <button type="button" onClick={() => setShowAddModal(false)} className="px-4 py-2 text-sm font-semibold text-ink-700 dark:text-ivory-500">Cancel</button>
            <button type="submit" className="px-4 py-2 text-sm font-semibold bg-auburn-500 text-white rounded-[8px]">Save Resident</button>
          </div>
          </form>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
