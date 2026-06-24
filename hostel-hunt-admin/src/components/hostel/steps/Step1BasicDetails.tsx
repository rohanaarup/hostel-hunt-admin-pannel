import React from 'react';
import { FormField, inputClass } from '../../ui/FormField';
import type { HostelEnrollmentState } from '../../../types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
  errors: Partial<Record<keyof HostelEnrollmentState, string>>;
}

export const Step1BasicDetails: React.FC<Props> = ({ data, onChange, errors }) => {
  const f = (key: keyof HostelEnrollmentState) => ({
    value: (data[key] as string) ?? '',
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      onChange(key, e.target.value),
    error: errors[key],
  });

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h3 className="text-lg font-bold text-white mb-1">Basic Details</h3>
        <p className="text-[#9A9690] text-sm">Tell us about your hostel and how guests can reach you.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Hostel Name */}
        <FormField label="Hostel Name" required error={errors.name} className="md:col-span-2">
          <input {...f('name')} placeholder="Sunrise Boys Hostel" className={inputClass(!!errors.name)} />
        </FormField>

        {/* Owner Name */}
        <FormField label="Owner Name" required error={errors.owner_name}>
          <input {...f('owner_name')} placeholder="Rajan Sharma" className={inputClass(!!errors.owner_name)} />
        </FormField>

        {/* Contact Number */}
        <FormField label="Contact Number" required error={errors.contact_number}>
          <input {...f('contact_number')} type="tel" placeholder="9876543210" className={inputClass(!!errors.contact_number)} />
        </FormField>

        {/* Email */}
        <FormField label="Email" required error={errors.email} className="md:col-span-2">
          <input {...f('email')} type="email" placeholder="hostel@example.com" className={inputClass(!!errors.email)} />
        </FormField>

        {/* Address */}
        <FormField label="Full Address" required error={errors.address} className="md:col-span-2">
          <input {...f('address')} placeholder="123, MG Road, Near City Mall" className={inputClass(!!errors.address)} />
        </FormField>

        {/* City */}
        <FormField label="City" required error={errors.city}>
          <input {...f('city')} placeholder="Mumbai" className={inputClass(!!errors.city)} />
        </FormField>

        {/* State */}
        <FormField label="State" required error={errors.state}>
          <input {...f('state')} placeholder="Maharashtra" className={inputClass(!!errors.state)} />
        </FormField>

        {/* Pincode */}
        <FormField label="Pincode" required error={errors.pincode}>
          <input {...f('pincode')} type="text" maxLength={6} placeholder="400001" className={inputClass(!!errors.pincode)} />
        </FormField>

        {/* Landmark */}
        <FormField label="Landmark" error={errors.landmark}>
          <input {...f('landmark')} placeholder="Opposite City Park" className={inputClass()} />
        </FormField>

        {/* Google Maps URL */}
        <FormField label="Google Maps Link" error={errors.google_maps_url} className="md:col-span-2"
          hint="Paste the 'Share' link from Google Maps">
          <input {...f('google_maps_url')} type="url" placeholder="https://maps.google.com/..." className={inputClass(!!errors.google_maps_url)} />
        </FormField>

        {/* Lat / Lng */}
        <FormField label="Latitude" error={errors.latitude} hint="e.g. 19.0760">
          <input {...f('latitude')} type="number" step="any" placeholder="19.0760" className={inputClass(!!errors.latitude)} />
        </FormField>

        <FormField label="Longitude" error={errors.longitude} hint="e.g. 72.8777">
          <input {...f('longitude')} type="number" step="any" placeholder="72.8777" className={inputClass(!!errors.longitude)} />
        </FormField>
      </div>
    </div>
  );
};
