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
        "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-sm font-medium transition active:scale-95 " +
        (selected
          ? "border-mint/60 bg-mint-soft text-mint shadow-glow "
          : "border-line bg-white/5 text-mist hover:border-mint/40 hover:text-cloud ") +
        className
      }
    >
      {children}
    </button>
  );
}
