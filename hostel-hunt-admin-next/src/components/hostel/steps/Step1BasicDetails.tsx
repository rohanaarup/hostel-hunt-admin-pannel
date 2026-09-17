'use client';

import React from 'react';
import { Input, Textarea, Select } from '@/components/ui/Input';
import FormField, { inputClass } from '@/components/ui/FormField';
import type { HostelEnrollmentState } from '@/types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
  errors: Partial<Record<keyof HostelEnrollmentState, string>>;
}

export default function Step1BasicDetails({ data, onChange, errors }: Props) {
  const f = (key: keyof HostelEnrollmentState) => ({
    value: (data[key] as string) ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onChange(key, e.target.value),
    error: errors[key],
  });

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-ink-900 dark:text-ivory-50 mb-1">Basic Details</h3>
        <p className="text-ink-700 dark:text-ivory-500 text-sm">Tell us about your hostel and how guests can reach you.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Hostel Name */}
        <FormField label="Hostel Name" required error={errors.name} className="md:col-span-2">
          <Input {...f('name')} placeholder="Sunrise Boys Hostel" hasError={!!errors.name} />
        </FormField>

        {/* Owner Name */}
        <FormField label="Owner Name" required error={errors.owner_name}>
          <Input {...f('owner_name')} placeholder="Rajan Sharma" hasError={!!errors.owner_name} />
        </FormField>

        {/* Contact Number */}
        <FormField label="Contact Number" required error={errors.contact_number}>
          <Input {...f('contact_number')} type="tel" placeholder="9876543210" hasError={!!errors.contact_number} />
        </FormField>

        {/* Email */}
        <FormField label="Email" required error={errors.email} className="md:col-span-2">
          <Input {...f('email')} type="email" placeholder="hostel@example.com" hasError={!!errors.email} />
        </FormField>

        {/* Locality */}
        <FormField label="Locality" required error={errors.locality} className="md:col-span-2">
          <Input {...f('locality')} placeholder="e.g. Andheri West" hasError={!!errors.locality} />
        </FormField>

        {/* Address */}
        <FormField label="Full Address" required error={errors.address} className="md:col-span-2">
          <Input {...f('address')} placeholder="123, MG Road, Near City Mall" hasError={!!errors.address} />
        </FormField>

        {/* City */}
        <FormField label="City" required error={errors.city}>
          <Input {...f('city')} placeholder="Mumbai" hasError={!!errors.city} />
        </FormField>

        {/* State */}
        <FormField label="State" required error={errors.state}>
          <Input {...f('state')} placeholder="Maharashtra" hasError={!!errors.state} />
        </FormField>

        {/* Pincode */}
        <FormField label="Pincode" required error={errors.pincode}>
          <Input {...f('pincode')} type="text" maxLength={6} placeholder="400001" hasError={!!errors.pincode} />
        </FormField>

        {/* Landmark */}
        <FormField label="Landmark" error={errors.landmark}>
          <Input {...f('landmark')} placeholder="Opposite City Park"  />
        </FormField>

        {/* Google Maps URL */}
        <FormField
          label="Google Maps Link"
          error={errors.google_maps_url}
          className="md:col-span-2"
          hint="Paste the 'Share' link from Google Maps"
        >
          <Input {...f('google_maps_url')} type="url" placeholder="https://maps.google.com/..." hasError={!!errors.google_maps_url} />
        </FormField>

        {/* Lat / Lng */}
        <FormField label="Latitude" error={errors.latitude} hint="e.g. 19.0760">
          <Input {...f('latitude')} type="number" step="any" placeholder="19.0760" hasError={!!errors.latitude} />
        </FormField>

        <FormField label="Longitude" error={errors.longitude} hint="e.g. 72.8777">
          <Input {...f('longitude')} type="number" step="any" placeholder="72.8777" hasError={!!errors.longitude} />
        </FormField>
      </div>
    </div>
  );
}
