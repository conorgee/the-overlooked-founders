import type { TextareaHTMLAttributes } from "react";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export function Textarea({ label, error, className = "", ...props }: TextareaProps) {
  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label className="text-xs uppercase tracking-widest text-text-muted font-medium">
          {label}
        </label>
      )}
      <textarea
        className={`bg-transparent border-b border-white/20 px-0 py-3 text-white placeholder:text-text-subtle focus:outline-none focus:border-white transition-colors resize-y min-h-[120px] ${
          error ? "border-red-400" : ""
        } ${className}`}
        {...props}
      />
      {error && <p className="text-red-400 text-xs mt-1">{error}</p>}
    </div>
  );
}
