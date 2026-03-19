import { useState, useRef, useCallback } from "react";
import clsx from "clsx";
import type { Photo, Finding } from "@/lib/types";

interface BeforeAfterComparisonProps {
  beforePhotos: Photo[];
  afterPhotos: Photo[];
  findings: Finding[];
  onFindingClick?: (finding: Finding) => void;
}

type ViewMode = "slider" | "toggle" | "side_by_side";

export function BeforeAfterComparison({
  beforePhotos,
  afterPhotos,
  findings,
  onFindingClick,
}: BeforeAfterComparisonProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("slider");
  const [selectedAngleIndex, setSelectedAngleIndex] = useState(0);
  const [sliderPosition, setSliderPosition] = useState(50);
  const [showBefore, setShowBefore] = useState(true);
  const [zoom, setZoom] = useState(1);
  const containerRef = useRef<HTMLDivElement>(null);

  const beforePhoto = beforePhotos[selectedAngleIndex];
  const afterPhoto = afterPhotos[selectedAngleIndex];

  // Get findings for the current after photo
  const photoFindings = afterPhoto
    ? findings.filter((f) => f.photo_id === afterPhoto.id)
    : [];

  const handleSliderMove = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const clientX =
        "touches" in e ? (e.touches[0]?.clientX ?? 0) : e.clientX;
      const x = clientX - rect.left;
      const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
      setSliderPosition(percentage);
    },
    [],
  );

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.25, 3));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.25, 1));
  const handleZoomReset = () => setZoom(1);

  return (
    <div className="space-y-4">
      {/* View mode switcher */}
      <div className="flex items-center justify-between">
        <div className="flex bg-dock-100 rounded-lg p-0.5">
          {(
            [
              { mode: "slider" as const, label: "Slider" },
              { mode: "toggle" as const, label: "Toggle" },
              { mode: "side_by_side" as const, label: "Side by Side" },
            ] as const
          ).map(({ mode, label }) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={clsx(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                viewMode === mode
                  ? "bg-white text-navy-700 shadow-sm"
                  : "text-dock-500 hover:text-dock-700",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= 1}
            className="p-1.5 rounded text-dock-500 hover:text-navy-700 disabled:opacity-30"
            aria-label="Zoom out"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM13.5 10.5h-6" />
            </svg>
          </button>
          <button
            onClick={handleZoomReset}
            className="text-xs text-dock-500 px-1"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= 3}
            className="p-1.5 rounded text-dock-500 hover:text-navy-700 disabled:opacity-30"
            aria-label="Zoom in"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6" />
            </svg>
          </button>
        </div>
      </div>

      {/* Photo angle selector */}
      {(beforePhotos.length > 1 || afterPhotos.length > 1) && (
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          {afterPhotos.map((photo, index) => (
            <button
              key={photo.id}
              onClick={() => setSelectedAngleIndex(index)}
              className={clsx(
                "flex-shrink-0 w-14 h-14 rounded-lg overflow-hidden border-2 transition-colors",
                index === selectedAngleIndex
                  ? "border-navy-500"
                  : "border-transparent hover:border-dock-300",
              )}
            >
              <img
                src={photo.thumbnail_url ?? photo.url}
                alt={photo.metadata.angle}
                className="w-full h-full object-cover"
              />
            </button>
          ))}
        </div>
      )}

      {/* Comparison view */}
      <div
        ref={containerRef}
        className="relative rounded-xl overflow-hidden bg-black select-none"
        style={{ aspectRatio: "16/10" }}
      >
        {viewMode === "slider" && beforePhoto && afterPhoto && (
          <div
            className="relative w-full h-full overflow-hidden"
            onMouseMove={(e) => {
              if (e.buttons === 1) handleSliderMove(e);
            }}
            onTouchMove={handleSliderMove}
          >
            {/* After (bottom layer) */}
            <div className="absolute inset-0" style={{ transform: `scale(${zoom})` }}>
              <img
                src={afterPhoto.url}
                alt="After"
                className="w-full h-full object-contain"
                draggable={false}
              />
              {/* Damage markers */}
              {photoFindings.map((finding) =>
                finding.bounding_box ? (
                  <button
                    key={finding.id}
                    onClick={() => onFindingClick?.(finding)}
                    className={clsx(
                      "absolute border-2 rounded",
                      finding.status === "confirmed"
                        ? "border-red-500"
                        : finding.status === "rejected"
                          ? "border-dock-400"
                          : "border-amber-400",
                    )}
                    style={{
                      left: `${finding.bounding_box.x}%`,
                      top: `${finding.bounding_box.y}%`,
                      width: `${finding.bounding_box.width}%`,
                      height: `${finding.bounding_box.height}%`,
                    }}
                    aria-label={`${finding.damage_type} - ${finding.severity}`}
                  >
                    <span className="absolute -top-5 left-0 text-[10px] bg-black/70 text-white px-1 rounded whitespace-nowrap">
                      {finding.damage_type}
                    </span>
                  </button>
                ) : null,
              )}
            </div>

            {/* Before (clipped top layer) */}
            <div
              className="absolute inset-0 overflow-hidden"
              style={{
                clipPath: `inset(0 ${100 - sliderPosition}% 0 0)`,
                transform: `scale(${zoom})`,
              }}
            >
              <img
                src={beforePhoto.url}
                alt="Before"
                className="w-full h-full object-contain"
                draggable={false}
              />
            </div>

            {/* Slider handle */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg cursor-col-resize z-10"
              style={{ left: `${sliderPosition}%` }}
              onMouseDown={(e) => {
                e.preventDefault();
                const handleMove = (me: MouseEvent) =>
                  handleSliderMove(me as unknown as React.MouseEvent);
                const handleUp = () => {
                  window.removeEventListener("mousemove", handleMove);
                  window.removeEventListener("mouseup", handleUp);
                };
                window.addEventListener("mousemove", handleMove);
                window.addEventListener("mouseup", handleUp);
              }}
            >
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white shadow-lg flex items-center justify-center">
                <svg className="w-4 h-4 text-dock-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l4-4 4 4m0 6l-4 4-4-4" />
                </svg>
              </div>
            </div>

            {/* Labels */}
            <div className="absolute top-3 left-3 bg-marine-500/80 text-white text-xs font-semibold px-2 py-1 rounded">
              Before
            </div>
            <div className="absolute top-3 right-3 bg-amber-500/80 text-white text-xs font-semibold px-2 py-1 rounded">
              After
            </div>
          </div>
        )}

        {viewMode === "toggle" && (
          <div className="relative w-full h-full" style={{ transform: `scale(${zoom})` }}>
            <img
              src={
                showBefore
                  ? (beforePhoto?.url ?? "")
                  : (afterPhoto?.url ?? "")
              }
              alt={showBefore ? "Before" : "After"}
              className="w-full h-full object-contain"
            />
            {!showBefore &&
              photoFindings.map((finding) =>
                finding.bounding_box ? (
                  <button
                    key={finding.id}
                    onClick={() => onFindingClick?.(finding)}
                    className="absolute border-2 border-amber-400 rounded"
                    style={{
                      left: `${finding.bounding_box.x}%`,
                      top: `${finding.bounding_box.y}%`,
                      width: `${finding.bounding_box.width}%`,
                      height: `${finding.bounding_box.height}%`,
                    }}
                    aria-label={`${finding.damage_type} - ${finding.severity}`}
                  />
                ) : null,
              )}
            <button
              onClick={() => setShowBefore(!showBefore)}
              className={clsx(
                "absolute bottom-3 left-1/2 -translate-x-1/2",
                "px-4 py-2 rounded-full text-sm font-medium",
                "bg-white/90 text-navy-800 shadow-lg",
                "hover:bg-white transition-colors",
              )}
            >
              Show {showBefore ? "After" : "Before"}
            </button>
            <div
              className={clsx(
                "absolute top-3 left-3 text-xs font-semibold px-2 py-1 rounded",
                showBefore
                  ? "bg-marine-500/80 text-white"
                  : "bg-amber-500/80 text-white",
              )}
            >
              {showBefore ? "Before" : "After"}
            </div>
          </div>
        )}

        {viewMode === "side_by_side" && (
          <div className="flex w-full h-full">
            <div className="flex-1 relative" style={{ transform: `scale(${zoom})` }}>
              {beforePhoto && (
                <img
                  src={beforePhoto.url}
                  alt="Before"
                  className="w-full h-full object-contain"
                />
              )}
              <div className="absolute top-2 left-2 bg-marine-500/80 text-white text-xs font-semibold px-2 py-1 rounded">
                Before
              </div>
            </div>
            <div className="w-px bg-white/30" />
            <div className="flex-1 relative" style={{ transform: `scale(${zoom})` }}>
              {afterPhoto && (
                <>
                  <img
                    src={afterPhoto.url}
                    alt="After"
                    className="w-full h-full object-contain"
                  />
                  {photoFindings.map((finding) =>
                    finding.bounding_box ? (
                      <button
                        key={finding.id}
                        onClick={() => onFindingClick?.(finding)}
                        className="absolute border-2 border-amber-400 rounded"
                        style={{
                          left: `${finding.bounding_box.x}%`,
                          top: `${finding.bounding_box.y}%`,
                          width: `${finding.bounding_box.width}%`,
                          height: `${finding.bounding_box.height}%`,
                        }}
                        aria-label={`${finding.damage_type} - ${finding.severity}`}
                      />
                    ) : null,
                  )}
                </>
              )}
              <div className="absolute top-2 right-2 bg-amber-500/80 text-white text-xs font-semibold px-2 py-1 rounded">
                After
              </div>
            </div>
          </div>
        )}

        {/* No photos fallback */}
        {!beforePhoto && !afterPhoto && (
          <div className="flex items-center justify-center h-full text-dock-400 text-sm">
            No photos available for comparison
          </div>
        )}
      </div>

      {/* Findings count */}
      {photoFindings.length > 0 && (
        <p className="text-xs text-dock-500">
          {photoFindings.length} finding{photoFindings.length !== 1 ? "s" : ""}{" "}
          on this view
        </p>
      )}
    </div>
  );
}
