'use client';

import React, { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input, Textarea, Select } from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Icon from '@/components/ui/Icon';
import type { Notice } from '@/types';
import { noticeService, hostelService } from '@/services/api';
import gsap from 'gsap';

function timeAgo(iso: string) {
  if (!iso) return '-';
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function NoticeBoard() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState({ title: '', body: '', hostel: '' });
  const containerRef = React.useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: notices = [] as Notice[], isLoading: isNoticesLoading } = useQuery<Notice[]>({
    queryKey: ['notices'],
    queryFn: () => noticeService.getNotices()
      .then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  const { data: hostels = [] as any[], isLoading: isHostelsLoading } = useQuery<any[]>({
    queryKey: ['hostels'],
    queryFn: () => hostelService.getHostels()
      .then(r => Array.isArray(r?.data) ? r.data : Array.isArray(r) ? r : [])
  });

  const isLoading = isNoticesLoading || isHostelsLoading;

  useEffect(() => {
    if (!isLoading && containerRef.current) {
      const items = containerRef.current.querySelectorAll('.notice-item');
      gsap.fromTo(items,
        { opacity: 0, x: 20 },
        { opacity: 1, x: 0, duration: 0.35, stagger: 0.08, ease: 'power2.out' }
      );
    }
  }, [isLoading]);

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await noticeService.createNotice(formData);
      queryClient.invalidateQueries({ queryKey: ['notices'] });
      setShowAddModal(false);
      setFormData({ title: '', body: '', hostel: '' });
    } catch (error) {
      console.error('Failed to create notice', error);
      alert('Failed to create notice');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this notice?')) return;
    try {
      await noticeService.deleteNotice(id);
      queryClient.invalidateQueries({ queryKey: ['notices'] });
    } catch (error) {
      console.error('Failed to delete notice', error);
      alert('Failed to delete notice');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex justify-between items-center mb-4 mt-8 lg:mt-0">
        <h2 className="text-[17px] font-bold" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
          Notice Board
        </h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="text-sm font-semibold transition-colors flex items-center gap-1 hover:opacity-70"
          style={{ color: 'var(--color-primary)' }}
        >
          <Icon name="plus" className="w-3.5 h-3.5" />
          Add Notice
        </button>
      </div>

      <div
        className="rounded-2xl p-5 flex-1"
        style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
      >
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: 'var(--color-border)' }} />
            ))}
          </div>
        ) : notices.length === 0 ? (
          <div className="py-12 text-center">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3"
              style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
            >
              <Icon name="bell" className="w-6 h-6" />
            </div>
            <p className="text-[13px] font-bold mb-1" style={{ color: 'var(--color-text-primary)' }}>No active notices</p>
            <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>Important announcements will appear here.</p>
          </div>
        ) : (
          <div ref={containerRef} className="space-y-3">
            {notices.map((notice) => (
              <div
                key={notice.id}
                className="notice-item p-4 rounded-xl relative group transition-colors"
                style={{
                  background: 'var(--color-background)',
                  border: '1px solid var(--color-border)'
                }}
              >
                <button
                  onClick={() => handleDelete(notice.id)}
                  className="absolute top-3 right-3 transition-opacity opacity-0 group-hover:opacity-100 hover:scale-110"
                  style={{ color: 'var(--color-error)' }}
                  title="Delete notice"
                >
                  <Icon name="x" className="w-4 h-4" />
                </button>
                <div className="pr-6">
                  <h3 className="font-bold text-[14px]" style={{ color: 'var(--color-text-primary)' }}>{notice.title}</h3>
                  <p className="text-[12px] mt-1 line-clamp-2" style={{ color: 'var(--color-text-muted)' }}>{notice.body}</p>
                  <div className="flex justify-between items-center mt-3 pt-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-primary)' }}>
                      {notice.hostel}
                    </span>
                    <span className="text-[10px] font-medium opacity-70" style={{ color: 'var(--color-text-muted)' }}>
                      {timeAgo(notice.posted_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}>
        <div
          className="p-6 rounded-2xl w-[90vw] max-w-lg"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
        >
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
            Add Notice
          </h2>
          <form onSubmit={handleAddSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Title</label>
              <Input required type="text" value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="w-full p-2.5 rounded-lg text-sm outline-none"
                style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Content</label>
              <Textarea required value={formData.body}
                onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                rows={3}
                className="w-full p-2.5 rounded-lg text-sm outline-none resize-none"
                style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: 'var(--color-text-muted)' }}>Hostel</label>
              <Select required value={formData.hostel}
                onChange={(e) => setFormData({ ...formData, hostel: e.target.value })}
                className="w-full p-2.5 rounded-lg text-sm outline-none"
                style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              >
                <option value="">Select Hostel</option>
                {hostels.map((h) => (
                  <option key={h.hostel_id || h.id} value={h.hostel_id || h.id}>{h.name}</option>
                ))}
              </Select>
            </div>
            <div className="pt-4 flex justify-end gap-3">
              <button type="button" onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-sm font-semibold transition-colors hover:opacity-80"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Cancel
              </button>
              <button type="submit"
                className="px-5 py-2 text-sm font-semibold rounded-[8px] transition-all hover:opacity-90"
                style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
              >
                Post Notice
              </button>
            </div>
          </form>
        </div>
      </Modal>
    </div>
  );
}
