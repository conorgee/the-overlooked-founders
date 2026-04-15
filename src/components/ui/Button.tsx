import type { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  children: ReactNode;
}

const variants = {
  primary: "bg-accent text-black hover:bg-accent-hover",
  secondary: "border border-white/20 text-white hover:border-white/50 bg-transparent",
  ghost: "text-text-muted hover:text-white bg-transparent",
};

const sizes = {
  sm: "px-4 py-2 text-xs uppercase tracking-widest",
  md: "px-6 py-3 text-xs uppercase tracking-widest",
  lg: "px-8 py-4 text-sm uppercase tracking-widest",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 font-medium transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
