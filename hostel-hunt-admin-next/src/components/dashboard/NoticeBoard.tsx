'use client';

import React, { useState, useEffect } from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import Modal from '@/components/ui/Modal';
import type { Notice } from '@/types';
import { noticeService, hostelService } from '@/services/api';

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
  const { theme } = useTheme();
  const [notices, setNotices] = useState<Notice[]>([]);
  const [hostels, setHostels] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState({ title: '', body: '', hostel: '' });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setIsLoading(true);
      const [notRes, hostRes] = await Promise.all([noticeService.getNotices(), hostelService.getHostels()]);
      setNotices(notRes?.data || notRes || []);
      setHostels(hostRes?.data || hostRes || []);
    } catch (error) {
      console.error('Failed to fetch notices', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await noticeService.createNotice(formData);
      setShowAddModal(false);
      setFormData({ title: '', body: '', hostel: '' });
      fetchData();
    } catch (error) {
      console.error('Failed to create notice', error);
      alert('Failed to create notice');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this notice?')) return;
    try {
      await noticeService.deleteNotice(id);
      fetchData();
    } catch (error) {
      console.error('Failed to delete notice', error);
      alert('Failed to delete notice');
    }
  };

  const cardBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-100';
  const cardBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';
  const textSub = theme === 'dark' ? 'text-ivory-500' : 'text-ink-700';

  return (
    <>
      <div className="flex justify-between items-center mb-4 mt-8">
        <h2 className="text-[17px] font-bold">Notice Board</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="text-auburn-500 hover:text-auburn-700 dark:text-auburn-300 dark:hover:text-auburn-100 text-sm font-semibold transition-colors flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Notice
        </button>
      </div>

      <div className={`${cardBg} rounded-2xl border ${cardBorder} p-5`}>
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 bg-ivory-300 dark:bg-ivory-700 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : notices.length === 0 ? (
          <div className="py-8 text-center text-ink-700 dark:text-ivory-500 font-medium text-sm">
            No active notices
          </div>
        ) : (
          <div className="space-y-3">
            {notices.map((notice) => (
              <div key={notice.id} className="p-4 rounded-xl border border-ivory-300 dark:border-ivory-700 bg-ivory-50/50 dark:bg-ivory-950/50 relative group">
                <button
                  onClick={() => handleDelete(notice.id)}
                  className="absolute top-3 right-3 text-ink-700/50 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete notice"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
                <div className="pr-6">
                  <h3 className="font-bold text-ink-900 dark:text-ivory-50 text-[14px]">{notice.title}</h3>
                  <p className={`text-[12px] mt-1 ${textSub}`}>{notice.body}</p>
                  <div className="flex justify-between items-center mt-3 pt-3 border-t border-ivory-300 dark:border-ivory-700">
                    <span className="text-[10px] font-bold text-auburn-500 dark:text-auburn-300 uppercase tracking-wider">{notice.hostel}</span>
                    <span className="text-[10px] font-medium text-ink-700/70 dark:text-ivory-500/70">{timeAgo(notice.posted_at)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal isOpen={showAddModal} onClose={() => setShowAddModal(false)}>
        <div className="bg-ivory-100 dark:bg-ivory-900 border border-ivory-300 dark:border-ivory-700 p-6 rounded-2xl w-[90vw] max-w-lg">
          <h2 className="text-xl font-bold text-ink-900 dark:text-ivory-50 mb-4">Add Notice</h2>
          <form onSubmit={handleAddSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Title</label>
            <input
              required
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Content</label>
            <textarea
              required
              value={formData.body}
              onChange={(e) => setFormData({ ...formData, body: e.target.value })}
              rows={3}
              className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-700 dark:text-ivory-500 mb-1">Hostel</label>
            <select
              required
              value={formData.hostel}
              onChange={(e) => setFormData({ ...formData, hostel: e.target.value })}
              className="w-full p-2 rounded-lg border border-ivory-300 dark:border-ivory-700 bg-transparent text-sm"
            >
              <option value="">Select Hostel</option>
              {hostels.map((h) => (
                <option key={h.hostel_id || h.id} value={h.hostel_id || h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <button
              type="button"
              onClick={() => setShowAddModal(false)}
              className="px-4 py-2 text-sm font-semibold text-ink-700 dark:text-ivory-500"
            >
              Cancel
            </button>
            <button type="submit" className="px-4 py-2 text-sm font-semibold bg-auburn-500 text-white rounded-[8px]">
              Post Notice
            </button>
          </div>
        </form>
        </div>
      </Modal>
    </>
  );
}
