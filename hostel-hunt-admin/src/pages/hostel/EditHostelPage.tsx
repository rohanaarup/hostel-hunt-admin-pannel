import React, { useState } from 'react';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import { Step1BasicDetails } from '../../components/hostel/steps/Step1BasicDetails';
import { Step2HostelInfo } from '../../components/hostel/steps/Step2HostelInfo';
import { Step3Amenities } from '../../components/hostel/steps/Step3Amenities';
import { Step4MediaUpload } from '../../components/hostel/steps/Step4MediaUpload';
import { Step5RoomConfig } from '../../components/hostel/steps/Step5RoomConfig';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { INITIAL_ENROLLMENT_STATE } from '../../types';
import type { HostelEnrollmentState } from '../../types';
import { hostelService } from '../../services/api';

// Removed dummy data

const SECTIONS = [
  { id: 'basic', label: 'Basic Details', icon: '📍', step: 0 },
  { id: 'info', label: 'Hostel Info', icon: '🏨', step: 1 },
  { id: 'amenities', label: 'Amenities', icon: '✅', step: 2 },
  { id: 'media', label: 'Media', icon: '📸', step: 3 },
  { id: 'rooms', label: 'Rooms', icon: '🛏', step: 4 },
];

export const EditHostelPage: React.FC = () => {
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
        // The API wraps responses in { success, data: [...] } or returns [...] directly depending on standard
        // Since we didn't add a custom paginator or wrapper on GET list, it's usually an array or {results: []}
        const hostels = Array.isArray(res) ? res : res.data || res.results;
        if (hostels && hostels.length > 0) {
          const fetched = hostels[0];
          // Ensure rooms have _draft_id for UI state tracking
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

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';

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
      
      // Convert to numbers
      payload.total_floors = Number(payload.total_floors) || 0;
      payload.total_rooms = Number(payload.total_rooms) || 0;
      payload.total_beds = Number(payload.total_beds) || 0;
      
      // Ensure arrays
      payload.occupancy_types = Array.isArray(payload.occupancy_types) ? payload.occupancy_types : [];
      payload.amenities = Array.isArray(payload.amenities) ? payload.amenities : [];
      
      // Handle empty coordinates
      payload.latitude = payload.latitude ? String(payload.latitude) : null;
      payload.longitude = payload.longitude ? String(payload.longitude) : null;
      
      // Format media for backend
      payload.media_ids = payload.media
        ? payload.media.map((m: any) => m.id).filter(Boolean)
        : [];
        
      // Format rooms for backend and filter out incomplete rooms
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
      
      // Drop frontend fields and owner references
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

      setSavedData(data);
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
        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold">Edit Hostel Details</h1>
            <p className={`${textSub} mt-1 text-sm font-medium`}>
              {loading ? 'Loading...' : data.name ? `${data.name} · Details` : 'No hostel configured yet'}
            </p>
          </div>

          {/* Action bar */}
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
                className="px-4 py-2 border border-[#2A2A2A] hover:border-[#3A3A3A] text-[#9A9690] hover:text-white rounded-[10px] text-sm font-medium transition-all"
              >
                Discard
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={!isDirty || isSaving}
              className={`flex items-center gap-2 px-5 py-2 rounded-[10px] text-sm font-semibold transition-all ${
                isDirty && !isSaving
                  ? 'bg-[#E8571A] hover:bg-[#FF6B35] text-white orange-glow'
                  : 'bg-[#2A2A2A] text-[#4A4A4A] cursor-not-allowed'
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
          {/* Sidebar nav */}
          <div className="hidden lg:flex flex-col gap-1 w-52 flex-shrink-0">
            {SECTIONS.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setActiveSection(i)}
                className={`flex items-center gap-3 px-4 py-3 rounded-[10px] text-sm font-semibold text-left transition-all ${
                  activeSection === i
                    ? 'bg-[#E8571A]/10 border border-[#E8571A]/30 text-[#E8571A]'
                    : 'text-[#9A9690] hover:text-white hover:bg-[#FFFFFF08]'
                }`}
              >
                <span className="text-base">{s.icon}</span>
                {s.label}
              </button>
            ))}
          </div>

          {/* Mobile section tabs */}
          <div className="lg:hidden w-full mb-4">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {SECTIONS.map((s, i) => (
                <button key={s.id} onClick={() => setActiveSection(i)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-[10px] text-xs font-semibold whitespace-nowrap flex-shrink-0 transition-all border ${
                    activeSection === i
                      ? 'border-[#E8571A] bg-[#E8571A]/10 text-[#E8571A]'
                      : 'border-[#2A2A2A] text-[#9A9690]'
                  }`}>
                  {s.icon} {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Main content */}
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
};
