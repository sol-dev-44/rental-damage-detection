import clsx from "clsx";

type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "navy";

type BadgeSize = "sm" | "md";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  className?: string;
  dot?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-dock-100 text-dock-700",
  success: "bg-green-50 text-green-700",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-red-50 text-red-700",
  info: "bg-marine-50 text-marine-700",
  navy: "bg-navy-50 text-navy-700",
};

const dotVariantClasses: Record<BadgeVariant, string> = {
  default: "bg-dock-400",
  success: "bg-green-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  info: "bg-marine-500",
  navy: "bg-navy-500",
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-xs",
  md: "px-2.5 py-1 text-xs",
};

export function Badge({
  children,
  variant = "default",
  size = "sm",
  className,
  dot = false,
}: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center font-medium rounded-full",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {dot && (
        <span
          className={clsx(
            "w-1.5 h-1.5 rounded-full mr-1.5",
            dotVariantClasses[variant],
          )}
        />
      )}
      {children}
    </span>
  );
}

// Convenience helpers for common status mappings

export function inspectionStatusBadgeVariant(
  status: string,
): BadgeVariant {
  switch (status) {
    case "completed":
      return "success";
    case "review":
      return "warning";
    case "analyzing":
      return "info";
    case "capturing":
      return "navy";
    case "draft":
      return "default";
    default:
      return "default";
  }
}

export function severityBadgeVariant(severity: string): BadgeVariant {
  switch (severity) {
    case "critical":
    case "severe":
      return "danger";
    case "moderate":
      return "warning";
    case "minor":
      return "info";
    case "none":
      return "success";
    default:
      return "default";
  }
}

export function findingStatusBadgeVariant(status: string): BadgeVariant {
  switch (status) {
    case "confirmed":
      return "success";
    case "rejected":
      return "danger";
    case "corrected":
      return "warning";
    case "pending":
      return "default";
    default:
      return "default";
  }
}
