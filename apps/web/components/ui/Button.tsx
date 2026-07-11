"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";
import Link from "next/link";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

// Instrument-panel buttons: sharp corners, mono small-caps labels.
const base =
  "inline-flex items-center justify-center gap-2 rounded-none font-mono font-semibold uppercase tracking-label transition " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const variants: Record<Variant, string> = {
  primary: "bg-mint text-mint-ink hover:opacity-90",
  secondary: "border border-line bg-transparent text-cloud hover:border-mint/60 hover:text-mint",
  ghost: "text-mist hover:text-cloud",
  danger: "border border-coral/40 bg-transparent text-coral hover:bg-coral/10",
};

const sizes: Record<Size, string> = {
  sm: "px-3.5 py-2 text-[10px]",
  md: "px-5 py-2.5 text-[11px]",
  lg: "px-7 py-3.5 text-xs",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", className = "", ...props },
  ref,
) {
  return <button ref={ref} className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...props} />;
});

type ButtonLinkProps = {
  href: string;
  variant?: Variant;
  size?: Size;
  className?: string;
  children: React.ReactNode;
};

export function ButtonLink({ href, variant = "primary", size = "md", className = "", children }: ButtonLinkProps) {
  return (
    <Link href={href} className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}>
      {children}
    </Link>
  );
}
