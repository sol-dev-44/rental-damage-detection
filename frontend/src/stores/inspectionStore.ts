import { create } from "zustand";
import type { InspectionType } from "@/lib/types";

export type InspectionStep =
  | "select_asset"
  | "capture_before"
  | "capture_after"
  | "analyzing"
  | "review";

interface CapturedPhoto {
  id: string;
  blob: Blob;
  dataUrl: string;
  angle: string;
  position: string;
  photoType: "before" | "after";
  timestamp: number;
  uploaded: boolean;
  uploadedId: string | null;
}

interface OfflinePhotoEntry {
  inspectionId: string;
  photo: CapturedPhoto;
}

interface InspectionFlowState {
  // Flow state
  currentStep: InspectionStep;
  inspectionType: InspectionType;
  selectedAssetId: string | null;
  selectedSessionId: string | null;
  createdInspectionId: string | null;
  detectionJobId: string | null;

  // Photo capture state
  beforePhotos: CapturedPhoto[];
  afterPhotos: CapturedPhoto[];
  currentAngleIndex: number;

  // Offline queue
  offlinePhotoQueue: OfflinePhotoEntry[];

  // Actions -- flow
  setStep: (step: InspectionStep) => void;
  setInspectionType: (type: InspectionType) => void;
  selectAsset: (assetId: string) => void;
  selectSession: (sessionId: string | null) => void;
  setCreatedInspectionId: (id: string) => void;
  setDetectionJobId: (jobId: string) => void;
  goToNextStep: () => void;
  goToPreviousStep: () => void;

  // Actions -- photos
  addPhoto: (photo: CapturedPhoto) => void;
  removePhoto: (photoId: string) => void;
  markPhotoUploaded: (photoId: string, uploadedId: string) => void;
  setCurrentAngleIndex: (index: number) => void;

  // Actions -- offline
  addToOfflinePhotoQueue: (entry: OfflinePhotoEntry) => void;
  removeFromOfflinePhotoQueue: (photoId: string) => void;

  // Actions -- reset
  resetFlow: () => void;
}

const RECOMMENDED_ANGLES = [
  "bow",
  "stern",
  "port",
  "starboard",
  "deck_top",
  "hull_bottom",
  "interior",
  "engine",
];

const STEP_ORDER: InspectionStep[] = [
  "select_asset",
  "capture_before",
  "capture_after",
  "analyzing",
  "review",
];

const initialState = {
  currentStep: "select_asset" as InspectionStep,
  inspectionType: "post_rental" as InspectionType,
  selectedAssetId: null,
  selectedSessionId: null,
  createdInspectionId: null,
  detectionJobId: null,
  beforePhotos: [],
  afterPhotos: [],
  currentAngleIndex: 0,
  offlinePhotoQueue: [],
};

export const useInspectionStore = create<InspectionFlowState>()((set, get) => ({
  ...initialState,

  setStep: (step) => set({ currentStep: step }),

  setInspectionType: (type) => set({ inspectionType: type }),

  selectAsset: (assetId) => set({ selectedAssetId: assetId }),

  selectSession: (sessionId) => set({ selectedSessionId: sessionId }),

  setCreatedInspectionId: (id) => set({ createdInspectionId: id }),

  setDetectionJobId: (jobId) => set({ detectionJobId: jobId }),

  goToNextStep: () => {
    const { currentStep, inspectionType } = get();
    const currentIndex = STEP_ORDER.indexOf(currentStep);

    // For post_rental inspections, skip "capture_before" if it is the next step
    let nextIndex = currentIndex + 1;
    if (
      inspectionType === "post_rental" &&
      STEP_ORDER[nextIndex] === "capture_before"
    ) {
      nextIndex += 1;
    }

    const nextStep = STEP_ORDER[nextIndex];
    if (nextStep) {
      set({ currentStep: nextStep });
    }
  },

  goToPreviousStep: () => {
    const { currentStep, inspectionType } = get();
    const currentIndex = STEP_ORDER.indexOf(currentStep);

    let prevIndex = currentIndex - 1;
    if (
      inspectionType === "post_rental" &&
      STEP_ORDER[prevIndex] === "capture_before"
    ) {
      prevIndex -= 1;
    }

    const prevStep = STEP_ORDER[prevIndex];
    if (prevStep) {
      set({ currentStep: prevStep });
    }
  },

  addPhoto: (photo) => {
    if (photo.photoType === "before") {
      set((state) => ({ beforePhotos: [...state.beforePhotos, photo] }));
    } else {
      set((state) => ({ afterPhotos: [...state.afterPhotos, photo] }));
    }
  },

  removePhoto: (photoId) => {
    set((state) => ({
      beforePhotos: state.beforePhotos.filter((p) => p.id !== photoId),
      afterPhotos: state.afterPhotos.filter((p) => p.id !== photoId),
    }));
  },

  markPhotoUploaded: (photoId, uploadedId) => {
    set((state) => ({
      beforePhotos: state.beforePhotos.map((p) =>
        p.id === photoId ? { ...p, uploaded: true, uploadedId } : p,
      ),
      afterPhotos: state.afterPhotos.map((p) =>
        p.id === photoId ? { ...p, uploaded: true, uploadedId } : p,
      ),
    }));
  },

  setCurrentAngleIndex: (index) => set({ currentAngleIndex: index }),

  addToOfflinePhotoQueue: (entry) => {
    set((state) => ({
      offlinePhotoQueue: [...state.offlinePhotoQueue, entry],
    }));
  },

  removeFromOfflinePhotoQueue: (photoId) => {
    set((state) => ({
      offlinePhotoQueue: state.offlinePhotoQueue.filter(
        (e) => e.photo.id !== photoId,
      ),
    }));
  },

  resetFlow: () => set(initialState),
}));

export { RECOMMENDED_ANGLES };
