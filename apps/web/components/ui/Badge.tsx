type Tone = "mint" | "sky" | "coral" | "gold" | "neutral" | "live" | "cached" | "demo";

const tones: Record<Tone, string> = {
  mint: "bg-mint-soft text-mint border-mint/30",
  sky: "bg-sky-soft text-sky border-sky/30",
  coral: "bg-coral-soft text-coral border-coral/30",
  gold: "bg-gold/15 text-gold border-gold/30",
  neutral: "bg-white/5 text-mist border-line",
  live: "bg-mint-soft text-mint border-mint/30",
  cached: "bg-sky-soft text-sky border-sky/30",
  demo: "bg-white/5 text-mist border-line",
};

type BadgeProps = {
  tone?: Tone;
  className?: string;
  title?: string;
  children: React.ReactNode;
};

export function Badge({ tone = "neutral", className = "", title, children }: BadgeProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
