import React from 'react';
import type { HostelEnrollmentState } from '../../../types';
import { AMENITY_OPTIONS } from '../../../types';

interface Props {
  data: HostelEnrollmentState;
  onEditStep: (step: number) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
}

const Section: React.FC<{
  title: string;
  step: number;
  onEdit: (s: number) => void;
  children: React.ReactNode;
}> = ({ title, step, onEdit, children }) => (
  <div className="bg-[#0F0F0F] border border-[#2A2A2A] rounded-[14px] overflow-hidden">
    <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#1A1A1A]">
      <span className="font-semibold text-white text-sm">{title}</span>
      <button
        type="button"
        onClick={() => onEdit(step)}
        className="text-[#E8571A] hover:text-[#FF6B35] text-xs font-semibold flex items-center gap-1 transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
        Edit
      </button>
    </div>
    <div className="px-5 py-4 text-sm">{children}</div>
  </div>
);

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex justify-between py-1.5 border-b border-[#1A1A1A] last:border-0">
    <span className="text-[#9A9690] font-medium">{label}</span>
    <span className="text-white font-medium text-right max-w-[60%]">{value || '—'}</span>
  </div>
);

export const Step6Review: React.FC<Props> = ({ data, onEditStep, onSubmit, isSubmitting }) => {
  const selectedAmenities = AMENITY_OPTIONS.filter(a => data.amenities.includes(a.key));

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-white mb-1">Review & Submit</h3>
        <p className="text-[#9A9690] text-sm">Review all details before submitting. You can edit any section.</p>
      </div>

      {/* Step 1: Basic Details */}
      <Section title="📍 Basic Details" step={0} onEdit={onEditStep}>
        <Row label="Hostel Name" value={data.name} />
        <Row label="Owner Name" value={data.owner_name} />
        <Row label="Contact" value={data.contact_number} />
        <Row label="Email" value={data.email} />
        <Row label="Address" value={`${data.address}, ${data.city}, ${data.state} – ${data.pincode}`} />
        {data.landmark && <Row label="Landmark" value={data.landmark} />}
        {(data.latitude || data.longitude) && (
          <Row label="Location" value={`${data.latitude}, ${data.longitude}`} />
        )}
      </Section>

      {/* Step 2: Hostel Info */}
      <Section title="🏨 Hostel Information" step={1} onEdit={onEditStep}>
        <Row label="Type" value={
          data.gender_type === 'boys' ? '👦 Boys Only' :
          data.gender_type === 'girls' ? '👧 Girls Only' :
          data.gender_type === 'co_living' ? '👥 Co-Living' : '—'
        } />
        <Row label="Floors / Rooms / Beds" value={`${data.total_floors} / ${data.total_rooms} / ${data.total_beds}`} />
        <Row label="Occupancy Types" value={data.occupancy_types.join(', ') || '—'} />
        <Row label="Check-in" value={data.check_in_policy} />
        <Row label="Check-out" value={data.check_out_policy} />
        {data.description && (
          <div className="mt-2">
            <p className="text-[#9A9690] font-medium mb-1">Description</p>
            <p className="text-white text-[13px] leading-relaxed line-clamp-3">{data.description}</p>
          </div>
        )}
      </Section>

      {/* Step 3: Amenities */}
      <Section title="✅ Amenities" step={2} onEdit={onEditStep}>
        {selectedAmenities.length === 0 ? (
          <p className="text-[#9A9690]">No amenities selected</p>
        ) : (
          <div className="flex flex-wrap gap-2 pt-1">
            {selectedAmenities.map(a => (
              <span key={a.key}
                className="flex items-center gap-1 bg-[#E8571A]/10 text-[#E8571A] border border-[#E8571A]/20 rounded-full px-2.5 py-1 text-[11px] font-semibold">
                {a.icon} {a.label}
              </span>
            ))}
          </div>
        )}
      </Section>

      {/* Step 4: Media */}
      <Section title="📸 Media" step={3} onEdit={onEditStep}>
        <Row label="Total files" value={data.media.length} />
        <Row label="Hostel images" value={data.media.filter(m => m.category === 'hostel').length} />
        <Row label="Room images" value={data.media.filter(m => m.category === 'room').length} />
        <Row label="Common area" value={data.media.filter(m => m.category === 'common_area').length} />
        <Row label="Videos" value={data.media.filter(m => m.category === 'video').length} />
      </Section>

      {/* Step 5: Rooms */}
      <Section title="🛏 Room Configuration" step={4} onEdit={onEditStep}>
        {data.rooms.length === 0 ? (
          <p className="text-[#9A9690]">No rooms configured</p>
        ) : (
          <div className="space-y-2">
            {data.rooms.map((room, i) => (
              <div key={room._draft_id} className="flex items-center justify-between py-1.5 border-b border-[#1A1A1A] last:border-0">
                <div>
                  <p className="text-white font-medium">{room.room_name || `Room ${i + 1}`}</p>
                  <p className="text-[#9A9690] text-xs">
                    {room.sharing_type} · Capacity: {room.capacity}
                    {room.is_ac ? ' · AC' : ''}
                    {room.has_attached_bathroom ? ' · Attached Bath' : ''}
                  </p>
                </div>
                <span className="text-[#E8571A] font-bold">
                  {room.price_per_month ? `₹${room.price_per_month}/mo` : '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Submit button */}
      <button
        type="button"
        onClick={onSubmit}
        disabled={isSubmitting}
        className="w-full bg-[#E8571A] hover:bg-[#FF6B35] text-white font-bold py-4 rounded-[12px] transition-all orange-glow disabled:opacity-60 flex items-center justify-center gap-3 text-base mt-2"
      >
        {isSubmitting ? (
          <>
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Submitting...
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Submit Hostel Registration
          </>
        )}
      </button>
    </div>
  );
};
