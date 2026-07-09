// ─── Auth & Owner ─────────────────────────────────────────────────────────────

export type AuthStep = 'identifier' | 'otp' | 'password' | 'complete';
export type SignupStep = 'identifier' | 'otp' | 'create_password';
export type ForgotStep = 'identifier' | 'otp' | 'new_password' | 'success';
export type IdentifierType = 'email' | 'phone';

/** Maps 1:1 to the owners table in PostgreSQL */
export interface Owner {
  owner_id: string;          // UUID primary key
  email: string | null;
  phone_number: string | null;
  display_name: string;
  // password_hash is NEVER stored on frontend – backend only
  is_verified: boolean;
  is_active: boolean;
  profile_photo_url: string | null;
  role: 'owner';
  created_at: string;        // ISO string
  updated_at: string;
}

/** Frontend-only auth user state (subset of Owner) */
export interface AuthUser {
  owner_id: string;
  email: string | null;
  phone_number: string | null;
  display_name: string;
  is_verified: boolean;
  role: 'owner';
}

export interface LoginCredentials {
  identifier: string;        // email or phone
  identifier_type: IdentifierType;
  password: string;
  remember_me: boolean;
}

export interface SignupPayload {
  identifier: string;
  identifier_type: IdentifierType;
  display_name: string;
  password: string;
}

export interface OtpPayload {
  identifier: string;
  identifier_type: IdentifierType;
  otp: string;
}

export interface ResetPasswordPayload {
  identifier: string;
  identifier_type: IdentifierType;
  otp: string;
  new_password: string;
}

// ─── Hostel ───────────────────────────────────────────────────────────────────

export type HostelGenderType = 'boys' | 'girls' | 'co_living';
export type OccupancyType = 'single' | 'double' | 'triple' | 'quad' | 'dormitory';

/** Maps 1:1 to hostels table in PostgreSQL */
export interface Hostel {
  hostel_id: string;
  owner_id: string;
  name: string;
  owner_name: string;
  contact_number: string;
  email: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  landmark: string;
  latitude: number | null;
  longitude: number | null;
  google_maps_url: string;
  gender_type: HostelGenderType;
  total_floors: number;
  total_rooms: number;
  total_beds: number;
  occupancy_types: OccupancyType[];
  description: string;
  rules: string;
  check_in_policy: string;
  check_out_policy: string;
  amenities: string[];
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

// ─── Media ────────────────────────────────────────────────────────────────────

export type MediaCategory = 'hostel' | 'room' | 'common_area' | 'video';

export interface MediaItem {
  id: string;               // local UUID before upload
  file?: File;              // only present before upload
  preview_url: string;      // data URL or remote URL
  category: MediaCategory;
  upload_progress: number;  // 0–100
  remote_url?: string;      // set after successful upload
  mime_type: string;
  file_name: string;
  order_index: number;
}

// ─── Room ─────────────────────────────────────────────────────────────────────

export type SharingType = 'single' | 'double' | 'triple' | 'quad' | 'dormitory';

/** Maps 1:1 to rooms table in PostgreSQL */
export interface Room {
  room_id: string;
  hostel_id: string;
  room_name: string;
  sharing_type: SharingType;
  capacity: number;
  price_per_month: number;
  available_beds: number;
  has_attached_bathroom: boolean;
  is_ac: boolean;
  description: string;
  photos: MediaItem[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ─── Booking ──────────────────────────────────────────────────────────────────

export type BookingStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'checked_in' | 'checked_out';

export interface BookingUser {
  user_id: string;
  name: string;
  email: string;
  phone: string;
  profile_photo_url: string | null;
}

/** Maps 1:1 to bookings table in PostgreSQL */
export interface Booking {
  booking_id: string;
  hostel_id: string;
  room_id: string;
  room_name: string;
  user: BookingUser;
  status: BookingStatus;
  check_in_date: string;
  check_out_date: string | null;
  requested_at: string;
  updated_at: string;
  notes: string;
}

// ─── Payment ──────────────────────────────────────────────────────────────────

export type PaymentStatus = 'pending' | 'completed' | 'failed' | 'refunded';
export type PaymentMethod = 'upi' | 'card' | 'bank_transfer' | 'cash';

export interface Payment {
  payment_id: string;
  booking_id: string;
  hostel_id: string;
  user_name: string;
  room_name: string;
  amount: number;
  status: PaymentStatus;
  method: PaymentMethod;
  transaction_ref: string | null;
  paid_at: string | null;
  created_at: string;
}

// ─── Activity ────────────────────────────────────────────────────────────────

export type ActivityType = 'booking_request' | 'booking_approved' | 'booking_rejected' | 'payment_received' | 'hostel_updated' | 'room_updated';

export interface ActivityItem {
  activity_id: string;
  type: ActivityType;
  title: string;
  description: string;
  timestamp: string;
  meta?: Record<string, unknown>;
}

// ─── Dashboard Stats ──────────────────────────────────────────────────────────

export interface DashboardStats {
  registered_hostel: boolean;
  total_rooms: number;
  available_rooms: number;
  occupied_rooms: number;
  pending_requests: number;
  booked_users: number;
  monthly_revenue: number;
  pending_payments: number;
}

// ─── Hostel Enrollment Wizard State ──────────────────────────────────────────

export interface HostelEnrollmentState {
  // Step 1 – Basic Details
  hostel_id?: string;
  name: string;
  owner_name: string;
  contact_number: string;
  email: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  google_maps_url: string;
  landmark: string;
  latitude: string;
  longitude: string;

  // Step 2 – Hostel Info
  gender_type: HostelGenderType | '';
  total_floors: string;
  total_rooms: string;
  total_beds: string;
  occupancy_types: OccupancyType[];
  description: string;
  rules: string;
  check_in_policy: string;
  check_out_policy: string;

  // Step 3 – Amenities
  amenities: string[];

  // Step 4 – Media
  media: MediaItem[];

  // Step 5 – Rooms
  rooms: RoomDraft[];
}

export interface RoomDraft {
  _draft_id: string;        // local only
  room_name: string;
  sharing_type: SharingType | '';
  capacity: string;
  price_per_month: string;
  available_beds: string;
  has_attached_bathroom: boolean;
  is_ac: boolean;
  description: string;
  photos: MediaItem[];
}

export const INITIAL_ENROLLMENT_STATE: HostelEnrollmentState = {
  name: '', owner_name: '', contact_number: '', email: '',
  address: '', city: '', state: '', pincode: '',
  google_maps_url: '', landmark: '', latitude: '', longitude: '',
  gender_type: '', total_floors: '', total_rooms: '', total_beds: '',
  occupancy_types: [], description: '', rules: '', check_in_policy: '', check_out_policy: '',
  amenities: [],
  media: [],
  rooms: [],
};

export const AMENITY_OPTIONS = [
  { key: 'wifi', label: 'WiFi', icon: '📶' },
  { key: 'ac', label: 'AC', icon: '❄️' },
  { key: 'food', label: 'Food', icon: '🍽️' },
  { key: 'laundry', label: 'Laundry', icon: '👕' },
  { key: 'cctv', label: 'CCTV', icon: '📷' },
  { key: 'parking', label: 'Parking', icon: '🅿️' },
  { key: 'housekeeping', label: 'Housekeeping', icon: '🧹' },
  { key: 'power_backup', label: 'Power Backup', icon: '🔋' },
  { key: 'security', label: 'Security', icon: '🛡️' },
  { key: 'lift', label: 'Lift', icon: '🛗' },
  { key: 'gym', label: 'Gym', icon: '💪' },
  { key: 'water_supply', label: 'Water Supply', icon: '💧' },
  { key: 'hot_water', label: 'Hot Water', icon: '🚿' },
  { key: 'study_room', label: 'Study Room', icon: '📚' },
  { key: 'recreation', label: 'Recreation Area', icon: '🎮' },
];
