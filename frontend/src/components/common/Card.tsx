import { type ReactNode } from "react";
import clsx from "clsx";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
  hover?: boolean;
  onClick?: () => void;
}

const paddingClasses = {
  none: "",
  sm: "p-3",
  md: "p-4 sm:p-6",
  lg: "p-6 sm:p-8",
};

export function Card({
  children,
  className,
  padding = "md",
  hover = false,
  onClick,
}: CardProps) {
  const Component = onClick ? "button" : "div";

  return (
    <Component
      className={clsx(
        "bg-white rounded-xl border border-dock-200 shadow-sm",
        paddingClasses[padding],
        hover && "hover:shadow-md hover:border-dock-300 transition-shadow duration-200",
        onClick && "cursor-pointer text-left w-full",
        className,
      )}
      onClick={onClick}
    >
      {children}
    </Component>
  );
}

interface CardHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
}

export function CardHeader({ title, subtitle, action, className }: CardHeaderProps) {
  return (
    <div className={clsx("flex items-start justify-between", className)}>
      <div>
        <h3 className="text-base font-semibold text-navy-900">{title}</h3>
        {subtitle && (
          <p className="mt-0.5 text-sm text-dock-500">{subtitle}</p>
        )}
      </div>
      {action && <div className="flex-shrink-0 ml-4">{action}</div>}
    </div>
  );
}

interface CardFooterProps {
  children: ReactNode;
  className?: string;
}

export function CardFooter({ children, className }: CardFooterProps) {
  return (
    <div
      className={clsx(
        "mt-4 pt-4 border-t border-dock-100 flex items-center gap-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
