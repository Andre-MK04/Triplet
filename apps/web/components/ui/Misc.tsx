export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-mist" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-mint/30 border-t-mint" aria-hidden />
      {label ?? "Loading…"}
    </span>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  /** Accepted for backwards compatibility; the ruled typographic style has no icon. */
  icon?: string;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  // Typographic empty state: a ruled block, no illustration.
  return (
    <div className="border-y border-line px-6 py-16 text-center">
      <h3 className="mx-auto max-w-md font-display text-2xl font-bold text-cloud">{title}</h3>
      {children ? <div className="mx-auto mt-3 max-w-md text-sm text-mist">{children}</div> : null}
      {action ? <div className="mt-6 flex justify-center">{action}</div> : null}
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
        <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">{eyebrow}</p>
      ) : null}
      <h2 className="font-display text-3xl font-bold tracking-tight text-cloud sm:text-4xl">{title}</h2>
      {children ? <p className="mt-3 text-base leading-relaxed text-mist">{children}</p> : null}
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
    info: "border-sky/30 text-sky",
    warning: "border-gold/30 text-gold",
    error: "border-coral/40 text-coral",
    success: "border-mint/40 text-mint",
  } as const;
  // A quiet statement with a tinted left rule — not an alert box.
  return (
    <div className={`rounded-none border-l-2 bg-transparent px-4 py-2 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}
