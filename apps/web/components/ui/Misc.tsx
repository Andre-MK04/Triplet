export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-mist" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-mint/30 border-t-mint" aria-hidden />
      {label ?? "Loading…"}
    </span>
  );
}

export function EmptyState({
  icon = "🧭",
  title,
  children,
  action,
}: {
  icon?: string;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="glass rounded-card flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="text-4xl" aria-hidden>
        {icon}
      </span>
      <h3 className="text-lg font-semibold text-cloud">{title}</h3>
      {children ? <div className="max-w-md text-sm text-mist">{children}</div> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      {eyebrow ? (
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.2em] text-mint">{eyebrow}</p>
      ) : null}
      <h2 className="font-display text-3xl font-bold tracking-tight text-cloud sm:text-4xl">{title}</h2>
      {children ? <p className="mt-3 text-base text-mist">{children}</p> : null}
    </div>
  );
}

export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "warning" | "error" | "success";
  children: React.ReactNode;
}) {
  const tones = {
    info: "border-sky/30 bg-sky-soft text-sky",
    warning: "border-gold/30 bg-gold/10 text-gold",
    error: "border-coral/40 bg-coral-soft text-coral",
    success: "border-mint/40 bg-mint-soft text-mint",
  } as const;
  return <div className={`rounded-xl border px-4 py-3 text-sm ${tones[tone]}`}>{children}</div>;
}
