"use client";

import { useEffect, useId, useRef, useState } from "react";

import { Button } from "./Button";

/**
 * A modal for a decision that cannot be undone.
 *
 * window.confirm() is unstyled, unlabelled to assistive technology beyond its
 * bare string, impossible to make the consequences legible in, and in some
 * browsers suppressible entirely — which for account deletion means the
 * safeguard may simply not appear. This is the replacement.
 *
 * Where `confirmPhrase` is set the action stays disabled until the exact phrase
 * is typed. That is deliberate friction, reserved for destruction that has no
 * undo.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  confirmPhrase,
  onConfirm,
  onCancel,
  isWorking = false,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  confirmPhrase?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isWorking?: boolean;
}) {
  const [typed, setTyped] = useState("");
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) {
      setTyped("");
      return;
    }
    // Focus lands on Cancel, not Confirm: opening a destructive dialog should
    // never leave the destructive action one Enter away.
    cancelRef.current?.focus();

    const previouslyFocused = document.activeElement as HTMLElement | null;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab") return;

      // Keep focus inside the dialog while it is open.
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input, [href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      previouslyFocused?.focus();
    };
  }, [open, onCancel]);

  if (!open) return null;

  const phraseSatisfied = !confirmPhrase || typed.trim() === confirmPhrase;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-deep/80 p-4 sm:items-center"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="w-full max-w-md border border-line bg-ink-raised p-6"
      >
        <h2 id={titleId} className="font-display text-2xl font-bold text-cloud">
          {title}
        </h2>
        <div id={descriptionId} className="mt-3 space-y-3 text-sm leading-relaxed text-mist">
          {children}
        </div>

        {confirmPhrase ? (
          <label className="mt-5 block">
            <span className="block font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
              Type <span className="text-coral">{confirmPhrase}</span> to continue
            </span>
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              autoComplete="off"
              // A slip of the keyboard should not be able to satisfy this.
              spellCheck={false}
              className="cmd-input mt-2 w-full py-2 font-mono text-sm text-cloud"
              aria-label={`Type ${confirmPhrase} to confirm`}
            />
          </label>
        ) : null}

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button ref={cancelRef} variant="secondary" onClick={onCancel} disabled={isWorking}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            disabled={!phraseSatisfied || isWorking}
          >
            {isWorking ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
