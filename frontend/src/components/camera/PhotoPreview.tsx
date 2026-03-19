import { useState } from "react";
import clsx from "clsx";
import { Button } from "@/components/common/Button";
import { Modal } from "@/components/common/Modal";

interface PreviewPhoto {
  id: string;
  dataUrl: string;
  angle: string;
  photoType: "before" | "after";
  uploaded: boolean;
}

interface PhotoPreviewProps {
  photos: PreviewPhoto[];
  onDelete: (photoId: string) => void;
  onRetake?: (photoId: string) => void;
  title?: string;
}

export function PhotoPreview({
  photos,
  onDelete,
  onRetake,
  title,
}: PhotoPreviewProps) {
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(null);
  const selectedPhoto = photos.find((p) => p.id === selectedPhotoId);

  const formatAngleName = (angle: string): string => {
    return angle.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  if (photos.length === 0) {
    return (
      <div className="text-center py-8 text-dock-400">
        <svg
          className="w-12 h-12 mx-auto mb-3 text-dock-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
          />
        </svg>
        <p className="text-sm">No photos captured yet</p>
      </div>
    );
  }

  return (
    <div>
      {title && (
        <h4 className="text-sm font-medium text-navy-800 mb-3">{title}</h4>
      )}

      {/* Thumbnail grid */}
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
        {photos.map((photo) => (
          <div key={photo.id} className="relative group">
            <button
              onClick={() => setSelectedPhotoId(photo.id)}
              className="block w-full aspect-square rounded-lg overflow-hidden focus:outline-none focus:ring-2 focus:ring-navy-500 focus:ring-offset-2"
            >
              <img
                src={photo.dataUrl}
                alt={`${formatAngleName(photo.angle)} - ${photo.photoType}`}
                className="w-full h-full object-cover"
              />
            </button>

            {/* Angle label */}
            <div className="absolute bottom-1 left-1 right-1">
              <span className="text-[10px] font-medium bg-black/60 text-white px-1.5 py-0.5 rounded">
                {formatAngleName(photo.angle)}
              </span>
            </div>

            {/* Upload status indicator */}
            <div className="absolute top-1 right-1">
              {photo.uploaded ? (
                <span className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center">
                  <svg
                    className="w-2.5 h-2.5 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </span>
              ) : (
                <span className="w-4 h-4 rounded-full bg-amber-500 flex items-center justify-center">
                  <svg
                    className="w-2.5 h-2.5 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                    />
                  </svg>
                </span>
              )}
            </div>

            {/* Delete on hover */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(photo.id);
              }}
              className={clsx(
                "absolute top-1 left-1 w-5 h-5 rounded-full",
                "bg-red-500 text-white flex items-center justify-center",
                "opacity-0 group-hover:opacity-100 transition-opacity",
                "focus:opacity-100",
              )}
              aria-label={`Delete ${formatAngleName(photo.angle)} photo`}
            >
              <svg
                className="w-3 h-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={3}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {/* Full-size preview modal */}
      <Modal
        isOpen={Boolean(selectedPhoto)}
        onClose={() => setSelectedPhotoId(null)}
        title={
          selectedPhoto
            ? `${formatAngleName(selectedPhoto.angle)} - ${selectedPhoto.photoType === "before" ? "Before" : "After"}`
            : undefined
        }
        size="xl"
      >
        {selectedPhoto && (
          <div className="space-y-4">
            <div className="rounded-lg overflow-hidden bg-black">
              <img
                src={selectedPhoto.dataUrl}
                alt={formatAngleName(selectedPhoto.angle)}
                className="w-full h-auto max-h-[60vh] object-contain"
              />
            </div>
            <div className="flex gap-2 justify-end">
              {onRetake && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    onRetake(selectedPhoto.id);
                    setSelectedPhotoId(null);
                  }}
                >
                  Retake
                </Button>
              )}
              <Button
                variant="danger"
                size="sm"
                onClick={() => {
                  onDelete(selectedPhoto.id);
                  setSelectedPhotoId(null);
                }}
              >
                Delete
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
