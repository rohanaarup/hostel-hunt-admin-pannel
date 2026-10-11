'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Input, Textarea, Select } from '@/components/ui/Input';
import FormField, { inputClass } from '@/components/ui/FormField';
import type { HostelEnrollmentState } from '@/types';
import { locationService, type City, type Locality } from '@/services/api';

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

  const { data: cities = [], isLoading: citiesLoading, error: citiesError } = useQuery<City[]>({
    queryKey: ['cities', 'all'],
    queryFn: () => locationService.getCities(),
  });
  const selectedCity = cities.find(c => c.id === data.city_id);
  const { data: localities = [], isLoading: localitiesLoading } = useQuery<Locality[]>({
    queryKey: ['localities', selectedCity?.slug],
    queryFn: () => locationService.getLocalities(selectedCity!.slug),
    enabled: !!selectedCity,
  });

  const chooseCity = (id: string) => {
    const city = cities.find(c => c.id === id);
    onChange('city_id', id);
    onChange('city', city?.name ?? '');
    onChange('state', city?.state ?? '');
    onChange('locality_id', '');
    onChange('locality', '');
  };
  const chooseLocality = (id: string) => {
    const locality = localities.find(l => l.id === id);
    onChange('locality_id', id);
    onChange('locality', locality?.name ?? '');
  };

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


        {/* Address */}
        <FormField label="Full Address" required error={errors.address} className="md:col-span-2">
          <Input {...f('address')} placeholder="123, MG Road, Near City Mall" hasError={!!errors.address} />
        </FormField>

        {/* City: chosen from the list */}
        <FormField
          label="City"
          required
          error={errors.city_id || errors.city}
          hint={citiesError ? 'Could not load cities. Reload the page.' : cities.length === 0 && !citiesLoading ? 'No cities yet. Ask support to add yours.' : undefined}
        >
          <Select
            value={data.city_id ?? ''}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => chooseCity(e.target.value)}
            disabled={citiesLoading}
          >
            <option value="">{citiesLoading ? 'Loading cities...' : 'Select a city'}</option>
            {cities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </FormField>

        {/* Locality: chosen from the selected city's list */}
        <FormField
          label="Locality"
          required
          error={errors.locality_id || errors.locality}
          hint={selectedCity && !localitiesLoading && localities.length === 0 ? 'No localities for this city yet. Ask support to add yours.' : undefined}
        >
          <Select
            value={data.locality_id ?? ''}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => chooseLocality(e.target.value)}
            disabled={!selectedCity || localitiesLoading}
          >
            <option value="">{!selectedCity ? 'Choose a city first' : localitiesLoading ? 'Loading localities...' : 'Select a locality'}</option>
            {localities.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
        </FormField>

        {/* State follows the chosen city */}
        <FormField label="State" error={errors.state}>
          <Input value={data.state ?? ''} readOnly placeholder="Set by the city" />
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
