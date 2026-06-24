import React from 'react';
import { FormField, inputClass, selectClass, textareaClass } from '../../ui/FormField';
import type { HostelEnrollmentState, RoomDraft, SharingType } from '../../../types';

interface Props {
  data: HostelEnrollmentState;
  onChange: (key: keyof HostelEnrollmentState, value: unknown) => void;
}

function uid() { return Math.random().toString(36).slice(2, 10); }

const SHARING_OPTIONS: { value: SharingType; label: string }[] = [
  { value: 'single', label: 'Single' },
  { value: 'double', label: 'Double' },
  { value: 'triple', label: 'Triple' },
  { value: 'quad', label: '4-Bed' },
  { value: 'dormitory', label: 'Dormitory' },
];

const emptyRoom = (): RoomDraft => ({
  _draft_id: uid(),
  room_name: '',
  sharing_type: '',
  capacity: '',
  price_per_month: '',
  available_beds: '',
  has_attached_bathroom: false,
  is_ac: false,
  description: '',
  photos: [],
});

export const Step5RoomConfig: React.FC<Props> = ({ data, onChange }) => {
  const rooms = data.rooms;

  const addRoom = () => {
    onChange('rooms', [...rooms, emptyRoom()]);
  };

  const removeRoom = (id: string) => {
    onChange('rooms', rooms.filter(r => r._draft_id !== id));
  };

  const updateRoom = (id: string, key: keyof RoomDraft, value: unknown) => {
    onChange('rooms', rooms.map(r => r._draft_id === id ? { ...r, [key]: value } : r));
  };

  return (
    <div className="space-y-5 animate-fade-in-up">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-lg font-bold text-white mb-1">Room Configuration</h3>
          <p className="text-[#9A9690] text-sm">Add the room types available at your hostel.</p>
        </div>
        <button
          type="button"
          onClick={addRoom}
          className="flex items-center gap-2 bg-[#E8571A] hover:bg-[#FF6B35] text-white text-sm font-semibold px-4 py-2 rounded-[10px] transition-all orange-glow flex-shrink-0"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Add Room
        </button>
      </div>

      {rooms.length === 0 ? (
        <div className="border-2 border-dashed border-[#2A2A2A] rounded-[14px] p-12 text-center">
          <div className="text-4xl mb-3">🛏</div>
          <p className="text-white font-semibold mb-1">No rooms added yet</p>
          <p className="text-[#9A9690] text-sm mb-4">Click "Add Room" to configure your first room type.</p>
          <button
            type="button"
            onClick={addRoom}
            className="bg-[#E8571A]/10 hover:bg-[#E8571A]/20 text-[#E8571A] border border-[#E8571A]/30 font-semibold px-6 py-2.5 rounded-[10px] transition-all text-sm"
          >
            + Add First Room
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {rooms.map((room, idx) => (
            <RoomCard
              key={room._draft_id}
              room={room}
              index={idx}
              onUpdate={(key, val) => updateRoom(room._draft_id, key, val)}
              onRemove={() => removeRoom(room._draft_id)}
            />
          ))}

          <button
            type="button"
            onClick={addRoom}
            className="w-full py-3 border-2 border-dashed border-[#2A2A2A] hover:border-[#E8571A]/50 rounded-[12px] text-[#9A9690] hover:text-[#E8571A] text-sm font-semibold transition-all flex items-center justify-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Another Room
          </button>
        </div>
      )}
    </div>
  );
};

// ── Individual Room Card ──────────────────────────────────────────────────────

interface RoomCardProps {
  room: RoomDraft;
  index: number;
  onUpdate: (key: keyof RoomDraft, value: unknown) => void;
  onRemove: () => void;
}

const RoomCard: React.FC<RoomCardProps> = ({ room, index, onUpdate, onRemove }) => {
  const [expanded, setExpanded] = React.useState(true);

  return (
    <div className="bg-[#0F0F0F] border border-[#2A2A2A] rounded-[14px] overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#1A1A1A]">
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-3 flex-1 text-left"
        >
          <div className="w-8 h-8 bg-[#E8571A]/10 border border-[#E8571A]/20 rounded-[8px] flex items-center justify-center text-sm font-bold text-[#E8571A]">
            {index + 1}
          </div>
          <div>
            <p className="text-white font-semibold text-sm">
              {room.room_name || `Room ${index + 1}`}
            </p>
            <p className="text-[#9A9690] text-xs">
              {room.sharing_type ? `${room.sharing_type}` : 'Configure below'}
              {room.price_per_month ? ` · ₹${room.price_per_month}/mo` : ''}
            </p>
          </div>
          <svg className={`w-4 h-4 text-[#9A9690] ml-auto transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <button
          type="button"
          onClick={onRemove}
          className="ml-3 w-7 h-7 flex items-center justify-center text-[#4A4A4A] hover:text-red-400 hover:bg-red-500/10 rounded-[6px] transition-all"
          title="Remove room"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      {/* Card body */}
      {expanded && (
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField label="Room Name" required>
              <input value={room.room_name} onChange={e => onUpdate('room_name', e.target.value)}
                placeholder="Deluxe Double Room" className={inputClass()} />
            </FormField>

            <FormField label="Sharing Type" required>
              <select value={room.sharing_type} onChange={e => onUpdate('sharing_type', e.target.value)}
                className={selectClass()}>
                <option value="">Select type</option>
                {SHARING_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </FormField>

            <FormField label="Capacity (persons)" required>
              <input type="number" min="1" value={room.capacity}
                onChange={e => onUpdate('capacity', e.target.value)}
                placeholder="2" className={inputClass()} />
            </FormField>

            <FormField label="Price / Month (₹)" required>
              <input type="number" min="0" value={room.price_per_month}
                onChange={e => onUpdate('price_per_month', e.target.value)}
                placeholder="6000" className={inputClass()} />
            </FormField>

            <FormField label="Available Beds" required>
              <input type="number" min="0" value={room.available_beds}
                onChange={e => onUpdate('available_beds', e.target.value)}
                placeholder="2" className={inputClass()} />
            </FormField>
          </div>

          {/* Toggles */}
          <div className="flex gap-4">
            <ToggleChip
              label="Attached Bathroom"
              value={room.has_attached_bathroom}
              onChange={v => onUpdate('has_attached_bathroom', v)}
            />
            <ToggleChip
              label="AC Room"
              value={room.is_ac}
              onChange={v => onUpdate('is_ac', v)}
            />
          </div>

          <FormField label="Room Description">
            <textarea value={room.description}
              onChange={e => onUpdate('description', e.target.value)}
              rows={2} placeholder="Brief description of this room type..."
              className={textareaClass()} />
          </FormField>
        </div>
      )}
    </div>
  );
};

const ToggleChip: React.FC<{ label: string; value: boolean; onChange: (v: boolean) => void }> = ({
  label, value, onChange
}) => (
  <button
    type="button"
    onClick={() => onChange(!value)}
    className={`flex items-center gap-2 px-4 py-2 rounded-[10px] border text-sm font-semibold transition-all ${
      value
        ? 'border-[#E8571A] bg-[#E8571A]/10 text-[#E8571A]'
        : 'border-[#2A2A2A] text-[#9A9690] hover:border-[#3A3A3A]'
    }`}
  >
    <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${
      value ? 'bg-[#E8571A] border-[#E8571A]' : 'border-[#3A3A3A]'
    }`}>
      {value && <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
      </svg>}
    </div>
    {label}
  </button>
);
