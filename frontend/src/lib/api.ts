import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type {
  Asset,
  AssetCreate,
  AssetUpdate,
  AssetFilters,
  Inspection,
  InspectionCreate,
  InspectionFilters,
  RentalSession,
  SessionFilters,
  Finding,
  FindingReview,
  FeedbackCreate,
  Feedback,
  DetectionRequest,
  DetectionResponse,
  AccuracyMetrics,
  PaginatedResponse,
} from "./types";

// ---- Offline Queue ----

interface QueuedMutation {
  id: string;
  timestamp: number;
  method: "post" | "put" | "patch" | "delete";
  url: string;
  data?: unknown;
}

const QUEUE_KEY = "dockguard_offline_queue";

function getOfflineQueue(): QueuedMutation[] {
  try {
    const stored = localStorage.getItem(QUEUE_KEY);
    return stored ? (JSON.parse(stored) as QueuedMutation[]) : [];
  } catch {
    return [];
  }
}

function addToOfflineQueue(mutation: Omit<QueuedMutation, "id" | "timestamp">): void {
  const queue = getOfflineQueue();
  queue.push({
    ...mutation,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
  });
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

function removeFromOfflineQueue(id: string): void {
  const queue = getOfflineQueue().filter((m) => m.id !== id);
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}

export function getOfflineQueueCount(): number {
  return getOfflineQueue().length;
}

export async function flushOfflineQueue(): Promise<void> {
  const queue = getOfflineQueue();
  for (const mutation of queue) {
    try {
      await apiClient.request({
        method: mutation.method,
        url: mutation.url,
        data: mutation.data,
      });
      removeFromOfflineQueue(mutation.id);
    } catch {
      // Stop processing on first failure -- network may still be down
      break;
    }
  }
}

// ---- Axios Instance ----

export const apiClient = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Auth token interceptor
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("dockguard_auth_token");
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Offline queue interceptor for mutations
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (!navigator.onLine && error.config) {
      const method = error.config.method as string;
      if (["post", "put", "patch", "delete"].includes(method)) {
        addToOfflineQueue({
          method: method as QueuedMutation["method"],
          url: error.config.url ?? "",
          data: error.config.data ? JSON.parse(error.config.data as string) : undefined,
        });
        return Promise.resolve({ data: null, _offlineQueued: true });
      }
    }
    return Promise.reject(error);
  },
);

// Auto-flush offline queue when coming back online
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    void flushOfflineQueue();
  });
}

// ---- API Functions: Assets ----

export async function fetchAssets(
  filters?: AssetFilters,
): Promise<PaginatedResponse<Asset>> {
  const response = await apiClient.get<PaginatedResponse<Asset>>("/assets", {
    params: filters,
  });
  return response.data;
}

export async function fetchAsset(id: string): Promise<Asset> {
  const response = await apiClient.get<Asset>(`/assets/${id}`);
  return response.data;
}

export async function createAsset(data: AssetCreate): Promise<Asset> {
  const response = await apiClient.post<Asset>("/assets", data);
  return response.data;
}

export async function updateAsset(
  id: string,
  data: AssetUpdate,
): Promise<Asset> {
  const response = await apiClient.patch<Asset>(`/assets/${id}`, data);
  return response.data;
}

export async function deleteAsset(id: string): Promise<void> {
  await apiClient.delete(`/assets/${id}`);
}

// ---- API Functions: Inspections ----

export async function fetchInspections(
  filters?: InspectionFilters,
): Promise<PaginatedResponse<Inspection>> {
  const response = await apiClient.get<PaginatedResponse<Inspection>>(
    "/inspections",
    { params: filters },
  );
  return response.data;
}

export async function fetchInspection(id: string): Promise<Inspection> {
  const response = await apiClient.get<Inspection>(`/inspections/${id}`);
  return response.data;
}

export async function createInspection(
  data: InspectionCreate,
): Promise<Inspection> {
  const response = await apiClient.post<Inspection>("/inspections", data);
  return response.data;
}

export async function updateInspection(
  id: string,
  data: Partial<InspectionCreate>,
): Promise<Inspection> {
  const response = await apiClient.patch<Inspection>(
    `/inspections/${id}`,
    data,
  );
  return response.data;
}

// ---- API Functions: Photos ----

export async function uploadPhoto(
  inspectionId: string,
  file: Blob,
  metadata: {
    photo_type: "before" | "after";
    angle: string;
    position: string;
  },
): Promise<{ id: string; url: string }> {
  const formData = new FormData();
  formData.append("file", file, "photo.jpg");
  formData.append("photo_type", metadata.photo_type);
  formData.append("angle", metadata.angle);
  formData.append("position", metadata.position);

  const response = await apiClient.post<{ id: string; url: string }>(
    `/inspections/${inspectionId}/photos`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return response.data;
}

export async function deletePhoto(
  inspectionId: string,
  photoId: string,
): Promise<void> {
  await apiClient.delete(`/inspections/${inspectionId}/photos/${photoId}`);
}

// ---- API Functions: Detection ----

export async function triggerDetection(
  data: DetectionRequest,
): Promise<DetectionResponse> {
  const response = await apiClient.post<DetectionResponse>(
    "/detection/analyze",
    data,
  );
  return response.data;
}

export async function getDetectionStatus(
  jobId: string,
): Promise<DetectionResponse> {
  const response = await apiClient.get<DetectionResponse>(
    `/detection/status/${jobId}`,
  );
  return response.data;
}

// ---- API Functions: Findings ----

export async function reviewFinding(
  findingId: string,
  review: FindingReview,
): Promise<Finding> {
  const response = await apiClient.patch<Finding>(
    `/findings/${findingId}/review`,
    review,
  );
  return response.data;
}

// ---- API Functions: Feedback ----

export async function submitFeedback(
  data: FeedbackCreate,
): Promise<Feedback> {
  const response = await apiClient.post<Feedback>("/feedback", data);
  return response.data;
}

// ---- API Functions: Rental Sessions ----

export async function fetchSessions(
  filters?: SessionFilters,
): Promise<PaginatedResponse<RentalSession>> {
  const response = await apiClient.get<PaginatedResponse<RentalSession>>(
    "/sessions",
    { params: filters },
  );
  return response.data;
}

export async function fetchSession(id: string): Promise<RentalSession> {
  const response = await apiClient.get<RentalSession>(`/sessions/${id}`);
  return response.data;
}

// ---- API Functions: Metrics ----

export async function fetchAccuracyMetrics(): Promise<AccuracyMetrics> {
  const response = await apiClient.get<AccuracyMetrics>("/metrics/accuracy");
  return response.data;
}

// ---- Auth ----

export async function login(credentials: {
  email: string;
  password: string;
}): Promise<{ token: string; user: { id: string; name: string; email: string } }> {
  const response = await apiClient.post<{
    token: string;
    user: { id: string; name: string; email: string };
  }>("/auth/login", credentials);
  return response.data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}
