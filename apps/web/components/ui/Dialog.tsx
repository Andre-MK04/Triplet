"use client";

import { useEffect, useId, useRef } from "react";

/**
 * A modal overlay that behaves like one.
 *
 * Triplet's overlays already carried role="dialog" and aria-modal, which
 * announces a modal without being one: focus stayed loose behind the overlay,
 * Escape did nothing, and dismissing left focus on whatever the browser
 * happened to pick. A screen-reader user was told they were in a dialog and
 * then tabbed straight out of it into the page underneath.
 *
 * Everything modal behaviour actually requires lives here so no overlay has to
 * remember it: focus moved in and trapped, Escape to close, focus returned to
 * whatever opened it, the page behind made inert and unscrollable.
 *
 * A bottom sheet on small screens and a centred dialog on large ones — the same
 * component, because they are the same thing and only the geometry differs.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  labelledBy,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  /** Rendered as the dialog's heading and used as its accessible name. */
  title?: string;
  /** Optional supporting line, referenced by aria-describedby. */
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** For a dialog that renders its own heading: the id of that heading. */
  labelledBy?: string;
  size?: "sm" | "md" | "lg";
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  // Callers pass an inline arrow for onClose, so its identity changes on every
  // render. Held in a ref and kept out of the effect's dependencies, because an
  // effect that tears down and re-runs each render would re-capture "what had
  // focus" as whatever the dialog itself had just focused — and then restore
  // focus to nothing on close.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Where focus came from. `undefined` means "not captured yet"; the value is
  // written once and never overwritten, because React re-runs effects in
  // development and a second capture would record whatever the first run had
  // just focused — an element inside the panel, which is gone by the time
  // focus needs restoring.
  const returnFocusTo = useRef<HTMLElement | null | undefined>(undefined);

  // Captured during the render that opens the dialog, not in an effect.
  //
  // By the time effects run, a panel containing an autoFocus field has already
  // taken focus, so an effect would record something inside the dialog and
  // "restore" focus to an element about to be removed — dropping the reader on
  // the body instead of the control they opened this with. During render the
  // children have not mounted yet, so this is still the opener.
  if (typeof document !== "undefined" && open && returnFocusTo.current === undefined) {
    returnFocusTo.current = document.activeElement as HTMLElement | null;
  }

  useEffect(() => {
    if (!open) return;

    // Move focus into the dialog. The panel itself when nothing inside wants
    // it, so a screen reader starts at the heading rather than mid-content.
    const focusables = () =>
      Array.from(
        panelRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((element) => element.offsetParent !== null);

    (focusables()[0] ?? panelRef.current)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const elements = focusables();
      if (elements.length === 0) {
        event.preventDefault();
        return;
      }
      const first = elements[0];
      const last = elements[elements.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || active === panelRef.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown, true);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.style.overflow = previousOverflow;
      // Put focus back where it came from, so dismissing does not lose the
      // reader's place in the page. Deferred by a frame: React is still
      // committing this unmount, and focusing an element mid-commit is undone
      // when the browser moves focus off the nodes being removed.
      const target = returnFocusTo.current;
      // Cleared here rather than on the render that closes the dialog: a
      // Dialog kept mounted with open={false} renders before its effect tears
      // down, so clearing during render would wipe the target moments before
      // the cleanup needs it.
      returnFocusTo.current = undefined;
      if (!target) return;
      // Try immediately, then once more on a timer. React is still committing
      // this unmount, so the first attempt can be undone as the browser drops
      // focus from the nodes being removed — but the retry must not be a
      // requestAnimationFrame, which never fires while the page is hidden and
      // would leave a backgrounded tab with focus stranded on the body.
      target.focus();
      setTimeout(() => {
        if (target.isConnected && document.activeElement !== target) target.focus();
      }, 0);
    };
  }, [open]);

  if (!open) return null;

  const widths = { sm: "max-w-sm", md: "max-w-lg", lg: "max-w-2xl" } as const;

  return (
    <div
      className="fixed inset-0 z-[70] flex items-end justify-center bg-ink/70 backdrop-blur-sm sm:items-center sm:p-4"
      onMouseDown={(event) => {
        // Only a press that both starts and ends on the backdrop dismisses, so
        // a drag that happens to finish outside does not close the dialog.
        if (event.target === event.currentTarget) onCloseRef.current();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy ?? (title ? titleId : undefined)}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={`max-h-[90vh] w-full overflow-y-auto border border-line bg-ink-raised ${widths[size]} sm:max-h-[85vh]`}
      >
        {title ? (
          <div className="border-b border-line px-5 py-4">
            <h2 id={titleId} className="font-display text-xl font-bold text-cloud">
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="mt-1 text-sm leading-relaxed text-mist">
                {description}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="px-5 py-4">{children}</div>

        {footer ? <div className="border-t border-line px-5 py-4">{footer}</div> : null}
      </div>
    </div>
  );
}
