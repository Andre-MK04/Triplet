"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";
import Link from "next/link";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition " +
  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint " +
  "disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]";

const variants: Record<Variant, string> = {
  primary: "bg-mint text-ink hover:brightness-110 shadow-glow",
  secondary: "border border-line bg-white/5 text-cloud hover:border-mint/50 hover:bg-white/10",
  ghost: "text-mist hover:text-cloud hover:bg-white/5",
  danger: "border border-coral/40 bg-coral-soft text-coral hover:bg-coral/25",
};

const sizes: Record<Size, string> = {
  sm: "px-3.5 py-1.5 text-sm",
  md: "px-5 py-2.5 text-sm",
  lg: "px-7 py-3.5 text-base",
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
