import clsx from "clsx";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizeClasses = {
  sm: "h-4 w-4 border-2",
  md: "h-8 w-8 border-2",
  lg: "h-12 w-12 border-3",
};

export function LoadingSpinner({
  size = "md",
  className,
  label = "Loading...",
}: LoadingSpinnerProps) {
  return (
    <div
      className={clsx("flex items-center justify-center", className)}
      role="status"
      aria-label={label}
    >
      <div
        className={clsx(
          "animate-spin rounded-full border-navy-200 border-t-navy-600",
          sizeClasses[size],
        )}
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}
