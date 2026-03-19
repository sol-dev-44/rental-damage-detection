import { useEffect, useRef, type ReactNode } from "react";
import clsx from "clsx";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl" | "full";
  showCloseButton?: boolean;
}

const sizeClasses = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  full: "max-w-full mx-4",
};

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  size = "md",
  showCloseButton = true,
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
      previousFocusRef.current?.focus();
    }

    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) {
      onClose();
    }
  }

  return (
    <div
      ref={overlayRef}
      className={clsx(
        "fixed inset-0 z-50 flex items-center justify-center p-4",
        "bg-black/50 backdrop-blur-sm",
        "animate-in fade-in duration-200",
      )}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={clsx(
          "relative w-full bg-white rounded-xl shadow-xl",
          "transform transition-all",
          sizeClasses[size],
        )}
      >
        {(title || showCloseButton) && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-dock-200">
            {title && (
              <h2 className="text-lg font-semibold text-navy-900">{title}</h2>
            )}
            {showCloseButton && (
              <button
                onClick={onClose}
                className={clsx(
                  "p-1.5 rounded-lg text-dock-400 hover:text-dock-600",
                  "hover:bg-dock-100 transition-colors",
                  !title && "ml-auto",
                )}
                aria-label="Close modal"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
          </div>
        )}
        <div className="px-6 py-4">{children}</div>
      </div>
    </div>
  );
}
