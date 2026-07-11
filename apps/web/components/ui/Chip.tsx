"use client";

type ChipProps = {
  selected?: boolean;
  onClick?: () => void;
  className?: string;
  children: React.ReactNode;
  ariaLabel?: string;
};

export function Chip({ selected = false, onClick, className = "", children, ariaLabel }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={ariaLabel}
      onClick={onClick}
      className={
        // Selection is a solid rectangular fill, per the design system.
        "inline-flex items-center gap-1.5 rounded-none border px-3.5 py-2 text-sm font-medium transition " +
        (selected
          ? "border-mint bg-mint text-mint-ink "
          : "border-line bg-transparent text-mist hover:border-mint/40 hover:text-cloud ") +
        className
      }
    >
      {children}
    </button>
  );
}
