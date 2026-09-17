'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/common/DashboardLayout';
import { hostelService } from '@/services/api';
import Icon from '@/components/ui/Icon';
import type { HostelEnrollmentState } from '@/types';
import gsap from 'gsap';

const AMENITY_ICONS: Record<string, string> = {
  wifi: '📶', ac: '❄️', food: '🍽️', laundry: '👕', cctv: '📷',
  parking: '🅿️', housekeeping: '🧹', power_backup: '🔋', security: '🛡️',
  lift: '🛗', gym: '💪', water_supply: '💧', hot_water: '🚿',
  study_room: '📚', recreation: '🎮',
};

export default function MyHostelPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [hostel, setHostel] = useState<HostelEnrollmentState | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchHostel = async () => {
      try {
        const res = await hostelService.getHostels();
        const hostels = Array.isArray(res) ? res : res.data || res.results;
        if (hostels && hostels.length > 0) setHostel(hostels[0]);
      } catch (error) {
        console.error('Error fetching hostel:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchHostel();
  }, []);

  useEffect(() => {
    if (!loading && hostel && contentRef.current) {
      const sections = contentRef.current.querySelectorAll('.section-block');
      gsap.fromTo(sections,
        { opacity: 0, y: 24 },
        { opacity: 1, y: 0, duration: 0.45, stagger: 0.1, ease: 'power2.out', delay: 0.15 }
      );
    }
  }, [loading, hostel]);

  const infoSections = hostel ? [
    {
      icon: 'map-pin' as const,
      color: 'var(--color-primary)',
      light: 'var(--color-primary-light)',
      label: 'Location',
      primary: `${hostel.locality || hostel.city}, ${hostel.state}`,
      secondary: hostel.address,
    },
    {
      icon: 'building' as const,
      color: 'var(--color-warning)',
      light: 'var(--color-warning-light)',
      label: 'Building',
      primary: `${hostel.total_floors} Floors, ${hostel.total_rooms} Rooms`,
      secondary: `${(hostel.gender_type as string || '').replace('_', ' ')} Hostel`,
    },
    {
      icon: 'phone' as const,
      color: 'var(--color-success)',
      light: 'var(--color-success-light)',
      label: 'Contact',
      primary: hostel.email,
      secondary: `+91 ${hostel.contact_number}`,
    },
  ] : [];

  return (
    <DashboardLayout title="My Hostel">
      <div className="w-full max-w-5xl mx-auto space-y-8 animate-fade-in-up">

        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1
              className="text-[28px] font-extrabold tracking-tight"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
            >
              Hostel Overview
            </h1>
            <p className="mt-1 font-medium" style={{ color: 'var(--color-text-muted)' }}>
              View and manage your hostel profile
            </p>
          </div>
          <button
            onClick={() => router.push('/hostel/edit')}
            className="flex items-center gap-2 px-5 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-90"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--color-text-inverse)',
              boxShadow: '0 4px 14px color-mix(in srgb, var(--color-primary) 30%, transparent)',
            }}
          >
            <Icon name="edit" className="w-4 h-4" />
            Edit Profile
          </button>
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
          </div>
        ) : !hostel ? (
          <div
            className="py-20 text-center rounded-2xl"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
              <Icon name="hostel" className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>No Hostel Configured</h2>
            <p className="mb-6 max-w-md mx-auto" style={{ color: 'var(--color-text-muted)' }}>
              You haven't set up your hostel yet. Add details to start managing rooms and bookings.
            </p>
            <button
              onClick={() => router.push('/hostel/edit')}
              className="px-6 py-2.5 rounded-[10px] text-sm font-semibold hover:opacity-90 transition-all"
              style={{ background: 'var(--color-primary)', color: 'var(--color-text-inverse)' }}
            >
              Get Started
            </button>
          </div>
        ) : (
          <div ref={contentRef} className="space-y-6">

            {/* Quick info cards */}
            <div className="section-block grid grid-cols-1 md:grid-cols-3 gap-5">
              {infoSections.map(s => (
                <div
                  key={s.label}
                  className="relative overflow-hidden rounded-2xl p-5 transition-all hover:shadow-md"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                >
                  <div className="absolute top-0 left-0 w-1 h-full" style={{ background: s.color }} />
                  <div className="pl-2">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: s.light, color: s.color }}>
                      <Icon name={s.icon} className="w-5 h-5" />
                    </div>
                    <p className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: 'var(--color-text-muted)' }}>
                      {s.label}
                    </p>
                    <p className="text-base font-bold truncate" style={{ color: 'var(--color-text-primary)' }} title={s.primary}>
                      {s.primary}
                    </p>
                    <p className="text-sm mt-0.5 truncate" style={{ color: 'var(--color-text-muted)' }}>{s.secondary}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Main content + sidebar */}
            <div className="section-block grid grid-cols-1 lg:grid-cols-3 gap-5">

              {/* Main details */}
              <div
                className="lg:col-span-2 rounded-2xl p-6 lg:p-8 space-y-8"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
              >
                {/* Description */}
                <div>
                  <h2
                    className="text-xl font-bold mb-3"
                    style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
                  >
                    {hostel.name}
                  </h2>
                  <p className="leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
                    {hostel.description || 'No description provided.'}
                  </p>
                </div>

                {/* Amenities */}
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2" style={{ color: 'var(--color-text-muted)' }}>
                    <Icon name="sparkles" className="w-4 h-4" style={{ color: 'var(--color-primary)' } as any} />
                    Amenities
                  </h3>
                  {hostel.amenities && hostel.amenities.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {hostel.amenities.map(amenity => (
                        <span
                          key={amenity}
                          className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full capitalize"
                          style={{ background: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
                        >
                          <span>{AMENITY_ICONS[amenity] || '✓'}</span>
                          {amenity.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>No amenities listed.</p>
                  )}
                </div>

                {/* Policies */}
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--color-text-muted)' }}>
                    Rules & Policies
                  </h3>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {[
                      { label: 'Check-in Policy', value: hostel.check_in_policy },
                      { label: 'Check-out Policy', value: hostel.check_out_policy },
                    ].map(p => (
                      <div
                        key={p.label}
                        className="p-4 rounded-xl"
                        style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)' }}
                      >
                        <p className="text-[10px] uppercase tracking-widest font-bold mb-2" style={{ color: 'var(--color-text-muted)' }}>
                          {p.label}
                        </p>
                        <p className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                          {p.value || 'Not specified'}
                        </p>
                      </div>
                    ))}
                    <div
                      className="sm:col-span-2 p-4 rounded-xl"
                      style={{ background: 'var(--color-background)', border: '1px solid var(--color-border)' }}
                    >
                      <p className="text-[10px] uppercase tracking-widest font-bold mb-2" style={{ color: 'var(--color-text-muted)' }}>
                        General Rules
                      </p>
                      <p className="text-sm font-medium whitespace-pre-wrap" style={{ color: 'var(--color-text-primary)' }}>
                        {hostel.rules || 'Not specified'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Sidebar */}
              <div className="space-y-5">
                {/* Owner */}
                <div
                  className="rounded-2xl p-5"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                >
                  <h3 className="text-[11px] font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--color-text-muted)' }}>
                    Owner Details
                  </h3>
                  <div className="flex items-center gap-4">
                    <div
                      className="w-12 h-12 rounded-full flex items-center justify-center font-bold text-lg"
                      style={{ background: 'var(--color-primary-light)', color: 'var(--color-primary)' }}
                    >
                      {hostel.owner_name ? hostel.owner_name.charAt(0).toUpperCase() : 'O'}
                    </div>
                    <div>
                      <p className="font-bold" style={{ color: 'var(--color-text-primary)' }}>{hostel.owner_name}</p>
                      <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Hostel Owner</p>
                    </div>
                  </div>
                </div>

                {/* Occupancy types */}
                <div
                  className="rounded-2xl p-5"
                  style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                >
                  <h3 className="text-[11px] font-bold uppercase tracking-wider mb-4" style={{ color: 'var(--color-text-muted)' }}>
                    Room Types
                  </h3>
                  {hostel.occupancy_types && hostel.occupancy_types.length > 0 ? (
                    <div className="flex flex-col gap-2">
                      {hostel.occupancy_types.map(type => (
                        <div key={type} className="flex items-center gap-3">
                          <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--color-primary)' }} />
                          <span className="capitalize font-medium text-sm" style={{ color: 'var(--color-text-primary)' }}>
                            {type} Sharing
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>No occupancy types specified</p>
                  )}
                </div>

                {/* Google Maps link */}
                {hostel.google_maps_url && (
                  <a
                    href={hostel.google_maps_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 p-4 rounded-2xl transition-all hover:opacity-80"
                    style={{
                      background: 'var(--color-primary-light)',
                      border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)',
                      color: 'var(--color-primary)',
                    }}
                  >
                    <Icon name="map-pin" className="w-5 h-5" />
                    <span className="text-sm font-semibold">View on Google Maps</span>
                    <Icon name="chevron-right" className="w-4 h-4 ml-auto" />
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
