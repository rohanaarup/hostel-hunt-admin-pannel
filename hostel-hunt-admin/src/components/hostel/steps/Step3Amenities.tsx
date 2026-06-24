import React from 'react';
import { AMENITY_OPTIONS } from '../../../types';
import type { HostelEnrollmentState } from '../../../types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
}

export const Step3Amenities: React.FC<Props> = ({ data, onChange }) => {
  const toggle = (key: string) => {
    const current = data.amenities;
    onChange('amenities', current.includes(key) ? current.filter(k => k !== key) : [...current, key]);
  };

  const selected = data.amenities;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-white mb-1">Amenities & Facilities</h3>
        <p className="text-[#9A9690] text-sm">
          Select all the facilities available at your hostel.
          <span className="text-[#E8571A] font-semibold ml-2">{selected.length} selected</span>
        </p>
      </div>

      {/* Quick select buttons */}
      <div className="flex gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => onChange('amenities', AMENITY_OPTIONS.map(a => a.key))}
          className="text-xs font-semibold text-[#E8571A] border border-[#E8571A]/30 hover:border-[#E8571A] bg-[#E8571A]/5 hover:bg-[#E8571A]/15 px-3 py-1.5 rounded-[8px] transition-all"
        >
          Select All
        </button>
        <button
          type="button"
          onClick={() => onChange('amenities', [])}
          className="text-xs font-semibold text-[#9A9690] border border-[#2A2A2A] hover:border-[#3A3A3A] px-3 py-1.5 rounded-[8px] transition-all"
        >
          Clear All
        </button>
      </div>

      {/* Grid of amenity chips */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {AMENITY_OPTIONS.map(amenity => {
          const isSelected = selected.includes(amenity.key);
          return (
            <button
              key={amenity.key}
              type="button"
              onClick={() => toggle(amenity.key)}
              className={`relative flex items-center gap-3 px-4 py-3.5 rounded-[12px] border transition-all duration-200 text-left group ${
                isSelected
                  ? 'border-[#E8571A] bg-[#E8571A]/10 text-white shadow-[0_0_12px_rgba(232,87,26,0.15)]'
                  : 'border-[#2A2A2A] bg-[#0F0F0F] text-[#9A9690] hover:border-[#3A3A3A] hover:text-white hover:bg-[#1A1A1A]'
              }`}
            >
              {/* Checkmark */}
              <div className={`absolute top-2 right-2 w-4 h-4 rounded-full border flex items-center justify-center transition-all ${
                isSelected ? 'bg-[#E8571A] border-[#E8571A]' : 'border-[#3A3A3A] group-hover:border-[#4A4A4A]'
              }`}>
                {isSelected && (
                  <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>

              <span className="text-xl flex-shrink-0">{amenity.icon}</span>
              <span className="font-semibold text-sm leading-tight">{amenity.label}</span>
            </button>
          );
        })}
      </div>

      {selected.length > 0 && (
        <div className="bg-[#0F0F0F] rounded-[12px] border border-[#2A2A2A] p-4">
          <p className="text-[11px] font-semibold text-[#4A4A4A] uppercase tracking-wider mb-3">Selected Facilities</p>
          <div className="flex flex-wrap gap-2">
            {selected.map(key => {
              const a = AMENITY_OPTIONS.find(o => o.key === key);
              return a ? (
                <span key={key}
                  className="flex items-center gap-1.5 bg-[#E8571A]/15 text-[#E8571A] border border-[#E8571A]/30 rounded-full px-3 py-1 text-xs font-semibold">
                  {a.icon} {a.label}
                </span>
              ) : null;
            })}
          </div>
        </div>
      )}
    </div>
  );
};
