'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/common/DashboardLayout';
import { useTheme } from '@/contexts/ThemeContext';
import { hostelService } from '@/services/api';
import type { HostelEnrollmentState } from '@/types';

export default function MyHostelPage() {
  const { theme } = useTheme();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [hostel, setHostel] = useState<HostelEnrollmentState | null>(null);

  useEffect(() => {
    const fetchHostel = async () => {
      try {
        const res = await hostelService.getHostels();
        const hostels = Array.isArray(res) ? res : res.data || res.results;
        if (hostels && hostels.length > 0) {
          setHostel(hostels[0]);
        }
      } catch (error) {
        console.error("Error fetching hostel:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchHostel();
  }, []);

  const cardBg = theme === 'dark' ? 'bg-ivory-900' : 'bg-ivory-100';
  const cardBorder = theme === 'dark' ? 'border-ivory-700' : 'border-ivory-300';
  const textSub = theme === 'dark' ? 'text-ivory-500' : 'text-ink-700';

  return (
    <DashboardLayout title="My Hostel">
      <div className="w-full animate-fade-in-up max-w-5xl mx-auto space-y-8">
        <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold text-ink-900 dark:text-ivory-50">Hostel Overview</h1>
            <p className={`${textSub} mt-1 font-medium`}>
              Manage and view your hostel profile details
            </p>
          </div>
          <button
            onClick={() => router.push('/hostel/edit')}
            className="flex items-center gap-2 px-5 py-2 rounded-[10px] text-sm font-semibold transition-all bg-auburn-500 hover:bg-auburn-700 dark:bg-auburn-300 dark:hover:bg-auburn-100 text-ivory-50 dark:text-ink-900 auburn-glow"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit Profile
          </button>
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <svg className="w-8 h-8 animate-spin text-auburn-500 dark:text-auburn-300" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : !hostel ? (
          <div className={`py-20 text-center ${cardBg} border ${cardBorder} rounded-2xl`}>
            <div className="text-5xl mb-4">🏨</div>
            <h2 className="text-xl font-bold text-ink-900 dark:text-ivory-50 mb-2">No Hostel Configured</h2>
            <p className={`${textSub} mb-6 max-w-md mx-auto`}>
              You haven't set up your hostel yet. Add your details to start managing rooms and bookings.
            </p>
            <button
              onClick={() => router.push('/hostel/edit')}
              className="px-6 py-2.5 rounded-[10px] text-sm font-semibold bg-auburn-500 hover:bg-auburn-700 dark:bg-auburn-300 dark:hover:bg-auburn-100 text-ivory-50 dark:text-ink-900 transition-all"
            >
              Get Started
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl`}>
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center text-xl mb-4">📍</div>
                <p className="text-[11px] uppercase tracking-widest font-bold text-ink-700 dark:text-ivory-500 mb-1">Location</p>
                <p className="text-lg font-bold text-ink-900 dark:text-ivory-50">{hostel.locality || hostel.city}, {hostel.state}</p>
                <p className={`${textSub} text-sm mt-1 truncate`} title={hostel.address}>{hostel.address}</p>
              </div>
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl`}>
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center text-xl mb-4">🏢</div>
                <p className="text-[11px] uppercase tracking-widest font-bold text-ink-700 dark:text-ivory-500 mb-1">Building</p>
                <p className="text-lg font-bold text-ink-900 dark:text-ivory-50">{hostel.total_floors} Floors, {hostel.total_rooms} Rooms</p>
                <p className={`${textSub} text-sm mt-1 capitalize`}>{hostel.gender_type} Hostel</p>
              </div>
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl`}>
                <div className="w-10 h-10 rounded-xl bg-green-500/10 text-green-500 flex items-center justify-center text-xl mb-4">📞</div>
                <p className="text-[11px] uppercase tracking-widest font-bold text-ink-700 dark:text-ivory-500 mb-1">Contact</p>
                <p className="text-lg font-bold text-ink-900 dark:text-ivory-50 truncate" title={hostel.email}>{hostel.email}</p>
                <p className={`${textSub} text-sm mt-1`}>+91 {hostel.contact_number}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className={`lg:col-span-2 ${cardBg} border ${cardBorder} rounded-2xl p-6 lg:p-8 space-y-8`}>
                <div>
                  <h2 className="text-xl font-bold text-ink-900 dark:text-ivory-50 mb-3">{hostel.name}</h2>
                  <p className={`${textSub} leading-relaxed`}>
                    {hostel.description || 'No description provided.'}
                  </p>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-ink-900 dark:text-ivory-50 mb-4 flex items-center gap-2">
                    <span className="text-auburn-500 dark:text-auburn-300">✅</span> Amenities
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {hostel.amenities && hostel.amenities.length > 0 ? (
                      hostel.amenities.map(amenity => (
                        <span key={amenity} className="bg-ivory-300 dark:bg-ivory-700 text-ink-900 dark:text-ivory-50 text-xs font-semibold px-3 py-1.5 rounded-full capitalize">
                          {amenity.replace('_', ' ')}
                        </span>
                      ))
                    ) : (
                      <p className={`${textSub} text-sm`}>No amenities listed.</p>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-bold text-ink-900 dark:text-ivory-50 mb-4 flex items-center gap-2">
                    <span className="text-auburn-500 dark:text-auburn-300">📋</span> Rules & Policies
                  </h3>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="p-4 bg-ivory-50/50 dark:bg-ivory-50/5 border border-ivory-300 dark:border-ivory-700 rounded-xl">
                      <p className="text-[10px] uppercase tracking-widest font-bold text-ink-700 dark:text-ivory-500 mb-2">Check-in Policy</p>
                      <p className="text-sm font-medium text-ink-900 dark:text-ivory-50">{hostel.check_in_policy || 'Not specified'}</p>
                    </div>
                    <div className="p-4 bg-ivory-50/50 dark:bg-ivory-50/5 border border-ivory-300 dark:border-ivory-700 rounded-xl">
                      <p className="text-[10px] uppercase tracking-widest font-bold text-ink-700 dark:text-ivory-500 mb-2">Check-out Policy</p>
                      <p className="text-sm font-medium text-ink-900 dark:text-ivory-50">{hostel.check_out_policy || 'Not specified'}</p>
                    </div>
                    <div className="sm:col-span-2 p-4 bg-ivory-50/50 dark:bg-ivory-50/5 border border-ivory-300 dark:border-ivory-700 rounded-xl">
                      <p className="text-[10px] uppercase tracking-widest font-bold text-ink-700 dark:text-ivory-500 mb-2">General Rules</p>
                      <p className="text-sm font-medium text-ink-900 dark:text-ivory-50 whitespace-pre-wrap">{hostel.rules || 'Not specified'}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-6">
                <div className={`${cardBg} border ${cardBorder} rounded-2xl p-6`}>
                   <h3 className="text-sm font-bold mb-4 text-ink-700 dark:text-ivory-500 uppercase tracking-wider">Owner Details</h3>
                   <div className="flex items-center gap-4">
                     <div className="w-12 h-12 rounded-full bg-auburn-500/10 dark:bg-auburn-300/10 text-auburn-500 dark:text-auburn-300 flex items-center justify-center font-bold text-lg">
                       {hostel.owner_name ? hostel.owner_name.charAt(0) : 'O'}
                     </div>
                     <div>
                       <p className="font-bold text-ink-900 dark:text-ivory-50">{hostel.owner_name}</p>
                       <p className={`text-xs ${textSub}`}>Hostel Owner</p>
                     </div>
                   </div>
                </div>

                <div className={`${cardBg} border ${cardBorder} rounded-2xl p-6`}>
                   <h3 className="text-sm font-bold mb-4 text-ink-700 dark:text-ivory-500 uppercase tracking-wider">Room Occupancy Types</h3>
                   <div className="flex flex-col gap-2">
                     {hostel.occupancy_types && hostel.occupancy_types.length > 0 ? (
                       hostel.occupancy_types.map(type => (
                         <div key={type} className="flex items-center gap-3">
                           <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                           <span className="capitalize font-medium text-sm text-ink-900 dark:text-ivory-50">{type} Sharing</span>
                         </div>
                       ))
                     ) : (
                       <p className={`text-xs ${textSub}`}>No occupancy types specified</p>
                     )}
                   </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
