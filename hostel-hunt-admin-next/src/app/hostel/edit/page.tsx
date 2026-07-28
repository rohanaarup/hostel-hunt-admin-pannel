'use client';

import React, { useState } from 'react';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useTheme } from '@/contexts/ThemeContext';
import Step1BasicDetails from '@/components/hostel/steps/Step1BasicDetails';
import Step2HostelInfo from '@/components/hostel/steps/Step2HostelInfo';
import Step3Amenities from '@/components/hostel/steps/Step3Amenities';
import Step4MediaUpload from '@/components/hostel/steps/Step4MediaUpload';
import Step5RoomConfig from '@/components/hostel/steps/Step5RoomConfig';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { INITIAL_ENROLLMENT_STATE } from '@/types';
import type { HostelEnrollmentState } from '@/types';
import { hostelService } from '@/services/api';

const SECTIONS = [
  { id: 'basic', label: 'Basic Details', icon: '📍', step: 0 },
  { id: 'info', label: 'Hostel Info', icon: '🏨', step: 1 },
  { id: 'amenities', label: 'Amenities', icon: '✅', step: 2 },
  { id: 'media', label: 'Media', icon: '📸', step: 3 },
  { id: 'rooms', label: 'Rooms', icon: '🛏', step: 4 },
];

export default function EditHostelPage() {
  const { theme } = useTheme();

  const [data, setData] = useState<any>(INITIAL_ENROLLMENT_STATE);
  const [savedData, setSavedData] = useState<any>(INITIAL_ENROLLMENT_STATE);
  const [errors, setErrors] = useState<Partial<Record<keyof HostelEnrollmentState, string>>>({});
  const [activeSection, setActiveSection] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showSaved, setShowSaved] = useState(false);
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);

  React.useEffect(() => {
    const fetchHostel = async () => {
      try {
        const res = await hostelService.getHostels();
        const hostels = Array.isArray(res) ? res : res.data || res.results;
        if (hostels && hostels.length > 0) {
          const fetched = hostels[0];
          if (fetched.rooms) {
            fetched.rooms = fetched.rooms.map((r: any) => ({
              ...r,
              _draft_id: r._draft_id || r.room_id || Math.random().toString(36).slice(2, 10)
            }));
          }
          setData({ ...INITIAL_ENROLLMENT_STATE, ...fetched });
          setSavedData({ ...INITIAL_ENROLLMENT_STATE, ...fetched });
        }
      } catch (error) {
        console.error("Error fetching hostel:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchHostel();
  }, []);

  const isDirty = JSON.stringify(data) !== JSON.stringify(savedData);

  const cardBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-100';
  const cardBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';
  const textSub = theme === 'dark' ? 'text-ivory-500' : 'text-ink-700';

  const handleChange = (key: keyof HostelEnrollmentState, value: unknown) => {
    setData((prev: any) => {
      const newValue = typeof value === 'function' ? (value as Function)(prev[key]) : value;
      return { ...prev, [key]: newValue };
    });
    if (errors[key]) setErrors((prev: any) => ({ ...prev, [key]: undefined }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload: any = { ...data };

      payload.total_floors = Number(payload.total_floors) || 0;
      payload.total_rooms = Number(payload.total_rooms) || 0;
      payload.total_beds = Number(payload.total_beds) || 0;

      payload.occupancy_types = Array.isArray(payload.occupancy_types) ? payload.occupancy_types : [];
      payload.amenities = Array.isArray(payload.amenities) ? payload.amenities : [];

      payload.latitude = payload.latitude ? String(payload.latitude) : null;
      payload.longitude = payload.longitude ? String(payload.longitude) : null;

      payload.media_ids = payload.media
        ? payload.media.map((m: any) => m.id).filter(Boolean)
        : [];

      payload.rooms_data = payload.rooms
        ? payload.rooms
            .filter((r: any) => r.room_name && r.sharing_type)
            .map((r: any) => ({
              ...r,
              capacity: Number(r.capacity) || 0,
              price_per_month: Number(r.price_per_month) || 0,
              available_beds: Number(r.available_beds) || 0,
            }))
        : [];

      delete payload.media;
      delete payload.rooms;
      delete payload.owner;
      delete payload.owner_id;

      if (data.hostel_id) {
        await hostelService.updateHostel(data.hostel_id, payload);
      } else {
        const created = await hostelService.createHostel(payload);
        setData((prev: any) => ({...prev, hostel_id: created.hostel_id || created.data?.hostel_id}));
      }

      // Refetch to get updated IDs (e.g. room_ids) from the backend
      const res = await hostelService.getHostels();
      const hostels = Array.isArray(res) ? res : res.data || res.results;
      if (hostels && hostels.length > 0) {
        const fetched = hostels[0];
        if (fetched.rooms) {
          fetched.rooms = fetched.rooms.map((r: any) => ({
            ...r,
            _draft_id: r._draft_id || r.room_id || Math.random().toString(36).slice(2, 10)
          }));
        }
        setData({ ...INITIAL_ENROLLMENT_STATE, ...fetched });
        setSavedData({ ...INITIAL_ENROLLMENT_STATE, ...fetched });
      } else {
        setSavedData(data);
      }

      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 3000);
    } catch (err) {
      console.error('Error saving hostel:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDiscard = () => {
    setData(savedData);
    setErrors({});
    setShowDiscardDialog(false);
  };

  return (
    <DashboardLayout title="Edit Hostel">
      <ConfirmDialog
        isOpen={showDiscardDialog}
        title="Discard changes?"
        message="You have unsaved changes. Discarding will revert all fields to their last saved state."
        confirmLabel="Discard Changes"
        cancelLabel="Keep Editing"
        variant="warning"
        onConfirm={handleDiscard}
        onCancel={() => setShowDiscardDialog(false)}
      />

      <div className="w-full animate-fade-in-up">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-ink-900 dark:text-ivory-50">Edit Hostel Details</h1>
            <p className={`${textSub} mt-1 text-sm font-medium`}>
              {loading ? 'Loading...' : data.name ? `${data.name} · Details` : 'No hostel configured yet'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {isDirty && (
              <span className="flex items-center gap-1.5 text-amber-400 text-xs font-semibold bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 rounded-full">
                <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                Unsaved changes
              </span>
            )}
            {isDirty && (
              <button
                onClick={() => setShowDiscardDialog(true)}
                className="px-4 py-2 border border-ivory-300 hover:border-ivory-400 dark:border-ivory-700 dark:hover:border-ivory-600 text-ink-700 hover:text-ink-900 dark:text-ivory-500 dark:hover:text-ivory-50 rounded-[10px] text-sm font-medium transition-all"
              >
                Discard
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={isSaving}
              className={`flex items-center gap-2 px-5 py-2 rounded-[10px] text-sm font-semibold transition-all ${
                !isSaving
                  ? 'bg-auburn-500 hover:bg-auburn-700 dark:bg-auburn-300 dark:hover:bg-auburn-100 text-ivory-50 dark:text-ink-900 auburn-glow'
                  : 'bg-ivory-300 text-ivory-500 dark:bg-ivory-700 dark:text-ivory-500 cursor-not-allowed'
              }`}
            >
              {isSaving ? (
                <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg> Saving...</>
              ) : showSaved ? (
                <><svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg> Saved!</>
              ) : (
                <><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                </svg> Save Changes</>
              )}
            </button>
          </div>
        </div>

        <div className="flex gap-6">
          <div className="hidden lg:flex flex-col gap-1 w-52 flex-shrink-0">
            {SECTIONS.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setActiveSection(i)}
                className={`flex items-center gap-3 px-4 py-3 rounded-[10px] text-sm font-semibold text-left transition-all ${
                  activeSection === i
                    ? 'bg-auburn-500/10 dark:bg-auburn-300/10 border border-auburn-500/30 dark:border-auburn-300/30 text-auburn-500 dark:text-auburn-300'
                    : 'text-ink-700 dark:text-ivory-500 hover:text-ink-900 dark:hover:text-ivory-50 hover:bg-ivory-50/50 dark:hover:bg-ivory-50/10'
                }`}
              >
                <span className="text-base">{s.icon}</span>
                {s.label}
              </button>
            ))}
          </div>

          <div className="lg:hidden w-full mb-4">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {SECTIONS.map((s, i) => (
                <button key={s.id} onClick={() => setActiveSection(i)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-[10px] text-xs font-semibold whitespace-nowrap flex-shrink-0 transition-all border ${
                    activeSection === i
                      ? 'border-auburn-500 bg-auburn-500/10 text-auburn-500 dark:border-auburn-300 dark:bg-auburn-300/10 dark:text-auburn-300'
                      : 'border-ivory-300 text-ink-700 dark:border-ivory-700 dark:text-ivory-500'
                  }`}>
                  {s.icon} {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className={`flex-1 ${cardBg} border ${cardBorder} rounded-2xl p-6 lg:p-8 min-w-0`}>
            {activeSection === 0 && <Step1BasicDetails data={data} onChange={handleChange} errors={errors} />}
            {activeSection === 1 && <Step2HostelInfo data={data} onChange={handleChange} errors={errors} />}
            {activeSection === 2 && <Step3Amenities data={data} onChange={handleChange} />}
            {activeSection === 3 && <Step4MediaUpload data={data} onChange={handleChange} />}
            {activeSection === 4 && <Step5RoomConfig data={data} onChange={handleChange} />}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
