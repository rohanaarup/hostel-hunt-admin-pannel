import React from 'react';
import { FormField, inputClass, textareaClass } from '../../ui/FormField';
import type { HostelEnrollmentState, HostelGenderType, OccupancyType } from '../../../types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
  errors: Partial<Record<keyof HostelEnrollmentState, string>>;
}

const GENDER_OPTIONS: { value: HostelGenderType; label: string; icon: string }[] = [
  { value: 'boys', label: 'Boys Only', icon: '👦' },
  { value: 'girls', label: 'Girls Only', icon: '👧' },
  { value: 'co_living', label: 'Co-Living', icon: '👥' },
];

const OCCUPANCY_OPTIONS: { value: OccupancyType; label: string }[] = [
  { value: 'single', label: 'Single' },
  { value: 'double', label: 'Double' },
  { value: 'triple', label: 'Triple' },
  { value: 'quad', label: '4-Bed' },
  { value: 'dormitory', label: 'Dormitory' },
];

export const Step2HostelInfo: React.FC<Props> = ({ data, onChange, errors }) => {
  const toggleOccupancy = (val: OccupancyType) => {
    const current = data.occupancy_types;
    onChange('occupancy_types', current.includes(val) ? current.filter(v => v !== val) : [...current, val]);
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-white mb-1">Hostel Information</h3>
        <p className="text-[#9A9690] text-sm">Details about capacity, type, and policies.</p>
      </div>

      {/* Gender type */}
      <FormField label="Hostel Type" required error={errors.gender_type}>
        <div className="grid grid-cols-3 gap-3">
          {GENDER_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange('gender_type', opt.value)}
              className={`flex flex-col items-center gap-2 py-4 rounded-[10px] border transition-all font-medium text-sm ${
                data.gender_type === opt.value
                  ? 'border-[#E8571A] bg-[#E8571A]/10 text-white'
                  : 'border-[#2A2A2A] bg-[#0F0F0F] text-[#9A9690] hover:border-[#3A3A3A] hover:text-white'
              }`}
            >
              <span className="text-2xl">{opt.icon}</span>
              <span>{opt.label}</span>
            </button>
          ))}
        </div>
      </FormField>

      {/* Numbers */}
      <div className="grid grid-cols-3 gap-4">
        <FormField label="Total Floors" required error={errors.total_floors}>
          <input
            type="number" min="1" value={data.total_floors}
            onChange={e => onChange('total_floors', e.target.value)}
            placeholder="5" className={inputClass(!!errors.total_floors)}
          />
        </FormField>
        <FormField label="Total Rooms" required error={errors.total_rooms}>
          <input
            type="number" min="1" value={data.total_rooms}
            onChange={e => onChange('total_rooms', e.target.value)}
            placeholder="30" className={inputClass(!!errors.total_rooms)}
          />
        </FormField>
        <FormField label="Total Beds" required error={errors.total_beds}>
          <input
            type="number" min="1" value={data.total_beds}
            onChange={e => onChange('total_beds', e.target.value)}
            placeholder="60" className={inputClass(!!errors.total_beds)}
          />
        </FormField>
      </div>

      {/* Occupancy types */}
      <FormField label="Occupancy Types" required error={errors.occupancy_types as string}
        hint="Select all that apply">
        <div className="flex flex-wrap gap-2">
          {OCCUPANCY_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => toggleOccupancy(opt.value)}
              className={`px-4 py-2 rounded-[8px] text-sm font-semibold border transition-all ${
                data.occupancy_types.includes(opt.value)
                  ? 'border-[#E8571A] bg-[#E8571A]/15 text-[#E8571A]'
                  : 'border-[#2A2A2A] bg-[#0F0F0F] text-[#9A9690] hover:border-[#3A3A3A]'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </FormField>

      {/* Description */}
      <FormField label="Description" required error={errors.description}>
        <textarea
          value={data.description}
          onChange={e => onChange('description', e.target.value)}
          rows={4}
          placeholder="Describe your hostel – location advantages, atmosphere, nearby amenities..."
          className={textareaClass(!!errors.description)}
        />
      </FormField>

      {/* Rules */}
      <FormField label="House Rules" error={errors.rules}>
        <textarea
          value={data.rules}
          onChange={e => onChange('rules', e.target.value)}
          rows={3}
          placeholder="No loud music after 10 PM, no guests allowed, etc."
          className={textareaClass()}
        />
      </FormField>

      {/* Policies */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FormField label="Check-in Policy" error={errors.check_in_policy}>
          <input
            value={data.check_in_policy}
            onChange={e => onChange('check_in_policy', e.target.value)}
            placeholder="Check-in from 11 AM"
            className={inputClass()}
          />
        </FormField>
        <FormField label="Check-out Policy" error={errors.check_out_policy}>
          <input
            value={data.check_out_policy}
            onChange={e => onChange('check_out_policy', e.target.value)}
            placeholder="Check-out by 10 AM"
            className={inputClass()}
          />
        </FormField>
      </div>
    </div>
  );
};
