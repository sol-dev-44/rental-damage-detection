import { type ButtonHTMLAttributes, forwardRef } from "react";
import clsx from "clsx";
import { LoadingSpinner } from "./LoadingSpinner";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-navy-600 text-white hover:bg-navy-700 active:bg-navy-800 focus-visible:ring-navy-500",
  secondary:
    "bg-white text-navy-700 border border-dock-300 hover:bg-dock-50 active:bg-dock-100 focus-visible:ring-navy-500",
  danger:
    "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus-visible:ring-red-500",
  ghost:
    "bg-transparent text-navy-600 hover:bg-navy-50 active:bg-navy-100 focus-visible:ring-navy-500",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-sm gap-1.5",
  md: "px-4 py-2 text-sm gap-2",
  lg: "px-6 py-3 text-base gap-2.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "primary",
      size = "md",
      isLoading = false,
      fullWidth = false,
      leftIcon,
      rightIcon,
      className,
      disabled,
      children,
      ...props
    },
    ref,
  ) {
    return (
      <button
        ref={ref}
        className={clsx(
          "inline-flex items-center justify-center font-medium rounded-lg",
          "transition-colors duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          variantClasses[variant],
          sizeClasses[size],
          fullWidth && "w-full",
          className,
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <LoadingSpinner size="sm" />
        ) : (
          leftIcon && <span className="flex-shrink-0">{leftIcon}</span>
        )}
        {children}
        {rightIcon && !isLoading && (
          <span className="flex-shrink-0">{rightIcon}</span>
        )}
      </button>
    );
  },
);
