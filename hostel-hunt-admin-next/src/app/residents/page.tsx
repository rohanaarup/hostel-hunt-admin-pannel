'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input, Textarea, Select } from '@/components/ui/Input';
import DashboardLayout from '@/components/common/DashboardLayout';
import Modal from '@/components/ui/Modal';
import StatusBadge from '@/components/ui/StatusBadge';
import Icon from '@/components/ui/Icon';
import type { Resident } from '@/types';
import { residentService, hostelService } from '@/services/api';
import gsap from 'gsap';

function formatDate(d: string | null | undefined) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function getInitials(name: string) {
  return (name || 'R').split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
}

export default function ResidentsPage() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'vacated' | 'notice_given'>('all');
  const gridRef = useRef<HTMLDivElement>(null);

  const [formData, setFormData] = useState({
    name: '', phone: '', hostel: '', room: '', bed_number: '',
    id_proof_type: 'Aadhaar', id_proof_number: '',
    emergency_contact_name: '', emergency_contact_phone: '',
    move_in_date: '',
  });

  const queryClient = useQueryClient();

  const { data: residents = [] as Resident[], isLoading: isResidentsLoading } = useQuery<Resident[]>({
    queryKey: ['residents'],
    queryFn: () => residentService.getResidents()
      .then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  const { data: hostels = [] as any[], isLoading: isHostelsLoading } = useQuery<any[]>({
    queryKey: ['hostels'],
    queryFn: () => hostelService.getHostels()
      .then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  const isLoading = isResidentsLoading || isHostelsLoading;

  useEffect(() => {
    if (!isLoading && gridRef.current) {
      const cards = gridRef.current.querySelectorAll('.resident-card');
      gsap.fromTo(cards,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.35, stagger: 0.06, ease: 'power2.out' }
      );
    }
  }, [isLoading, statusFilter]);

  const handleMarkVacated = async (id: string) => {
    try {
      await residentService.markResidentVacated(id);
      queryClient.invalidateQueries({ queryKey: ['residents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
    } catch (error) {
      console.error('Failed to mark vacated', error);
      alert('Failed to update resident status');
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await residentService.createResident(formData);
      queryClient.invalidateQueries({ queryKey: ['residents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'stats'] });
      setShowAddModal(false);
    } catch (error) {
      console.error('Failed to create resident', error);
      alert('Failed to create resident record');
    }
  };

  const q = searchQuery.toLowerCase();
  const filtered = residents.filter(r => {
    const matchesSearch = !q || r.name.toLowerCase().includes(q) || r.phone.includes(q);
    const matchesStatus = statusFilter === 'all' || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const activeCount = residents.filter(r => r.status === 'active').length;
  const vacatedCount = residents.filter(r => r.status === 'vacated').length;
  const noticeCount = residents.filter(r => r.status === 'notice_given').length;

  const statusFilters = [
    { id: 'all' as const,         label: 'All',         count: residents.length },
    { id: 'active' as const,      label: 'Active',      count: activeCount },
    { id: 'notice_given' as const, label: 'Notice Given', count: noticeCount },
    { id: 'vacated' as const,     label: 'Vacated',     count: vacatedCount },
  ];

  return (
    <DashboardLayout title="Residents">
      <div className="w-full space-y-6 animate-fade-in-up">

        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1
              className="text-2xl font-extrabold tracking-tight"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
            >
              Residents Directory
            </h1>
            <p className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {residents.length} total · {activeCount} active
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-90"
            style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
          >
            <Icon name="plus" className="w-4 h-4" />
            Add Resident
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div
            className="flex items-center p-1 rounded-xl overflow-x-auto flex-shrink-0"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            {statusFilters.map(f => (
              <button
                key={f.id}
                onClick={() => setStatusFilter(f.id)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap"
                style={
                  statusFilter === f.id
                    ? { background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }
                    : { color: 'var(--color-text-muted)' }
                }
              >
                {f.label}
                <span
                  className="px-2 py-0.5 rounded-full text-[11px] font-bold"
                  style={
                    statusFilter === f.id
                      ? { background: 'rgba(255,255,255,0.2)', color: 'inherit' }
                      : { background: 'var(--color-border)', color: 'var(--color-text-muted)' }
                  }
                >
                  {f.count}
                </span>
              </button>
            ))}
          </div>

          <div className="relative flex-1">
            <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--color-text-muted)' } as any} />
            <Input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search by name or phone…"
              className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm font-medium outline-none transition-all"
              style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
        </div>

        {/* Grid / Loading / Empty */}
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-48 rounded-2xl animate-pulse" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div
            className="py-20 text-center rounded-2xl"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
              style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
            >
              <Icon name="residents" className="w-8 h-8" />
            </div>
            <p className="text-[15px] font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>
              {searchQuery ? 'No results found' : 'No residents yet'}
            </p>
            <p className="text-[13px]" style={{ color: 'var(--color-text-muted)' }}>
              {searchQuery ? 'Try a different search term.' : 'Add your first resident to get started.'}
            </p>
          </div>
        ) : (
          <div ref={gridRef} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filtered.map(res => (
              <div
                key={res.id}
                className="resident-card rounded-2xl p-5 flex flex-col gap-3 transition-all duration-200 hover:shadow-md"
                style={{
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                }}
                onMouseEnter={e => gsap.to(e.currentTarget, { y: -3, duration: 0.2, ease: 'power2.out' })}
                onMouseLeave={e => gsap.to(e.currentTarget, { y: 0, duration: 0.2, ease: 'power2.out' })}
              >
                {/* Avatar + name */}
                <div className="flex items-center gap-3">
                  <div
                    className="w-11 h-11 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0"
                    style={{
                      background: res.status === 'active' ? 'var(--color-success-light)' : 'var(--color-border)',
                      color: res.status === 'active' ? 'var(--color-success)' : 'var(--color-text-muted)',
                    }}
                  >
                    {getInitials(res.name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-bold truncate" style={{ color: 'var(--color-text-primary)' }}>
                      {res.name}
                    </p>
                    <p className="text-[11px] truncate" style={{ color: 'var(--color-text-muted)' }}>
                      {res.phone}
                    </p>
                  </div>
                </div>

                {/* Status badge */}
                <StatusBadge status={res.status} />

                {/* Info */}
                <div className="space-y-1.5 pt-2 border-t" style={{ borderColor: 'var(--color-border)' }}>
                  <div className="flex items-center gap-2">
                    <Icon name="bed" className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      Bed: <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{res.bed_number || '—'}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Icon name="calendar" className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      Moved in: <span style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{formatDate(res.move_in_date)}</span>
                    </span>
                  </div>
                </div>

                {/* Action */}
                {res.status === 'active' && (
                  <button
                    onClick={() => handleMarkVacated(res.id)}
                    className="mt-auto w-full text-xs font-bold py-2 rounded-[8px] transition-all hover:opacity-80"
                    style={{
                      background: 'var(--color-error-light)',
                      color: 'var(--color-error)',
                      border: '1px solid color-mix(in srgb, var(--color-error) 25%, transparent)',
                    }}
                  >
                    Mark Vacated
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Resident Modal */}
      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}>
        <div
          className="p-6 rounded-2xl w-[90vw] max-w-lg max-h-[90vh] overflow-y-auto"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
            Add Resident
          </h2>
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'Name', key: 'name', type: 'text', required: true },
                { label: 'Phone', key: 'phone', type: 'text', required: true },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>{f.label}</label>
                  <Input required={f.required} type={f.type}
                    value={(formData as any)[f.key]}
                    onChange={e => setFormData({ ...formData, [f.key]: e.target.value })}
                    className="w-full p-2.5 rounded-lg text-sm outline-none"
                    style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                  />
                </div>
              ))}
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Hostel</label>
                <Select required value={formData.hostel} onChange={e => setFormData({ ...formData, hostel: e.target.value })}
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                >
                  <option value="">Select</option>
                  {hostels.map(h => <option key={h.hostel_id || h.id} value={h.hostel_id || h.id}>{h.name}</option>)}
                </Select>
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Room ID</label>
                <Input type="text" value={formData.room} onChange={e => setFormData({ ...formData, room: e.target.value })}
                  placeholder="Optional"
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Bed #</label>
                <Input required type="text" value={formData.bed_number} onChange={e => setFormData({ ...formData, bed_number: e.target.value })}
                  className="w-full p-2.5 rounded-lg text-sm outline-none"
                  style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              {[
                { label: 'ID Proof Type', key: 'id_proof_type' },
                { label: 'ID Proof Number', key: 'id_proof_number' },
                { label: 'Emergency Contact Name', key: 'emergency_contact_name' },
                { label: 'Emergency Contact Phone', key: 'emergency_contact_phone' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>{f.label}</label>
                  <Input required type="text" value={(formData as any)[f.key]} onChange={e => setFormData({ ...formData, [f.key]: e.target.value })}
                    className="w-full p-2.5 rounded-lg text-sm outline-none"
                    style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
                  />
                </div>
              ))}
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Move-in Date</label>
              <Input required type="date" value={formData.move_in_date} onChange={e => setFormData({ ...formData, move_in_date: e.target.value })}
                className="w-full p-2.5 rounded-lg text-sm outline-none"
                style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              />
            </div>
            <div className="pt-4 flex justify-end gap-3">
              <button type="button" onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-sm font-semibold" style={{ color: 'var(--color-text-muted)' }}
              >Cancel</button>
              <button type="submit"
                className="px-4 py-2 text-sm font-semibold rounded-[8px] hover:opacity-90 transition-all"
                style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
              >Save Resident</button>
            </div>
          </form>
        </div>
      </Modal>
    </DashboardLayout>
  );
}
