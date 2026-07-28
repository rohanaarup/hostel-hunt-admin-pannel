'use client';

import React from 'react';
import { AMENITY_OPTIONS } from '@/types';
import type { HostelEnrollmentState } from '@/types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
}

export default function Step3Amenities({ data, onChange }: Props) {
  const toggle = (key: string) => {
    const current = data.amenities;
    onChange('amenities', current.includes(key) ? current.filter((k) => k !== key) : [...current, key]);
  };

  const selected = data.amenities;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-ink-900 dark:text-ivory-50 mb-1">Amenities & Facilities</h3>
        <p className="text-ink-700 dark:text-ivory-500 text-sm">
          Select all the facilities available at your hostel.
          <span className="text-auburn-500 dark:text-auburn-300 font-semibold ml-2">{selected.length} selected</span>
        </p>
      </div>

      {/* Quick select buttons */}
      <div className="flex gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => onChange('amenities', AMENITY_OPTIONS.map((a) => a.key))}
          className="text-xs font-semibold text-auburn-500 border border-auburn-500/30 hover:border-auburn-500 bg-auburn-500/5 hover:bg-auburn-500/15 dark:text-auburn-300 dark:border-auburn-300/30 dark:hover:border-auburn-300 dark:bg-auburn-300/5 dark:hover:bg-auburn-300/15 px-3 py-1.5 rounded-[8px] transition-all"
        >
          Select All
        </button>
        <button
          type="button"
          onClick={() => onChange('amenities', [])}
          className="text-xs font-semibold text-ink-700 border border-ivory-300 hover:border-ivory-400 dark:text-ivory-500 dark:border-ivory-700 dark:hover:border-ivory-600 px-3 py-1.5 rounded-[8px] transition-all"
        >
          Clear All
        </button>
      </div>

      {/* Grid of amenity chips */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {AMENITY_OPTIONS.map((amenity) => {
          const isSelected = selected.includes(amenity.key);
          return (
            <button
              key={amenity.key}
              type="button"
              onClick={() => toggle(amenity.key)}
              className={`relative flex items-center gap-3 px-4 py-3.5 rounded-[12px] border transition-all duration-200 text-left group ${
                isSelected
                  ? 'border-auburn-500 bg-auburn-500/10 text-ink-900 shadow-md shadow-auburn-500/15 dark:border-auburn-300 dark:bg-auburn-300/10 dark:text-ivory-50 dark:shadow-auburn-300/15'
                  : 'border-ivory-300 bg-ivory-50 text-ink-700 hover:border-ivory-400 hover:text-ink-900 hover:bg-ivory-100 dark:border-ivory-700 dark:bg-ivory-950 dark:text-ivory-500 dark:hover:border-ivory-600 dark:hover:text-ivory-50 dark:hover:bg-ivory-900'
              }`}
            >
              {/* Checkmark */}
              <div
                className={`absolute top-2 right-2 w-4 h-4 rounded-full border flex items-center justify-center transition-all ${
                  isSelected
                    ? 'bg-auburn-500 border-auburn-500 dark:bg-auburn-300 dark:border-auburn-300'
                    : 'border-ivory-300 group-hover:border-ivory-400 dark:border-ivory-700 dark:group-hover:border-ivory-600'
                }`}
              >
                {isSelected && (
                  <svg className="w-2.5 h-2.5 text-ivory-50 dark:text-ink-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
        <div className="bg-ivory-50 dark:bg-ivory-950 rounded-[12px] border border-ivory-300 dark:border-ivory-700 p-4">
          <p className="text-[11px] font-semibold text-ink-700 dark:text-ivory-500 uppercase tracking-wider mb-3">Selected Facilities</p>
          <div className="flex flex-wrap gap-2">
            {selected.map((key) => {
              const a = AMENITY_OPTIONS.find((o) => o.key === key);
              return a ? (
                <span
                  key={key}
                  className="flex items-center gap-1.5 bg-auburn-500/15 text-auburn-500 border border-auburn-500/30 dark:bg-auburn-300/15 dark:text-auburn-300 dark:border-auburn-300/30 rounded-full px-3 py-1 text-xs font-semibold"
                >
                  {a.icon} {a.label}
                </span>
              ) : null;
            })}
          </div>
        </div>
      )}
    </div>
  );
}
