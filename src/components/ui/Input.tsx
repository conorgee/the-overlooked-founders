import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export function Input({ label, error, className = "", ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label className="text-xs uppercase tracking-widest text-text-muted font-medium">
          {label}
        </label>
      )}
      <input
        className={`bg-transparent border-b border-white/20 px-0 py-3 text-white placeholder:text-text-subtle focus:outline-none focus:border-white transition-colors ${
          error ? "border-red-400" : ""
        } ${className}`}
        {...props}
      />
      {error && <p className="text-red-400 text-xs mt-1">{error}</p>}
    </div>
  );
}
