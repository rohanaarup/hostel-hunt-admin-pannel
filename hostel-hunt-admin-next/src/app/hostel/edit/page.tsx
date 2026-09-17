'use client';

import React, { useState, useEffect } from 'react';
import DashboardLayout from '@/components/common/DashboardLayout';
import Step1BasicDetails from '@/components/hostel/steps/Step1BasicDetails';
import Step2HostelInfo from '@/components/hostel/steps/Step2HostelInfo';
import Step3Amenities from '@/components/hostel/steps/Step3Amenities';
import Step4MediaUpload from '@/components/hostel/steps/Step4MediaUpload';
import Step5RoomConfig from '@/components/hostel/steps/Step5RoomConfig';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import Icon from '@/components/ui/Icon';
import { INITIAL_ENROLLMENT_STATE } from '@/types';
import type { HostelEnrollmentState } from '@/types';
import { hostelService } from '@/services/api';
import gsap from 'gsap';

const SECTIONS = [
  { id: 'basic',     label: 'Basic Details', icon: 'map-pin' as const, step: 0 },
  { id: 'info',      label: 'Hostel Info',   icon: 'building' as const, step: 1 },
  { id: 'amenities', label: 'Amenities',     icon: 'sparkles' as const, step: 2 },
  { id: 'media',     label: 'Media',         icon: 'image' as const, step: 3 },
  { id: 'rooms',     label: 'Rooms',         icon: 'bed' as const, step: 4 },
];

export default function EditHostelPage() {
  const [data, setData] = useState<any>(INITIAL_ENROLLMENT_STATE);
  const [savedData, setSavedData] = useState<any>(INITIAL_ENROLLMENT_STATE);
  const [errors, setErrors] = useState<Partial<Record<keyof HostelEnrollmentState, string>>>({});
  const [activeSection, setActiveSection] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showSaved, setShowSaved] = useState(false);
  const [showDiscardDialog, setShowDiscardDialog] = useState(false);

  useEffect(() => {
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
      payload.media_ids = payload.media ? payload.media.map((m: any) => m.id).filter(Boolean) : [];
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
      delete payload.media; delete payload.rooms; delete payload.owner; delete payload.owner_id;

      if (data.hostel_id) await hostelService.updateHostel(data.hostel_id, payload);
      else {
        const created = await hostelService.createHostel(payload);
        setData((prev: any) => ({...prev, hostel_id: created.hostel_id || created.data?.hostel_id}));
      }

      const res = await hostelService.getHostels();
      const hostels = Array.isArray(res) ? res : res.data || res.results;
      if (hostels && hostels.length > 0) {
        const fetched = hostels[0];
        if (fetched.rooms) {
          fetched.rooms = fetched.rooms.map((r: any) => ({
            ...r, _draft_id: r._draft_id || r.room_id || Math.random().toString(36).slice(2, 10)
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

  // Switch animation
  const contentRef = React.useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (contentRef.current) {
      gsap.fromTo(contentRef.current,
        { opacity: 0, y: 10 },
        { opacity: 1, y: 0, duration: 0.3, ease: 'power2.out' }
      );
    }
  }, [activeSection]);

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

      <div className="w-full max-w-[1200px] mx-auto animate-fade-in-up space-y-8">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight" style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}>
              Edit Hostel Profile
            </h1>
            <p className="mt-1 font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {loading ? 'Loading...' : data.name ? `${data.name} · Settings` : 'Complete setup to activate your hostel'}
            </p>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            {isDirty && (
              <span
                className="hidden sm:flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-full"
                style={{
                  background: 'var(--color-warning-light)',
                  color: 'var(--color-warning)',
                  border: '1px solid color-mix(in srgb, var(--color-warning) 30%, transparent)'
                }}
              >
                <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--color-warning)' }} />
                Unsaved
              </span>
            )}
            {isDirty && (
              <button
                onClick={() => setShowDiscardDialog(true)}
                className="flex-1 sm:flex-none px-4 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-80"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text-primary)' }}
              >
                Discard
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={isSaving || !isDirty}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-5 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
              style={{
                background: 'var(--color-primary)',
                color: 'var(--color-text-inverse)',
                boxShadow: isDirty && !isSaving ? '0 4px 14px color-mix(in srgb, var(--color-primary) 30%, transparent)' : 'none',
              }}
            >
              {isSaving ? (
                <><Icon name="refresh" className="w-4 h-4 animate-spin" /> Saving...</>
              ) : showSaved ? (
                <><Icon name="check" className="w-4 h-4" /> Saved!</>
              ) : (
                <><Icon name="check" className="w-4 h-4" /> Save Changes</>
              )}
            </button>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-6 lg:gap-8">
          
          {/* Sidebar Nav */}
          <div className="w-full md:w-56 lg:w-64 flex-shrink-0">
            {/* Desktop Nav */}
            <div className="hidden md:flex flex-col gap-1.5 sticky top-24">
              {SECTIONS.map((s, i) => {
                const isActive = activeSection === i;
                return (
                  <button
                    key={s.id}
                    onClick={() => setActiveSection(i)}
                    className="flex items-center gap-3 px-4 py-3 rounded-xl text-[14px] font-semibold text-left transition-all"
                    style={
                      isActive
                        ? { background: 'var(--color-primary-light)', color: 'var(--color-primary)' }
                        : { color: 'var(--color-text-muted)' }
                    }
                  >
                    <Icon name={s.icon} className="w-[18px] h-[18px]" />
                    {s.label}
                  </button>
                );
              })}
            </div>

            {/* Mobile Nav */}
            <div className="md:hidden flex gap-2 overflow-x-auto pb-2">
              {SECTIONS.map((s, i) => {
                const isActive = activeSection === i;
                return (
                  <button
                    key={s.id}
                    onClick={() => setActiveSection(i)}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap flex-shrink-0 transition-all border"
                    style={
                      isActive
                        ? { background: 'var(--color-primary-light)', borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }
                        : { background: 'var(--color-surface)', borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }
                    }
                  >
                    <Icon name={s.icon} className="w-3.5 h-3.5" />
                    {s.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Form Content */}
          <div
            ref={contentRef}
            className="flex-1 rounded-2xl p-6 lg:p-8 min-w-0"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
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
