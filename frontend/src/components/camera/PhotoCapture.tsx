import { useCallback, useEffect } from "react";
import clsx from "clsx";
import { useCamera } from "@/hooks/useCamera";
import { Button } from "@/components/common/Button";
import { RECOMMENDED_ANGLES } from "@/stores/inspectionStore";

interface PhotoCaptureProps {
  photoType: "before" | "after";
  currentAngleIndex: number;
  photoCount: number;
  maxPhotos?: number;
  onCapture: (blob: Blob, angle: string) => void;
  onAngleChange: (index: number) => void;
  onComplete: () => void;
  onBack?: () => void;
}

export function PhotoCapture({
  photoType,
  currentAngleIndex,
  photoCount,
  maxPhotos = 8,
  onCapture,
  onAngleChange,
  onComplete,
  onBack,
}: PhotoCaptureProps) {
  const {
    videoRef,
    canvasRef,
    isReady,
    error,
    startCamera,
    stopCamera,
    capturePhoto,
    switchCamera,
    hasPermission,
  } = useCamera({ facingMode: "environment" });

  useEffect(() => {
    void startCamera();
    return () => stopCamera();
  }, [startCamera, stopCamera]);

  const currentAngle = RECOMMENDED_ANGLES[currentAngleIndex] ?? "general";

  const handleCapture = useCallback(() => {
    const blob = capturePhoto();
    if (blob) {
      onCapture(blob, currentAngle);
      // Advance to next angle
      if (currentAngleIndex < RECOMMENDED_ANGLES.length - 1) {
        onAngleChange(currentAngleIndex + 1);
      }
    }
  }, [capturePhoto, currentAngle, currentAngleIndex, onCapture, onAngleChange]);

  const formatAngleName = (angle: string): string => {
    return angle.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  if (hasPermission === false) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center">
        <svg
          className="w-16 h-16 text-dock-300 mb-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z"
          />
        </svg>
        <h3 className="text-lg font-semibold text-navy-900 mb-2">
          Camera Access Required
        </h3>
        <p className="text-dock-500 mb-6 max-w-sm">
          Please enable camera access in your browser settings to capture
          inspection photos.
        </p>
        <Button onClick={() => void startCamera()}>Try Again</Button>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <Button onClick={() => void startCamera()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-black relative">
      {/* Camera preview */}
      <div className="relative flex-1 flex items-center justify-center overflow-hidden">
        <video
          ref={videoRef}
          className="w-full h-full object-cover"
          autoPlay
          playsInline
          muted
        />
        <canvas ref={canvasRef} className="hidden" />

        {/* Guide overlay */}
        <div className="absolute inset-0 pointer-events-none">
          {/* Angle guide label */}
          <div className="absolute top-4 left-0 right-0 flex justify-center">
            <div className="bg-black/60 text-white px-4 py-2 rounded-full text-sm font-medium">
              {formatAngleName(currentAngle)} shot
            </div>
          </div>

          {/* Corner guides */}
          <div className="absolute inset-8">
            <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-white/60 rounded-tl-lg" />
            <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-white/60 rounded-tr-lg" />
            <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-white/60 rounded-bl-lg" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-white/60 rounded-br-lg" />
          </div>

          {/* Photo count */}
          <div className="absolute top-4 right-4">
            <div className="bg-black/60 text-white px-3 py-1.5 rounded-full text-xs font-medium">
              {photoCount} / {maxPhotos}
            </div>
          </div>

          {/* Photo type label */}
          <div className="absolute top-4 left-4">
            <div
              className={clsx(
                "px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide",
                photoType === "before"
                  ? "bg-marine-500/80 text-white"
                  : "bg-amber-500/80 text-white",
              )}
            >
              {photoType}
            </div>
          </div>
        </div>
      </div>

      {/* Angle selector */}
      <div className="bg-black/90 px-4 py-2">
        <div className="flex gap-1 overflow-x-auto scrollbar-thin pb-1">
          {RECOMMENDED_ANGLES.map((angle, index) => (
            <button
              key={angle}
              onClick={() => onAngleChange(index)}
              className={clsx(
                "flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors",
                index === currentAngleIndex
                  ? "bg-white text-navy-900"
                  : "bg-white/10 text-white/70 hover:bg-white/20",
              )}
            >
              {formatAngleName(angle)}
            </button>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="bg-black/95 safe-bottom">
        <div className="flex items-center justify-between px-6 py-4">
          {onBack ? (
            <button
              onClick={onBack}
              className="text-white/70 hover:text-white text-sm font-medium px-3 py-2"
            >
              Back
            </button>
          ) : (
            <div className="w-16" />
          )}

          {/* Capture button */}
          <button
            onClick={handleCapture}
            disabled={!isReady}
            className={clsx(
              "w-16 h-16 rounded-full border-4 border-white flex items-center justify-center",
              "transition-transform active:scale-95",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
            aria-label="Capture photo"
          >
            <div className="w-12 h-12 rounded-full bg-white" />
          </button>

          <div className="flex items-center gap-3">
            {/* Switch camera */}
            <button
              onClick={() => void switchCamera()}
              className="text-white/70 hover:text-white p-2"
              aria-label="Switch camera"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182M21.015 4.356v4.992"
                />
              </svg>
            </button>

            {/* Done */}
            {photoCount > 0 && (
              <button
                onClick={onComplete}
                className="text-marine-400 hover:text-marine-300 text-sm font-semibold px-3 py-2"
              >
                Done ({photoCount})
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
