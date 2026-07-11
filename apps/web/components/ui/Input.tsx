"use client";

import { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, forwardRef } from "react";

// Command-line fields: no box, just a bottom hairline that turns mint on focus.
const fieldClass =
  "cmd-input w-full py-2.5 text-sm text-cloud placeholder:text-mist/50 focus:ring-0";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className = "", ...props },
  ref,
) {
  return <input ref={ref} className={`${fieldClass} ${className}`} {...props} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className = "", ...props }, ref) {
    return <textarea ref={ref} className={`${fieldClass} min-h-24 ${className}`} {...props} />;
  },
);

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { className = "", children, ...props },
  ref,
) {
  return (
    <select ref={ref} className={`${fieldClass} appearance-none ${className}`} {...props}>
      {children}
    </select>
  );
});

type FieldProps = {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: React.ReactNode;
};

export function Field({ label, hint, htmlFor, children }: FieldProps) {
  return (
    <label htmlFor={htmlFor} className="block space-y-1.5">
      <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-mist/70">{hint}</span> : null}
    </label>
  );
}
