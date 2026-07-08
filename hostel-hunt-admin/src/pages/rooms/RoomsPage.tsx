import React, { useEffect, useState } from 'react';
import { DashboardLayout } from '../../components/common/DashboardLayout';
import { useTheme } from '../../contexts/ThemeContext';
import { hostelService, roomService } from '../../services/api';

interface Room {
  room_id: string;
  hostel: string;
  room_number: string;
  floor: number;
  occupancy_type: string;
  price: string;
  is_available: boolean;
  amenities: string[];
  created_at: string;
}

export const RoomsPage: React.FC = () => {
  const { theme } = useTheme();
  const [loading, setLoading] = useState(true);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [hostelId, setHostelId] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // First get the hostel to get the hostel ID
        const hRes = await hostelService.getHostels();
        const hostels = Array.isArray(hRes) ? hRes : hRes.data || hRes.results;
        
        if (hostels && hostels.length > 0) {
          const hid = hostels[0].hostel_id || hostels[0].id;
          setHostelId(hid);
          
          // Now fetch the rooms for this hostel
          if (hid) {
            const rRes = await roomService.getRooms(hid);
            const roomsData = Array.isArray(rRes) ? rRes : rRes.data || rRes.results;
            setRooms(roomsData || []);
          }
        }
      } catch (error) {
        console.error("Error fetching rooms data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const cardBg = theme === 'dark' ? 'bg-[#1A1A1A]' : 'bg-white';
  const cardBorder = theme === 'dark' ? 'border-[#2A2A2A]' : 'border-[#E8E5E0]';
  const textSub = theme === 'dark' ? 'text-[#9A9690]' : 'text-[#6B6B6B]';

  const availableRooms = rooms.filter(r => r.is_available).length;
  const occupiedRooms = rooms.length - availableRooms;

  return (
    <DashboardLayout title="Rooms Management">
      <div className="w-full animate-fade-in-up space-y-8">
        
        <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h1 className="text-[28px] font-bold">Rooms Management</h1>
            <p className={`${textSub} mt-1 font-medium`}>
              View and manage all rooms in your hostel
            </p>
          </div>
          {hostelId && (
            <button className="flex items-center gap-2 px-5 py-2 rounded-[10px] text-sm font-semibold transition-all bg-[#2A2A2A] hover:bg-[#3A3A3A] text-white">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Room
            </button>
          )}
        </header>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <svg className="w-8 h-8 animate-spin text-[#E8571A]" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : !hostelId ? (
          <div className={`py-20 text-center ${cardBg} border ${cardBorder} rounded-2xl`}>
            <div className="text-5xl mb-4">🛏</div>
            <h2 className="text-xl font-bold mb-2">Hostel Not Configured</h2>
            <p className={`${textSub} mb-6 max-w-md mx-auto`}>
              You need to set up your hostel first before managing rooms.
            </p>
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl flex items-center justify-between`}>
                <div>
                  <p className="text-[11px] uppercase tracking-widest font-bold text-[#9A9690] mb-1">Total Rooms</p>
                  <p className="text-3xl font-extrabold">{rooms.length}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center text-2xl">
                  🔢
                </div>
              </div>
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl flex items-center justify-between`}>
                <div>
                  <p className="text-[11px] uppercase tracking-widest font-bold text-[#9A9690] mb-1">Available</p>
                  <p className="text-3xl font-extrabold">{availableRooms}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-green-500/10 text-green-500 flex items-center justify-center text-2xl">
                  ✅
                </div>
              </div>
              <div className={`${cardBg} border ${cardBorder} p-6 rounded-2xl flex items-center justify-between`}>
                <div>
                  <p className="text-[11px] uppercase tracking-widest font-bold text-[#9A9690] mb-1">Occupied</p>
                  <p className="text-3xl font-extrabold">{occupiedRooms}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-orange-500/10 text-orange-500 flex items-center justify-center text-2xl">
                  🧍
                </div>
              </div>
            </div>

            {/* Room Grid */}
            {rooms.length === 0 ? (
              <div className={`py-20 text-center ${cardBg} border ${cardBorder} rounded-2xl`}>
                <div className="text-5xl mb-4">🚪</div>
                <h2 className="text-xl font-bold mb-2">No Rooms Added Yet</h2>
                <p className={`${textSub} mb-6 max-w-md mx-auto`}>
                  You haven't added any rooms to your hostel.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {rooms.map(room => (
                  <div key={room.room_id} className={`${cardBg} border ${cardBorder} rounded-2xl overflow-hidden card-hover transition-all`}>
                    <div className="p-5">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <h3 className="text-xl font-bold">Room {room.room_number}</h3>
                          <p className={`text-xs font-semibold uppercase tracking-wider ${textSub} mt-1`}>
                            Floor {room.floor} · {room.occupancy_type}
                          </p>
                        </div>
                        {room.is_available ? (
                          <span className="bg-green-500/10 text-green-400 border border-green-500/20 text-[10px] font-bold px-2 py-1 rounded-[6px] uppercase tracking-wider">
                            Available
                          </span>
                        ) : (
                          <span className="bg-orange-500/10 text-orange-400 border border-orange-500/20 text-[10px] font-bold px-2 py-1 rounded-[6px] uppercase tracking-wider">
                            Occupied
                          </span>
                        )}
                      </div>
                      
                      <div className="mb-4">
                        <p className="text-2xl font-bold text-[#E8571A]">₹{Number(room.price).toLocaleString('en-IN')}</p>
                        <p className={`text-[10px] font-semibold uppercase tracking-wider ${textSub}`}>Per month</p>
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {room.amenities && room.amenities.length > 0 ? (
                          room.amenities.map(am => (
                            <span key={am} className="px-2 py-1 bg-[#FFFFFF08] border border-[#2A2A2A] rounded-md text-[10px] font-medium text-[#9A9690] capitalize">
                              {am.replace('_', ' ')}
                            </span>
                          ))
                        ) : (
                          <span className={`text-[10px] font-medium ${textSub}`}>No amenities listed</span>
                        )}
                      </div>
                    </div>
                    
                    <div className="border-t border-[#2A2A2A] px-5 py-3 bg-[#FFFFFF02] flex justify-end">
                      <button className="text-[#9A9690] hover:text-white text-xs font-semibold flex items-center gap-1 transition-colors">
                        Edit details
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
};
