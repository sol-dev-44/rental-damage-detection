// ---- Enums and literal types ----

export type AssetType = "jet_ski" | "boat" | "parasail";

export type RentalSessionStatus =
  | "reserved"
  | "checked_out"
  | "checked_in"
  | "completed"
  | "cancelled";

export type InspectionType = "pre_rental" | "post_rental" | "periodic";

export type InspectionStatus =
  | "draft"
  | "capturing"
  | "analyzing"
  | "review"
  | "completed";

export type FindingStatus = "pending" | "confirmed" | "rejected" | "corrected";

export type DamageSeverity = "none" | "minor" | "moderate" | "severe" | "critical";

export type FeedbackType = "confirm" | "reject" | "correct";

// ---- Assets ----

export interface Asset {
  id: string;
  name: string;
  asset_type: AssetType;
  registration_number: string;
  manufacturer: string;
  model: string;
  year: number;
  status: "available" | "rented" | "maintenance" | "retired";
  image_url: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetCreate {
  name: string;
  asset_type: AssetType;
  registration_number: string;
  manufacturer: string;
  model: string;
  year: number;
  notes?: string;
}

export interface AssetUpdate {
  name?: string;
  status?: Asset["status"];
  notes?: string;
}

// ---- Rental Sessions ----

export interface RentalSession {
  id: string;
  asset_id: string;
  asset?: Asset;
  customer_name: string;
  customer_email: string | null;
  customer_phone: string | null;
  status: RentalSessionStatus;
  checkout_time: string;
  expected_return_time: string;
  actual_return_time: string | null;
  pre_inspection_id: string | null;
  post_inspection_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---- Inspections ----

export interface Inspection {
  id: string;
  asset_id: string;
  asset?: Asset;
  session_id: string | null;
  inspection_type: InspectionType;
  status: InspectionStatus;
  inspector_name: string;
  photos: Photo[];
  findings: Finding[];
  notes: string | null;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InspectionCreate {
  asset_id: string;
  session_id?: string;
  inspection_type: InspectionType;
  inspector_name: string;
  notes?: string;
}

// ---- Photos ----

export interface PhotoMetadata {
  angle: string;
  position: string;
  width: number;
  height: number;
  file_size: number;
  capture_device: string | null;
  gps_lat: number | null;
  gps_lng: number | null;
}

export interface Photo {
  id: string;
  inspection_id: string;
  url: string;
  thumbnail_url: string | null;
  photo_type: "before" | "after";
  metadata: PhotoMetadata;
  uploaded_at: string;
}

// ---- Findings ----

export interface Finding {
  id: string;
  inspection_id: string;
  photo_id: string;
  damage_type: string;
  severity: DamageSeverity;
  confidence: number;
  location_description: string;
  bounding_box: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  status: FindingStatus;
  reviewer_notes: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FindingReview {
  status: FindingStatus;
  severity?: DamageSeverity;
  damage_type?: string;
  location_description?: string;
  reviewer_notes?: string;
}

// ---- Feedback ----

export interface Feedback {
  id: string;
  finding_id: string;
  feedback_type: FeedbackType;
  original_severity: DamageSeverity;
  corrected_severity: DamageSeverity | null;
  original_damage_type: string;
  corrected_damage_type: string | null;
  notes: string | null;
  submitted_by: string;
  created_at: string;
}

export interface FeedbackCreate {
  finding_id: string;
  feedback_type: FeedbackType;
  corrected_severity?: DamageSeverity;
  corrected_damage_type?: string;
  notes?: string;
}

// ---- Detection ----

export interface DetectionRequest {
  inspection_id: string;
  compare_with_inspection_id?: string;
}

export interface DetectionResponse {
  job_id: string;
  inspection_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  findings_count: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// ---- Metrics ----

export interface AccuracyMetrics {
  overall_accuracy: number;
  total_findings: number;
  confirmed_count: number;
  rejected_count: number;
  corrected_count: number;
  pending_count: number;
  accuracy_by_asset_type: Record<
    AssetType,
    { accuracy: number; total: number }
  >;
  accuracy_by_damage_type: Record<
    string,
    { accuracy: number; total: number }
  >;
  accuracy_by_severity: Record<
    DamageSeverity,
    { accuracy: number; total: number }
  >;
  confidence_calibration: Array<{
    confidence_bucket: string;
    actual_accuracy: number;
    count: number;
  }>;
  trend: Array<{
    period: string;
    accuracy: number;
    total: number;
  }>;
}

// ---- Pagination ----

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ---- Query Filters ----

export interface InspectionFilters {
  asset_id?: string;
  inspection_type?: InspectionType;
  status?: InspectionStatus;
  page?: number;
  page_size?: number;
}

export interface AssetFilters {
  asset_type?: AssetType;
  status?: Asset["status"];
  search?: string;
  page?: number;
  page_size?: number;
}

export interface SessionFilters {
  asset_id?: string;
  status?: RentalSessionStatus;
  page?: number;
  page_size?: number;
}
