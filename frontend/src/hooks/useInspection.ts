import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import {
  fetchInspections,
  fetchInspection,
  createInspection,
  triggerDetection,
  uploadPhoto,
  reviewFinding,
  submitFeedback,
} from "@/lib/api";
import type {
  Inspection,
  InspectionCreate,
  InspectionFilters,
  DetectionRequest,
  DetectionResponse,
  PaginatedResponse,
  FindingReview,
  Finding,
  FeedbackCreate,
  Feedback,
} from "@/lib/types";

// ---- Query Keys ----

export const inspectionKeys = {
  all: ["inspections"] as const,
  lists: () => [...inspectionKeys.all, "list"] as const,
  list: (filters: InspectionFilters) =>
    [...inspectionKeys.lists(), filters] as const,
  details: () => [...inspectionKeys.all, "detail"] as const,
  detail: (id: string) => [...inspectionKeys.details(), id] as const,
};

// ---- Queries ----

export function useInspections(
  filters: InspectionFilters = {},
  options?: Partial<UseQueryOptions<PaginatedResponse<Inspection>>>,
) {
  return useQuery({
    queryKey: inspectionKeys.list(filters),
    queryFn: () => fetchInspections(filters),
    ...options,
  });
}

export function useInspection(
  id: string,
  options?: Partial<UseQueryOptions<Inspection>>,
) {
  return useQuery({
    queryKey: inspectionKeys.detail(id),
    queryFn: () => fetchInspection(id),
    enabled: Boolean(id),
    ...options,
  });
}

// ---- Mutations ----

export function useCreateInspection() {
  const queryClient = useQueryClient();

  return useMutation<Inspection, Error, InspectionCreate>({
    mutationFn: createInspection,
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: inspectionKeys.lists(),
      });
    },
  });
}

export function useTriggerDetection() {
  const queryClient = useQueryClient();

  return useMutation<DetectionResponse, Error, DetectionRequest>({
    mutationFn: triggerDetection,
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: inspectionKeys.detail(variables.inspection_id),
      });
    },
  });
}

export function useUploadPhoto() {
  const queryClient = useQueryClient();

  return useMutation<
    { id: string; url: string },
    Error,
    {
      inspectionId: string;
      file: Blob;
      metadata: {
        photo_type: "before" | "after";
        angle: string;
        position: string;
      };
    }
  >({
    mutationFn: ({ inspectionId, file, metadata }) =>
      uploadPhoto(inspectionId, file, metadata),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: inspectionKeys.detail(variables.inspectionId),
      });
    },
  });
}

export function useReviewFinding() {
  const queryClient = useQueryClient();

  return useMutation<
    Finding,
    Error,
    { findingId: string; review: FindingReview; inspectionId: string }
  >({
    mutationFn: ({ findingId, review }) => reviewFinding(findingId, review),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: inspectionKeys.detail(variables.inspectionId),
      });
    },
  });
}

export function useSubmitFeedback() {
  return useMutation<Feedback, Error, FeedbackCreate>({
    mutationFn: submitFeedback,
  });
}
