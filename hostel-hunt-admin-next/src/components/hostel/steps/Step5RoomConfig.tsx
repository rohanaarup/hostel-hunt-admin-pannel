'use client';

import React, { useState } from 'react';
import FormField, { inputClass, selectClass } from '@/components/ui/FormField';
import type { HostelEnrollmentState, RoomDraft, SharingType } from '@/types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
}

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

const SHARING_OPTIONS: { value: SharingType; label: string }[] = [
  { value: 'single', label: 'Single' },
  { value: 'double', label: 'Double' },
  { value: 'triple', label: 'Triple' },
  { value: 'quad', label: '4-Bed' },
  { value: 'dormitory', label: 'Dormitory' },
];

export default function Step5RoomConfig({ data, onChange }: Props) {
  const rooms = data.rooms;
  
  // Bulk generation state
  const [showBulkGenerator, setShowBulkGenerator] = useState(rooms.length === 0);
  const [numFloors, setNumFloors] = useState('3');
  const [roomsPerFloor, setRoomsPerFloor] = useState('10');
  const [bedsPerRoom, setBedsPerRoom] = useState('2');
  const [defaultSharing, setDefaultSharing] = useState<SharingType>('double');
  const [defaultPrice, setDefaultPrice] = useState('6000');
  const [isAC, setIsAC] = useState(false);
  const [hasBathroom, setHasBathroom] = useState(true);

  const generateRooms = () => {
    const floorCount = parseInt(numFloors) || 0;
    const roomCount = parseInt(roomsPerFloor) || 0;
    const bedCount = parseInt(bedsPerRoom) || 1;
    
    if (floorCount <= 0 || roomCount <= 0) return;

    const newRooms: RoomDraft[] = [];
    
    for (let f = 1; f <= floorCount; f++) {
      for (let r = 1; r <= roomCount; r++) {
        const floorStr = f.toString();
        const roomStr = r.toString().padStart(2, '0');
        const roomNumber = `${floorStr}${roomStr}`; // e.g. 101, 102
        
        newRooms.push({
          _draft_id: uid(),
          floor_number: floorStr,
          room_number: roomNumber,
          room_name: `Room ${roomNumber}`,
          sharing_type: defaultSharing,
          capacity: bedCount.toString(),
          bed_count: bedCount.toString(),
          available_beds: bedCount.toString(),
          price_per_month: defaultPrice,
          has_attached_bathroom: hasBathroom,
          is_ac: isAC,
          description: '',
          photos: [],
        });
      }
    }
    
    onChange('rooms', [...rooms, ...newRooms]);
    setShowBulkGenerator(false);
  };

  const addCustomRoom = () => {
    onChange('rooms', [
      ...rooms,
      {
        _draft_id: uid(),
        floor_number: '1',
        room_number: '',
        room_name: '',
        sharing_type: '',
        capacity: '1',
        bed_count: '1',
        available_beds: '1',
        price_per_month: '',
        has_attached_bathroom: false,
        is_ac: false,
        description: '',
        photos: [],
      },
    ]);
  };

  const removeRoom = (id: string) => {
    onChange('rooms', rooms.filter((r) => r._draft_id !== id));
  };

  const updateRoom = (id: string, key: keyof RoomDraft, value: unknown) => {
    onChange('rooms', rooms.map((r) => (r._draft_id === id ? { ...r, [key]: value } : r)));
  };

  const updateRoomFields = (id: string, fields: Partial<RoomDraft>) => {
    onChange('rooms', rooms.map((r) => (r._draft_id === id ? { ...r, ...fields } : r)));
  };

  // Summary logic
  const uniqueFloors = new Set(rooms.map(r => r.floor_number)).size;
  const totalRooms = rooms.length;
  const totalBeds = rooms.reduce((acc, r) => acc + (parseInt(r.bed_count) || 0), 0);
  const avgPrice = rooms.length > 0 
    ? Math.round(rooms.reduce((acc, r) => acc + (parseInt(r.price_per_month) || 0), 0) / rooms.length)
    : 0;

  return (
    <div className="space-y-6 animate-fade-in-up pb-24">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-lg font-bold text-ink-900 dark:text-ivory-50 mb-1">Room Configuration</h3>
          <p className="text-ink-700 dark:text-ivory-500 text-sm">Bulk generate rooms or add them individually.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowBulkGenerator(!showBulkGenerator)}
          className="flex items-center gap-2 bg-auburn-500/10 text-auburn-500 dark:bg-auburn-300/10 dark:text-auburn-300 text-sm font-semibold px-4 py-2 rounded-[10px] transition-all flex-shrink-0"
        >
          {showBulkGenerator ? 'Hide Generator' : 'Bulk Generator'}
        </button>
      </div>

      {/* SECTION A: Bulk Generator */}
      {showBulkGenerator && (
        <div className="bg-ivory-50 dark:bg-ivory-950 border border-auburn-500/30 rounded-[14px] p-6 shadow-sm mb-6">
          <h4 className="text-base font-bold text-ink-900 dark:text-ivory-50 mb-4 flex items-center gap-2">
            <span className="text-xl">⚡</span> Quick Bulk Setup
          </h4>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            <FormField label="Number of Floors" required>
              <input type="number" min="1" max="20" value={numFloors} onChange={(e) => setNumFloors(e.target.value)} className={inputClass()} />
            </FormField>
            <FormField label="Rooms per Floor" required>
              <input type="number" min="1" max="50" value={roomsPerFloor} onChange={(e) => setRoomsPerFloor(e.target.value)} className={inputClass()} />
            </FormField>
            <FormField label="Beds per Room" required>
              <input type="number" min="1" max="10" value={bedsPerRoom} onChange={(e) => setBedsPerRoom(e.target.value)} className={inputClass()} />
            </FormField>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <FormField label="Default Sharing Type" required>
              <select value={defaultSharing} onChange={(e) => setDefaultSharing(e.target.value as SharingType)} className={selectClass()}>
                {SHARING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </FormField>
            <FormField label="Default Price/Month (₹)" required>
              <input type="number" min="0" value={defaultPrice} onChange={(e) => setDefaultPrice(e.target.value)} className={inputClass()} />
            </FormField>
          </div>

          <div className="flex flex-wrap gap-4 mb-6">
            <ToggleChip label="AC Rooms?" value={isAC} onChange={setIsAC} />
            <ToggleChip label="Attached Bathrooms?" value={hasBathroom} onChange={setHasBathroom} />
          </div>

          <button
            type="button"
            onClick={generateRooms}
            className="w-full bg-auburn-500 hover:bg-auburn-600 dark:bg-auburn-300 dark:hover:bg-auburn-400 text-ivory-50 dark:text-ink-900 font-bold py-3 rounded-[10px] transition-all auburn-glow"
          >
            Generate Rooms Now
          </button>
        </div>
      )}

      {/* SECTION B: Room List */}
      <div className="space-y-3">
        <div className="flex justify-between items-center mb-2">
          <h4 className="font-semibold text-ink-900 dark:text-ivory-50">Room List</h4>
          <button
            type="button"
            onClick={addCustomRoom}
            className="text-sm font-semibold text-auburn-500 hover:text-auburn-600 dark:text-auburn-300 transition-colors"
          >
            + Add Custom Room
          </button>
        </div>

        {rooms.length === 0 && !showBulkGenerator && (
          <div className="border-2 border-dashed border-ivory-300 dark:border-ivory-700 rounded-[14px] p-8 text-center text-ink-700 dark:text-ivory-500 text-sm">
            No rooms added. Use the Bulk Generator or add a custom room.
          </div>
        )}

        {rooms.map((room) => (
          <div key={room._draft_id} className="flex flex-wrap items-center gap-3 bg-white dark:bg-ivory-900 border border-ivory-200 dark:border-ivory-700 p-3 rounded-[12px] shadow-sm">
            <div className="w-16">
              <label className="block text-[10px] font-semibold text-ink-500 mb-1 uppercase tracking-wider">Floor</label>
              <input type="number" value={room.floor_number} onChange={(e) => updateRoom(room._draft_id, 'floor_number', e.target.value)} className={`${inputClass()} !py-1.5 !px-2 text-sm`} />
            </div>
            <div className="w-24">
              <label className="block text-[10px] font-semibold text-ink-500 mb-1 uppercase tracking-wider">Room No</label>
              <input value={room.room_number} onChange={(e) => updateRoomFields(room._draft_id, { room_number: e.target.value, room_name: `Room ${e.target.value}` })} className={`${inputClass()} !py-1.5 !px-2 text-sm`} />
            </div>
            <div className="w-28 flex-shrink-0">
              <label className="block text-[10px] font-semibold text-ink-500 mb-1 uppercase tracking-wider">Type</label>
              <select value={room.sharing_type} onChange={(e) => updateRoom(room._draft_id, 'sharing_type', e.target.value)} className={`${selectClass()} !py-1.5 !px-2 text-sm`}>
                <option value="">Select</option>
                {SHARING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div className="w-20">
              <label className="block text-[10px] font-semibold text-ink-500 mb-1 uppercase tracking-wider">Beds</label>
              <input type="number" value={room.bed_count} onChange={(e) => {
                updateRoomFields(room._draft_id, {
                  bed_count: e.target.value,
                  capacity: e.target.value,
                  available_beds: e.target.value
                });
              }} className={`${inputClass()} !py-1.5 !px-2 text-sm`} />
            </div>
            <div className="w-28">
              <label className="block text-[10px] font-semibold text-ink-500 mb-1 uppercase tracking-wider">Price (₹)</label>
              <input type="number" value={room.price_per_month} onChange={(e) => updateRoom(room._draft_id, 'price_per_month', e.target.value)} className={`${inputClass()} !py-1.5 !px-2 text-sm`} />
            </div>
            <div className="flex gap-2 ml-auto items-end h-[38px] pb-1">
              <button 
                type="button" 
                onClick={() => updateRoom(room._draft_id, 'is_ac', !room.is_ac)}
                className={`text-xs px-2 py-1 rounded border ${room.is_ac ? 'bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300' : 'text-ink-500 border-ivory-300'}`}
              >
                AC
              </button>
              <button 
                type="button" 
                onClick={() => updateRoom(room._draft_id, 'has_attached_bathroom', !room.has_attached_bathroom)}
                className={`text-xs px-2 py-1 rounded border ${room.has_attached_bathroom ? 'bg-green-100 text-green-700 border-green-300 dark:bg-green-900/30 dark:text-green-300' : 'text-ink-500 border-ivory-300'}`}
              >
                Bath
              </button>
              <button
                type="button"
                onClick={() => removeRoom(room._draft_id)}
                className="w-7 h-7 flex items-center justify-center text-ink-500 hover:text-red-500 hover:bg-red-50 ml-2 rounded transition-colors"
                title="Remove room"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* SECTION C: Summary Bar */}
      {rooms.length > 0 && (
        <div className="fixed bottom-[80px] left-0 right-0 md:left-64 flex justify-center pointer-events-none z-10 px-4">
          <div className="bg-ink-900 text-ivory-50 dark:bg-ivory-100 dark:text-ink-900 px-6 py-3 rounded-full shadow-lg text-sm font-semibold flex items-center gap-4 pointer-events-auto backdrop-blur-md bg-opacity-90 dark:bg-opacity-90">
            <span>{uniqueFloors} {uniqueFloors === 1 ? 'Floor' : 'Floors'}</span>
            <span className="w-1 h-1 bg-ivory-500 rounded-full"></span>
            <span>{totalRooms} Rooms</span>
            <span className="w-1 h-1 bg-ivory-500 rounded-full"></span>
            <span>{totalBeds} Total Beds</span>
            <span className="w-1 h-1 bg-ivory-500 rounded-full"></span>
            <span className="text-auburn-300 dark:text-auburn-500">Avg ₹{avgPrice}/mo</span>
          </div>
        </div>
      )}
    </div>
  );
}

const ToggleChip: React.FC<{ label: string; value: boolean; onChange: (v: boolean) => void }> = ({ label, value, onChange }) => (
  <button
    type="button"
    onClick={() => onChange(!value)}
    className={`flex items-center gap-2 px-4 py-2 rounded-[10px] border text-sm font-semibold transition-all ${
      value
        ? 'border-auburn-500 bg-auburn-500/10 text-auburn-500 dark:border-auburn-300 dark:bg-auburn-300/10 dark:text-auburn-300'
        : 'border-ivory-300 text-ink-700 hover:border-ivory-400 dark:border-ivory-700 dark:text-ivory-500 dark:hover:border-ivory-600'
    }`}
  >
    <div
      className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${
        value ? 'bg-auburn-500 border-auburn-500 dark:bg-auburn-300 dark:border-auburn-300' : 'border-ivory-300 dark:border-ivory-600'
      }`}
    >
      {value && <svg className="w-2.5 h-2.5 text-ivory-50 dark:text-ink-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
      </svg>}
    </div>
    {label}
  </button>
);
