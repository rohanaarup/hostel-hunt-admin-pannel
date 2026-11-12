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
  locality: string;
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
  upload_error?: string;    // set when uploading or saving this file failed
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

export type BookingStatus = 'pending' | 'approved' | 'confirmed' | 'rejected' | 'cancelled' | 'checked_in' | 'checked_out' | 'verified';

export interface BookingUser {
  user_id: string;
  name: string;
  email: string;
  phone: string;
  profile_photo_url: string | null;
}

export type BookingPaymentMode = 'offline' | 'online';

/** Maps 1:1 to bookings table in PostgreSQL */
export interface Booking {
  id: string;
  hostel: string;
  hostel_name: string;          // Enriched by serializer
  room: string | null;
  room_display: string | null;  // Resolved room name (from FK or denormalised)
  room_name: string | null;
  floor_number: string | null;
  room_number: string | null;
  bed_number: string | null;
  student_name: string;
  student_phone: string;
  payment_mode: BookingPaymentMode;
  status: BookingStatus | 'paid' | 'rejected';
  amount: number | null;
  check_in_date: string | null;
  check_out_date: string | null;
  notes: string | null;
  marked_paid_by: string | null;
  marked_paid_at: string | null;
  /** The stay this paid booking became (null when it has none yet). */
  stay_id?: string | null;
  stay_status?: string | null;
  stay_needs_review?: boolean;
  created_at: string;
  updated_at: string;
}


// ─── Payment ──────────────────────────────────────────────────────────────────

export type PaymentStatus = 'CREATED' | 'PENDING' | 'SUCCESS' | 'FAILED' | 'REFUNDED' | 'VOIDED';
export type PaymentPurpose = 'BOOKING' | 'RENT';
export type PaymentSource = 'ONLINE' | 'OFFLINE_OWNER';

/** One online (Razorpay) payment, as returned by GET /payments/admin-list/. */
export interface Payment {
  id: string;
  booking: string;
  razorpay_order_id: string;
  amount: string; // decimal string in rupees, e.g. "6500.00"
  currency: string;
  status: PaymentStatus;
  /** Booking or Rent; source Online (Razorpay) or Offline (recorded by the owner); paid_via is UPI, CARD, CASH ... */
  purpose?: PaymentPurpose;
  source?: PaymentSource;
  paid_via?: string;
  receipt_number?: string;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
  student_name: string;
  student_phone: string;
  hostel_name: string;
  room_number: string;
  bed_number: string;
  attempts: unknown[];
}

// ─── Resident ─────────────────────────────────────────────────────────────────

export type ResidentStatus = 'active' | 'vacated' | 'notice_given';

export interface Resident {
  id: string;
  hostel: string;
  room: string | null;
  bed_number: string;
  name: string;
  phone: string;
  id_proof_type: string;
  id_proof_number: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  move_in_date: string;
  expected_move_out_date: string | null;
  status: ResidentStatus;
  linked_booking: string | null;
  created_at: string;
}

// ─── Notice ───────────────────────────────────────────────────────────────────

export interface Notice {
  id: string;
  hostel: string | null;
  title: string;
  body: string;
  posted_by: string;
  posted_at: string;
  expires_at: string | null;
  is_active: boolean;
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
  total_hostels: number;
  total_residents: number;
  /** The beds the owner entered across their hostels: the same number the occupancy rate divides by. */
  total_beds: number;
  occupancy_rate: number;
  /** Counted over ALL bookings (the bookings list is paged, so a page is not a total). */
  bookings_by_status: Record<'pending' | 'confirmed' | 'paid' | 'cancelled' | 'rejected', number>;
  bookings_by_payment_mode: Record<'offline' | 'online', number>;
  revenue_collected: number;
  revenue_pending: number;
  pending_bookings: number;
}

// ─── Hostel Enrollment Wizard State ──────────────────────────────────────────

export interface HostelEnrollmentState {
  // Step 1 – Basic Details
  hostel_id?: string;
  name: string;
  owner_name: string;
  contact_number: string;
  email: string;
  locality: string;
  address: string;
  city: string;
  state: string;
  // Chosen from the city and locality lists; the text fields above follow them.
  city_id: string;
  locality_id: string;
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
  floor_number: string;
  room_number: string;
  room_name: string;
  sharing_type: SharingType | '';
  capacity: string;
  bed_count: string;
  price_per_month: string;
  available_beds: string;
  has_attached_bathroom: boolean;
  is_ac: boolean;
  description: string;
  photos: MediaItem[];
}

export const INITIAL_ENROLLMENT_STATE: HostelEnrollmentState = {
  name: '', owner_name: '', contact_number: '', email: '',
  locality: '', address: '', city: '', state: '', city_id: '', locality_id: '', pincode: '',
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

// ─── Stays and rent (Phase 9) ─────────────────────────────────────────────────

export type BillingMode = 'ANNIVERSARY' | 'FIXED_DAY';
export type FirstPeriodPolicy = 'PRORATE' | 'FULL_MONTH';

/** A hostel's rent rule as the server stores it. */
export interface BillingConfig {
  hostel_id: string;
  hostel_name: string;
  locality: string;
  billing_mode: BillingMode;
  fixed_due_day: number | null;
  fixed_due_last_day: boolean;
  first_period_policy: FirstPeriodPolicy | null;
  payable_window_days: number;
  grace_days: number;
  monthly_rent: { min: string; max: string } | null;
  booking_payment_covers: 'FIRST_PERIOD_RENT';
  applies_to: 'new_stays';
  is_default: boolean;
}

/** The editable part of the rule (what PUT /hostels/{id}/billing/ takes). */
export interface BillingRule {
  billing_mode: BillingMode;
  fixed_due_day: number | null;
  fixed_due_last_day: boolean;
  first_period_policy: FirstPeriodPolicy | null;
  payable_window_days: number;
  grace_days: number;
}

export interface PreviewRow {
  label: string;
  kind: 'BOOKING_PERIOD' | 'RENT';
  period: string;
  due: string;
  amount: string;
  period_start: string;
  period_end: string;
  due_date: string;
  amount_rupees: string;
}
export interface PreviewResult { join_date: string; rows: PreviewRow[]; summary: string }

export type RentStatus = 'OVERDUE' | 'PAYABLE' | 'SCHEDULED' | 'PAID';
export type StayAction = 'record_payment' | 'send_reminder' | 'view' | 'receipt' | 'void' | 'end_stay';

export interface AdminStayRow {
  id: string;
  student_name: string;
  hostel_id: string;
  hostel_name: string;
  room_label: string;
  bed_label: string;
  rent_amount: string;
  join_date: string;
  stay_status: string;
  needs_review: boolean;
  status: RentStatus;
  status_label: string;
  next_due: { due_id: string | null; date: string; amount: string; days_left: number; status: string; payable: boolean } | null;
  primary_action: StayAction;
  allowed_actions: StayAction[];
  action_due_id: string | null;
  action_due: {
    due_id: string; period_start: string; period_end: string; period_label: string; due_date: string; amount: string;
  } | null;
  receipt_payment_id: string | null;
  void_due_id: string | null;
  last_payment: {
    payment_id: string; receipt_number: string; amount: string; paid_at: string | null; method: string; source: string;
  } | null;
}

export interface AdminStaysTotals {
  active_stays: number;
  overdue: { amount: string; count: number };
  due_this_week: { amount: string; count: number };
  collected_this_month: { amount: string; stays_paid: number; stays_total: number };
}

export interface AdminStaysPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: AdminStayRow[];
  totals: AdminStaysTotals;
  tab_counts: { all: number; overdue: number; due_this_week: number; paid: number };
  hostels: { id: string; name: string; locality: string }[];
}

export type OfflineMethod = 'CASH' | 'BANK_TRANSFER' | 'UPI_DIRECT';
