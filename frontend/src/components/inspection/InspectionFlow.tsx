import { useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { useInspectionStore, type InspectionStep } from "@/stores/inspectionStore";
import { useCreateInspection, useTriggerDetection, useUploadPhoto } from "@/hooks/useInspection";
import { useDamageDetection } from "@/hooks/useDamageDetection";
import { PhotoCapture } from "@/components/camera/PhotoCapture";
import { PhotoPreview } from "@/components/camera/PhotoPreview";
import { Button } from "@/components/common/Button";
import { Card, CardHeader } from "@/components/common/Card";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import type { AssetType } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { fetchAssets } from "@/lib/api";

const STEP_LABELS: Record<InspectionStep, string> = {
  select_asset: "Select Asset",
  capture_before: "Before Photos",
  capture_after: "After Photos",
  analyzing: "AI Analysis",
  review: "Review Findings",
};

function assetTypeLabel(type: AssetType): string {
  switch (type) {
    case "jet_ski":
      return "Jet Ski";
    case "boat":
      return "Boat";
    case "parasail":
      return "Parasail";
    default:
      return type;
  }
}

export function InspectionFlow() {
  const navigate = useNavigate();

  const {
    currentStep,
    inspectionType,
    selectedAssetId,
    createdInspectionId,
    beforePhotos,
    afterPhotos,
    currentAngleIndex,
    setStep,
    setInspectionType,
    selectAsset,
    setCreatedInspectionId,
    setDetectionJobId,
    goToNextStep,
    goToPreviousStep,
    addPhoto,
    removePhoto,
    markPhotoUploaded,
    setCurrentAngleIndex,
    resetFlow,
  } = useInspectionStore();

  const createInspection = useCreateInspection();
  const triggerDetection = useTriggerDetection();
  const uploadPhotoMutation = useUploadPhoto();
  const detection = useDamageDetection();

  const { data: assetsData, isLoading: assetsLoading } = useQuery({
    queryKey: ["assets", { status: "available" }],
    queryFn: () => fetchAssets({ status: "available", page_size: 100 }),
    enabled: currentStep === "select_asset",
  });

  // Handle creating the inspection when moving from asset selection
  const handleAssetSelected = useCallback(
    async (assetId: string) => {
      selectAsset(assetId);
      try {
        const inspection = await createInspection.mutateAsync({
          asset_id: assetId,
          inspection_type: inspectionType,
          inspector_name: "Current User", // TODO: get from auth store
        });
        setCreatedInspectionId(inspection.id);
        goToNextStep();
      } catch {
        // Error handled by mutation state
      }
    },
    [selectAsset, createInspection, inspectionType, setCreatedInspectionId, goToNextStep],
  );

  // Handle photo capture
  const handlePhotoCapture = useCallback(
    (blob: Blob, angle: string) => {
      const dataUrl = URL.createObjectURL(blob);
      const photoType = currentStep === "capture_before" ? "before" : "after";
      const photo = {
        id: crypto.randomUUID(),
        blob,
        dataUrl,
        angle,
        position: angle,
        photoType: photoType as "before" | "after",
        timestamp: Date.now(),
        uploaded: false,
        uploadedId: null,
      };
      addPhoto(photo);

      // Upload immediately if online
      if (navigator.onLine && createdInspectionId) {
        void uploadPhotoMutation
          .mutateAsync({
            inspectionId: createdInspectionId,
            file: blob,
            metadata: {
              photo_type: photoType as "before" | "after",
              angle,
              position: angle,
            },
          })
          .then((result) => {
            markPhotoUploaded(photo.id, result.id);
          });
      }
    },
    [currentStep, addPhoto, createdInspectionId, uploadPhotoMutation, markPhotoUploaded],
  );

  // Handle triggering detection
  const handleTriggerDetection = useCallback(async () => {
    if (!createdInspectionId) return;
    setStep("analyzing");
    try {
      const result = await triggerDetection.mutateAsync({
        inspection_id: createdInspectionId,
      });
      setDetectionJobId(result.job_id);
      detection.startPolling(result.job_id, createdInspectionId);
    } catch {
      // Error handled by mutation state
    }
  }, [createdInspectionId, setStep, triggerDetection, setDetectionJobId, detection]);

  // Navigate to review when detection completes
  useEffect(() => {
    if (detection.status === "completed" && createdInspectionId) {
      setStep("review");
      navigate(`/inspections/${createdInspectionId}/review`);
    }
  }, [detection.status, createdInspectionId, setStep, navigate]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Revoke object URLs to prevent memory leaks
      beforePhotos.forEach((p) => URL.revokeObjectURL(p.dataUrl));
      afterPhotos.forEach((p) => URL.revokeObjectURL(p.dataUrl));
    };
    // Only on unmount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Get visible steps based on inspection type
  const visibleSteps: InspectionStep[] =
    inspectionType === "post_rental"
      ? ["select_asset", "capture_after", "analyzing", "review"]
      : ["select_asset", "capture_before", "capture_after", "analyzing", "review"];

  const currentStepIndex = visibleSteps.indexOf(currentStep);

  return (
    <div className="min-h-screen bg-dock-50">
      {/* Header */}
      <header className="bg-white border-b border-dock-200 sticky top-0 z-40">
        <div className="px-4 py-3 flex items-center justify-between">
          <button
            onClick={() => {
              resetFlow();
              navigate("/");
            }}
            className="text-dock-500 hover:text-navy-700 text-sm font-medium"
          >
            Cancel
          </button>
          <h1 className="text-base font-semibold text-navy-900">
            New Inspection
          </h1>
          <div className="w-16" />
        </div>

        {/* Progress bar */}
        <div className="flex px-4 pb-3 gap-1.5">
          {visibleSteps.map((step, index) => (
            <div key={step} className="flex-1 flex flex-col items-center gap-1">
              <div
                className={clsx(
                  "h-1 w-full rounded-full transition-colors",
                  index <= currentStepIndex
                    ? "bg-navy-600"
                    : "bg-dock-200",
                )}
              />
              <span
                className={clsx(
                  "text-[10px] font-medium",
                  index <= currentStepIndex
                    ? "text-navy-600"
                    : "text-dock-400",
                )}
              >
                {STEP_LABELS[step]}
              </span>
            </div>
          ))}
        </div>
      </header>

      {/* Step content */}
      <main>
        {/* Step 0: Select inspection type + asset */}
        {currentStep === "select_asset" && (
          <div className="p-4 space-y-6">
            {/* Inspection type selector */}
            <div>
              <label className="block text-sm font-medium text-navy-800 mb-2">
                Inspection Type
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(["pre_rental", "post_rental", "periodic"] as const).map(
                  (type) => (
                    <button
                      key={type}
                      onClick={() => setInspectionType(type)}
                      className={clsx(
                        "px-3 py-2.5 rounded-lg border text-sm font-medium transition-colors",
                        inspectionType === type
                          ? "border-navy-600 bg-navy-50 text-navy-700"
                          : "border-dock-200 bg-white text-dock-600 hover:border-dock-300",
                      )}
                    >
                      {type === "pre_rental"
                        ? "Pre-Rental"
                        : type === "post_rental"
                          ? "Post-Rental"
                          : "Periodic"}
                    </button>
                  ),
                )}
              </div>
            </div>

            {/* Asset list */}
            <div>
              <label className="block text-sm font-medium text-navy-800 mb-2">
                Select Equipment
              </label>
              {assetsLoading ? (
                <LoadingSpinner className="py-12" />
              ) : (
                <div className="space-y-2">
                  {assetsData?.items.map((asset) => (
                    <Card
                      key={asset.id}
                      hover
                      onClick={() => void handleAssetSelected(asset.id)}
                      className={clsx(
                        selectedAssetId === asset.id &&
                          "ring-2 ring-navy-500 border-navy-500",
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={clsx(
                            "w-10 h-10 rounded-lg flex items-center justify-center text-white font-semibold text-sm",
                            asset.asset_type === "jet_ski" && "bg-marine-500",
                            asset.asset_type === "boat" && "bg-navy-500",
                            asset.asset_type === "parasail" && "bg-amber-500",
                          )}
                        >
                          {asset.name.charAt(0)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-navy-900 truncate">
                            {asset.name}
                          </p>
                          <p className="text-xs text-dock-500">
                            {assetTypeLabel(asset.asset_type)} &middot;{" "}
                            {asset.registration_number}
                          </p>
                        </div>
                        <svg
                          className="w-5 h-5 text-dock-300"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={2}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M9 5l7 7-7 7"
                          />
                        </svg>
                      </div>
                    </Card>
                  ))}
                  {assetsData?.items.length === 0 && (
                    <p className="text-center py-8 text-dock-400 text-sm">
                      No available equipment found.
                    </p>
                  )}
                </div>
              )}
            </div>

            {createInspection.isError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                Failed to create inspection. Please try again.
              </div>
            )}
          </div>
        )}

        {/* Step 1: Before photos */}
        {currentStep === "capture_before" && (
          <div className="h-[calc(100vh-120px)]">
            {beforePhotos.length === 0 ? (
              <PhotoCapture
                photoType="before"
                currentAngleIndex={currentAngleIndex}
                photoCount={beforePhotos.length}
                onCapture={handlePhotoCapture}
                onAngleChange={setCurrentAngleIndex}
                onComplete={() => {
                  setCurrentAngleIndex(0);
                  goToNextStep();
                }}
                onBack={goToPreviousStep}
              />
            ) : (
              <div className="p-4 space-y-4">
                <PhotoPreview
                  photos={beforePhotos}
                  onDelete={removePhoto}
                  title="Before Photos"
                />
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    fullWidth
                    onClick={() => {
                      // Re-enter camera mode by removing all photos temporarily
                      // Actually, let's just open the camera for more
                    }}
                  >
                    Take More
                  </Button>
                  <Button
                    fullWidth
                    onClick={() => {
                      setCurrentAngleIndex(0);
                      goToNextStep();
                    }}
                  >
                    Continue
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 2: After photos */}
        {currentStep === "capture_after" && (
          <div className="h-[calc(100vh-120px)]">
            {afterPhotos.length === 0 ? (
              <PhotoCapture
                photoType="after"
                currentAngleIndex={currentAngleIndex}
                photoCount={afterPhotos.length}
                onCapture={handlePhotoCapture}
                onAngleChange={setCurrentAngleIndex}
                onComplete={() => void handleTriggerDetection()}
                onBack={goToPreviousStep}
              />
            ) : (
              <div className="p-4 space-y-4">
                <PhotoPreview
                  photos={afterPhotos}
                  onDelete={removePhoto}
                  title="After Photos"
                />
                <div className="flex gap-3">
                  <Button
                    variant="secondary"
                    fullWidth
                    onClick={goToPreviousStep}
                  >
                    Back
                  </Button>
                  <Button
                    fullWidth
                    onClick={() => void handleTriggerDetection()}
                    isLoading={triggerDetection.isPending}
                  >
                    Analyze Damage
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Analyzing */}
        {currentStep === "analyzing" && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center">
            {detection.error ? (
              <>
                <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4">
                  <svg
                    className="w-8 h-8 text-red-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-navy-900 mb-2">
                  Analysis Failed
                </h3>
                <p className="text-dock-500 mb-6 max-w-sm">{detection.error}</p>
                <Button onClick={() => void handleTriggerDetection()}>
                  Try Again
                </Button>
              </>
            ) : (
              <>
                <LoadingSpinner size="lg" className="mb-6" />
                <h3 className="text-lg font-semibold text-navy-900 mb-2">
                  Analyzing Photos
                </h3>
                <p className="text-dock-500 max-w-sm">
                  {detection.status === "queued"
                    ? "Your inspection is queued for analysis..."
                    : "AI is scanning for damage. This typically takes 15-30 seconds."}
                </p>
                {detection.findingsCount !== null && (
                  <p className="mt-3 text-sm text-marine-600 font-medium">
                    {detection.findingsCount} potential finding
                    {detection.findingsCount !== 1 ? "s" : ""} detected so far
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {/* Step 4: Review -- handled by /inspections/:id/review route */}
        {currentStep === "review" && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-green-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-navy-900 mb-2">
              Analysis Complete
            </h3>
            <p className="text-dock-500 mb-6">
              Redirecting to review...
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
