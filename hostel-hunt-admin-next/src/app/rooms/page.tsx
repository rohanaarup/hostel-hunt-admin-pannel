'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useRouter } from 'next/navigation';
import { hostelService, roomService } from '@/services/api';
import Icon from '@/components/ui/Icon';
import gsap from 'gsap';

interface Room {
  room_id: string;
  hostel: string;
  room_name: string;
  sharing_type: string;
  capacity: number;
  price_per_month: string;
  available_beds: number;
  has_attached_bathroom: boolean;
  is_ac: boolean;
  description: string;
  created_at: string;
}

export default function RoomsPage() {
  const router = useRouter();
  const gridRef = useRef<HTMLDivElement>(null);
  const { data: hostels = [] as any[], isLoading: isHostelsLoading } = useQuery<any[]>({
    queryKey: ['hostels'],
    queryFn: () => hostelService.getHostels()
      .then(r => Array.isArray(r) ? r : r?.data || r?.results || [])
  });

  const hostelId = hostels[0]?.hostel_id || hostels[0]?.id || null;

  const { data: rooms = [] as Room[], isLoading: isRoomsLoading } = useQuery<Room[]>({
    queryKey: ['rooms', hostelId],
    queryFn: () => roomService.getRooms(hostelId!)
      .then(r => Array.isArray(r) ? r : r?.data || r?.results || []),
    enabled: !!hostelId
  });

  const loading = isHostelsLoading || (!!hostelId && isRoomsLoading);

  useEffect(() => {
    if (!loading && gridRef.current) {
      const cards = gridRef.current.querySelectorAll('.room-card');
      gsap.fromTo(cards,
        { opacity: 0, y: 24, scale: 0.97 },
        { opacity: 1, y: 0, scale: 1, duration: 0.4, stagger: 0.07, ease: 'power2.out' }
      );
    }
  }, [loading]);

  const availableRooms = rooms.filter(r => r.available_beds > 0).length;
  const occupiedRooms  = rooms.length - availableRooms;
  const totalBeds      = rooms.reduce((s, r) => s + r.capacity, 0);
  const availBeds      = rooms.reduce((s, r) => s + r.available_beds, 0);

  const summaryStats = [
    { label: 'Total Rooms',    value: rooms.length,    color: 'var(--color-primary)', light: 'var(--color-primary-light)',   icon: 'rooms' as const },
    { label: 'Available',      value: availableRooms,  color: 'var(--color-success)', light: 'var(--color-success-light)',   icon: 'key' as const },
    { label: 'Occupied',       value: occupiedRooms,   color: 'var(--color-warning)', light: 'var(--color-warning-light)',   icon: 'bed' as const },
    { label: 'Available Beds', value: availBeds,       color: 'var(--color-primary)', light: 'var(--color-primary-light)',   icon: 'inbox' as const },
  ];

  const sharingTypeColors: Record<string, { color: string; light: string }> = {
    single:    { color: 'var(--color-primary)', light: 'var(--color-primary-light)' },
    double:    { color: 'var(--color-success)', light: 'var(--color-success-light)' },
    triple:    { color: 'var(--color-warning)', light: 'var(--color-warning-light)' },
    quad:      { color: 'var(--color-error)',   light: 'var(--color-error-light)' },
    dormitory: { color: 'var(--color-text-secondary)', light: 'var(--color-border)' },
  };

  return (
    <DashboardLayout title="Rooms Management">
      <div className="w-full space-y-8 animate-fade-in-up">

        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1
              className="text-[28px] font-extrabold tracking-tight"
              style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text-primary)' }}
            >
              Rooms Management
            </h1>
            <p className="mt-1 font-medium" style={{ color: 'var(--color-text-muted)' }}>
              {loading ? 'Loading...' : `${rooms.length} rooms · ${totalBeds} total beds`}
            </p>
          </div>
          {hostelId && (
            <button
              onClick={() => router.push('/hostel/edit')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-[10px] text-sm font-semibold transition-all hover:opacity-80"
              style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: 'var(--color-text-secondary)' }}
            >
              <Icon name="plus" className="w-4 h-4" />
              Add Room
            </button>
          )}
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin" style={{ borderColor: 'var(--color-primary)' }} />
          </div>
        ) : !hostelId ? (
          <div
            className="py-20 text-center rounded-2xl"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
          >
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
              <Icon name="hostel" className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>Hostel Not Configured</h2>
            <p className="mb-6 max-w-md mx-auto" style={{ color: 'var(--color-text-muted)' }}>
              Set up your hostel first before managing rooms.
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
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {summaryStats.map(s => (
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
                    <p className="text-[28px] font-extrabold leading-none" style={{ color: 'var(--color-text-primary)' }}>{s.value}</p>
                    <p className="text-[11px] font-bold uppercase tracking-wider mt-1" style={{ color: 'var(--color-text-muted)' }}>{s.label}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Room grid */}
            {rooms.length === 0 ? (
              <div
                className="py-20 text-center rounded-2xl"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
              >
                <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
                  <Icon name="bed" className="w-8 h-8" />
                </div>
                <h2 className="text-xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>No Rooms Added</h2>
                <p style={{ color: 'var(--color-text-muted)' }}>You haven't added any rooms to your hostel yet.</p>
              </div>
            ) : (
              <div ref={gridRef} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {rooms.map(room => {
                  const isAvail = room.available_beds > 0;
                  const shareColor = sharingTypeColors[room.sharing_type] || sharingTypeColors.single;
                  const occupancyPct = room.capacity > 0
                    ? Math.round(((room.capacity - room.available_beds) / room.capacity) * 100)
                    : 0;

                  return (
                    <div
                      key={room.room_id}
                      className="room-card rounded-2xl overflow-hidden flex flex-col transition-all duration-200 hover:shadow-lg"
                      style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                      onMouseEnter={e => gsap.to(e.currentTarget, { y: -4, duration: 0.2, ease: 'power2.out' })}
                      onMouseLeave={e => gsap.to(e.currentTarget, { y: 0, duration: 0.2, ease: 'power2.out' })}
                    >
                      {/* Colored header strip */}
                      <div
                        className="h-1.5 w-full"
                        style={{ background: isAvail ? 'var(--color-success)' : 'var(--color-warning)' }}
                      />

                      <div className="p-5 flex-1">
                        <div className="flex justify-between items-start mb-4">
                          <div>
                            <h3 className="text-lg font-bold" style={{ color: 'var(--color-text-primary)', fontFamily: 'var(--font-display)' }}>
                              {room.room_name}
                            </h3>
                            <div className="flex items-center gap-2 mt-1">
                              <span
                                className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md capitalize"
                                style={{ background: shareColor.light, color: shareColor.color }}
                              >
                                {room.sharing_type}
                              </span>
                              <span className="text-[11px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                                {room.capacity} persons
                              </span>
                            </div>
                          </div>
                          <span
                            className="text-[10px] font-bold px-2 py-1 rounded-[6px] uppercase tracking-wider flex-shrink-0"
                            style={{
                              background: isAvail ? 'var(--color-success-light)' : 'var(--color-warning-light)',
                              color: isAvail ? 'var(--color-success)' : 'var(--color-warning)',
                              border: `1px solid ${isAvail ? 'color-mix(in srgb, var(--color-success) 30%, transparent)' : 'color-mix(in srgb, var(--color-warning) 30%, transparent)'}`,
                            }}
                          >
                            {isAvail ? `${room.available_beds} beds free` : 'Full'}
                          </span>
                        </div>

                        {/* Price */}
                        <div className="mb-4">
                          <p className="text-[22px] font-extrabold" style={{ color: 'var(--color-primary)' }}>
                            ₹{Number(room.price_per_month).toLocaleString('en-IN')}
                          </p>
                          <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                            Per month
                          </p>
                        </div>

                        {/* Occupancy bar */}
                        <div className="mb-4">
                          <div className="flex justify-between items-center mb-1.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--color-text-muted)' }}>
                              Occupancy
                            </span>
                            <span className="text-[10px] font-bold" style={{ color: 'var(--color-text-primary)' }}>
                              {occupancyPct}%
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${occupancyPct}%`,
                                background: occupancyPct >= 90 ? 'var(--color-error)' : occupancyPct >= 70 ? 'var(--color-warning)' : 'var(--color-success)',
                              }}
                            />
                          </div>
                        </div>

                        {/* Amenity chips */}
                        <div className="flex flex-wrap gap-1.5">
                          {room.has_attached_bathroom && (
                            <span
                              className="px-2 py-1 rounded-md text-[10px] font-semibold"
                              style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
                            >
                              Attached Bath
                            </span>
                          )}
                          {room.is_ac && (
                            <span
                              className="px-2 py-1 rounded-md text-[10px] font-semibold"
                              style={{ background: 'var(--color-border)', color: 'var(--color-text-muted)' }}
                            >
                              AC Room
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Footer */}
                      <div
                        className="px-5 py-3 flex justify-end border-t"
                        style={{ borderColor: 'var(--color-border)', background: 'var(--color-background)' }}
                      >
                        <button
                          className="text-xs font-semibold flex items-center gap-1 transition-colors hover:opacity-70"
                          style={{ color: 'var(--color-primary)' }}
                        >
                          Edit details
                          <Icon name="chevron-right" className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
