import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import { hostelService } from '../../services/api';
import type { HostelEnrollmentState } from '../../types';

export const MyHostelPage: React.FC = () => {
  const { theme } = useTheme();
  const navigate = useNavigate();
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

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';

  return (
    <DashboardLayout title="My Hostel">
      <div className="w-full animate-fade-in-up max-w-5xl mx-auto space-y-8">
        
        {/* Header Section */}
        <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold">Hostel Overview</h1>
            <p className={`${textSub} mt-1 font-medium`}>
              Manage and view your hostel profile details
            </p>
          </div>
          <button
            onClick={() => navigate('/hostel/edit')}
            className="flex items-center gap-2 px-5 py-2 rounded-[10px] text-sm font-semibold transition-all bg-[#E8571A] hover:bg-[#FF6B35] text-white orange-glow"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit Profile
          </button>
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <svg className="w-8 h-8 animate-spin text-[#E8571A]" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : !hostel ? (
          <div className={`py-20 text-center ${cardBg} border ${cardBorder} rounded-2xl`}>
            <div className="text-5xl mb-4">🏨</div>
            <h2 className="text-xl font-bold mb-2">No Hostel Configured</h2>
            <p className={`${textSub} mb-6 max-w-md mx-auto`}>
              You haven't set up your hostel yet. Add your details to start managing rooms and bookings.
            </p>
            <button
              onClick={() => navigate('/hostel/edit')}
              className="px-6 py-2.5 rounded-[10px] text-sm font-semibold bg-[#E8571A] hover:bg-[#FF6B35] text-white transition-all"
            >
              Get Started
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            
            {/* Quick Info Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl`}>
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center text-xl mb-4">📍</div>
                <p className="text-[11px] uppercase tracking-widest font-bold text-[#9A9690] mb-1">Location</p>
                <p className="text-lg font-bold">{hostel.city}, {hostel.state}</p>
                <p className={`${textSub} text-sm mt-1 truncate`} title={hostel.address}>{hostel.address}</p>
              </div>
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl`}>
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center text-xl mb-4">🏢</div>
                <p className="text-[11px] uppercase tracking-widest font-bold text-[#9A9690] mb-1">Building</p>
                <p className="text-lg font-bold">{hostel.total_floors} Floors, {hostel.total_rooms} Rooms</p>
                <p className={`${textSub} text-sm mt-1 capitalize`}>{hostel.gender_type} Hostel</p>
              </div>
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl`}>
                <div className="w-10 h-10 rounded-xl bg-green-500/10 text-green-500 flex items-center justify-center text-xl mb-4">📞</div>
                <p className="text-[11px] uppercase tracking-widest font-bold text-[#9A9690] mb-1">Contact</p>
                <p className="text-lg font-bold truncate" title={hostel.email}>{hostel.email}</p>
                <p className={`${textSub} text-sm mt-1`}>+91 {hostel.contact_number}</p>
              </div>
            </div>

            {/* Main Content Area */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column (Details) */}
              <div className={`lg:col-span-2 ${cardBg} border ${cardBorder} rounded-2xl p-6 lg:p-8 space-y-8`}>
                <div>
                  <h2 className="text-xl font-bold mb-3">{hostel.name}</h2>
                  <p className={`${textSub} leading-relaxed`}>
                    {hostel.description || 'No description provided.'}
                  </p>
                </div>

                <div>
                  <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                    <span className="text-[#E8571A]">✅</span> Amenities
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {hostel.amenities && hostel.amenities.length > 0 ? (
                      hostel.amenities.map(amenity => (
                        <span key={amenity} className="bg-[#2A2A2A] text-white text-xs font-semibold px-3 py-1.5 rounded-full capitalize">
                          {amenity.replace('_', ' ')}
                        </span>
                      ))
                    ) : (
                      <p className={`${textSub} text-sm`}>No amenities listed.</p>
                    )}
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                    <span className="text-[#E8571A]">📋</span> Rules & Policies
                  </h3>
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="p-4 bg-[#FFFFFF05] border border-[#2A2A2A] rounded-xl">
                      <p className="text-[10px] uppercase tracking-widest font-bold text-[#9A9690] mb-2">Check-in Policy</p>
                      <p className="text-sm font-medium">{hostel.check_in_policy || 'Not specified'}</p>
                    </div>
                    <div className="p-4 bg-[#FFFFFF05] border border-[#2A2A2A] rounded-xl">
                      <p className="text-[10px] uppercase tracking-widest font-bold text-[#9A9690] mb-2">Check-out Policy</p>
                      <p className="text-sm font-medium">{hostel.check_out_policy || 'Not specified'}</p>
                    </div>
                    <div className="sm:col-span-2 p-4 bg-[#FFFFFF05] border border-[#2A2A2A] rounded-xl">
                      <p className="text-[10px] uppercase tracking-widest font-bold text-[#9A9690] mb-2">General Rules</p>
                      <p className="text-sm font-medium whitespace-pre-wrap">{hostel.rules || 'Not specified'}</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column (Sidebar) */}
              <div className="space-y-6">
                <div className={`${cardBg} border ${cardBorder} rounded-2xl p-6`}>
                   <h3 className="text-sm font-bold mb-4 text-[#9A9690] uppercase tracking-wider">Owner Details</h3>
                   <div className="flex items-center gap-4">
                     <div className="w-12 h-12 rounded-full bg-[#E8571A]/10 text-[#E8571A] flex items-center justify-center font-bold text-lg">
                       {hostel.owner_name ? hostel.owner_name.charAt(0) : 'O'}
                     </div>
                     <div>
                       <p className="font-bold">{hostel.owner_name}</p>
                       <p className={`text-xs ${textSub}`}>Hostel Owner</p>
                     </div>
                   </div>
                </div>

                <div className={`${cardBg} border ${cardBorder} rounded-2xl p-6`}>
                   <h3 className="text-sm font-bold mb-4 text-[#9A9690] uppercase tracking-wider">Room Occupancy Types</h3>
                   <div className="flex flex-col gap-2">
                     {hostel.occupancy_types && hostel.occupancy_types.length > 0 ? (
                       hostel.occupancy_types.map(type => (
                         <div key={type} className="flex items-center gap-3">
                           <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                           <span className="capitalize font-medium text-sm">{type} Sharing</span>
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
};
