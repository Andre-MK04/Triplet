"use client";

import { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, forwardRef } from "react";

const fieldClass =
  "w-full rounded-xl border border-line bg-ink-soft/80 px-3.5 py-2.5 text-sm text-cloud placeholder:text-mist/60 " +
  "transition focus:border-mint/60 focus:outline-none focus:ring-2 focus:ring-mint/20";

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
      <span className="block text-xs font-semibold uppercase tracking-wide text-mist">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-mist/70">{hint}</span> : null}
    </label>
  );
}
